import json
import random
from pathlib import Path

import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PLAYERS_FILE = "data/players.json"
SELECTION_FILE = "data/master_selection.txt"
OVERRIDES_FILE = "data/overrides.json"
OUTPUT_FILE = "outputs/excel/pronostics_tournoi.xlsx"
POST_DATA_FILE = "outputs/csv/master_post_data.csv"
RUNTIME_CONFIG_FILE = "data/runtime_config.json"

DEFAULT_N_SIMULATIONS = 1000

RANDOM_SEED = 42


# =========================================================
# CHARGEMENT / SELECTION
# =========================================================

def normalize_name(name):
    return " ".join(name.strip().lower().split())

def load_runtime_config():
    path = Path(RUNTIME_CONFIG_FILE)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_players(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("players.json doit contenir une liste JSON de joueurs.")

    cleaned = []
    for i, player in enumerate(data, start=1):
        if not isinstance(player, dict):
            raise ValueError(f"Entrée invalide à l'index {i} dans players.json.")
        if "player" not in player or "points" not in player:
            raise ValueError(
                f"Le joueur à l'index {i} doit contenir au minimum 'player' et 'points'."
            )
        cleaned.append(player)

    return cleaned


def load_selected_names(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with path.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    if not names:
        raise ValueError("selection.txt est vide.")

    return names


def load_overrides(filepath):
    path = Path(filepath)
    if not path.exists():
        return {"global": {}, "players": {}}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("overrides.json doit contenir un objet JSON.")

    data.setdefault("global", {})
    data.setdefault("players", {})
    return data


def build_overrides_map(overrides):
    result = {}
    for name, config in overrides.get("players", {}).items():
        result[normalize_name(name)] = config
    return result


def select_players(all_players, selected_names):
    players_map = {}
    duplicates_in_source = []

    for player in all_players:
        key = normalize_name(player["player"])
        if key in players_map:
            duplicates_in_source.append(player["player"])
        else:
            players_map[key] = player

    if duplicates_in_source:
        raise ValueError(
            "Doublons détectés dans players.json : "
            + ", ".join(sorted(duplicates_in_source))
        )

    selected_players = []
    missing = []
    already_added = set()

    for name in selected_names:
        key = normalize_name(name)

        if key not in players_map:
            missing.append(name)
            continue

        real_name = players_map[key]["player"]
        if real_name not in already_added:
            selected_players.append(players_map[key])
            already_added.add(real_name)

    if missing:
        raise ValueError(
            "Joueurs introuvables dans players.json :\n- "
            + "\n- ".join(missing)
        )

    if len(selected_players) < 2:
        raise ValueError("Il faut au moins 2 joueurs sélectionnés.")

    return selected_players


# =========================================================
# ELO
# =========================================================

def compute_effective_elo(player, overrides_map):
    base_elo = float(player["points"])
    key = normalize_name(player["player"])
    cfg = overrides_map.get(key, {})

    if "manual_elo" in cfg:
        return float(cfg["manual_elo"])

    return base_elo


def build_player_elos(players, overrides):
    overrides_map = build_overrides_map(overrides)

    return {
        player["player"]: compute_effective_elo(player, overrides_map)
        for player in players
    }


def elo_win_probability(elo_a, elo_b, elo_divisor=400.0):
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / elo_divisor))


# =========================================================
# MATRICE DES DUELS
# =========================================================

def build_duel_matrix(player_elos, elo_divisor=400.0):
    players = list(player_elos.keys())
    rows = []

    for a in players:
        row = {"player": a}
        for b in players:
            if a == b:
                row[b] = None
            else:
                row[b] = elo_win_probability(player_elos[a], player_elos[b], elo_divisor)
        rows.append(row)

    return pd.DataFrame(rows)


# =========================================================
# EXPECTED POINTS (TOUS CONTRE TOUS)
# =========================================================

def compute_expected_points(player_elos, elo_divisor=400.0):
    players = list(player_elos.keys())
    total_matches = len(players) - 1

    rows = []
    for a in players:
        expected_wins = 0.0
        expected_points = 0.0

        for b in players:
            if a == b:
                continue

            p_win = elo_win_probability(player_elos[a], player_elos[b], elo_divisor)
            expected_wins += p_win
            expected_points += 2.0 * p_win

        rows.append({
            "player": a,
            "elo": player_elos[a],
            "matches": total_matches,
            "expected_wins": expected_wins,
            "expected_points": expected_points,
            "expected_points_per_match": expected_points / total_matches if total_matches > 0 else 0.0,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["expected_points", "elo"],
        ascending=[False, False]
    ).reset_index(drop=True)

    df.insert(0, "expected_rank", range(1, len(df) + 1))
    return df


# =========================================================
# SIMULATION ROUND-ROBIN
# =========================================================

def simulate_round_robin(player_elos, elo_divisor=400.0):
    players = list(player_elos.keys())

    points = {p: 0 for p in players}
    wins = {p: 0 for p in players}
    losses = {p: 0 for p in players}

    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            a = players[i]
            b = players[j]

            p_a = elo_win_probability(player_elos[a], player_elos[b], elo_divisor)
            r = random.random()

            if r < p_a:
                points[a] += 2
                wins[a] += 1
                losses[b] += 1
            else:
                points[b] += 2
                wins[b] += 1
                losses[a] += 1

    rows = []
    for p in players:
        rows.append({
            "player": p,
            "elo": player_elos[p],
            "points": points[p],
            "wins": wins[p],
            "losses": losses[p],
        })

    df = pd.DataFrame(rows)

    df = df.sort_values(
        ["points", "wins", "elo", "player"],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)

    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def round_robin_probability_matrix(player_elos, n_simulations=50000, elo_divisor=400.0):
    players = list(player_elos.keys())
    n = len(players)

    rank_counts = {p: [0] * n for p in players}
    total_points = {p: 0.0 for p in players}
    total_wins = {p: 0.0 for p in players}

    for _ in range(n_simulations):
        sim_df = simulate_round_robin(player_elos, elo_divisor)

        for _, row in sim_df.iterrows():
            player = row["player"]
            rank = int(row["rank"])
            points = float(row["points"])
            wins = float(row["wins"])

            rank_counts[player][rank - 1] += 1
            total_points[player] += points
            total_wins[player] += wins

    rows = []
    for p in players:
        row = {
            "player": p,
            "elo": player_elos[p],
            "sim_expected_points": total_points[p] / n_simulations,
            "sim_expected_wins": total_wins[p] / n_simulations,
        }

        for k in range(n):
            row[f"Top{k + 1}"] = rank_counts[p][k] / n_simulations

        rows.append(row)

    df = pd.DataFrame(rows)

    for k in [1, 2, 3, 4, 5, 8]:
        if k <= n:
            cols = [f"Top{i}" for i in range(1, k + 1)]
            df[f"Top<={k}"] = df[cols].sum(axis=1)

    df = df.sort_values(
        ["Top1", "sim_expected_points", "elo"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    return df


# =========================================================
# CONTROLE ELO
# =========================================================

def build_elo_control_df(selected_players, overrides):
    overrides_map = build_overrides_map(overrides)
    rows = []

    for player in selected_players:
        name = player["player"]
        original_elo = float(player["points"])
        cfg = overrides_map.get(normalize_name(name), {})
        manual_elo = cfg.get("manual_elo")
        effective_elo = float(manual_elo) if manual_elo is not None else original_elo

        rows.append({
            "player": name,
            "elo_original": original_elo,
            "manual_elo": manual_elo,
            "elo_effective": effective_elo,
            "manual_override": manual_elo is not None,
            "games": player.get("games"),
            "inactivity": player.get("inactivity"),
        })

    df = pd.DataFrame(rows)
    return df.sort_values(["elo_effective", "player"], ascending=[False, True]).reset_index(drop=True)


# =========================================================
# EXPORT EXCEL
# =========================================================

def autosize_columns(worksheet, dataframe, percent_cols=None, workbook=None):
    percent_cols = percent_cols or set()
    percent_format = workbook.add_format({"num_format": "0.00%"}) if workbook else None
    number_format = workbook.add_format({"num_format": "0.00"}) if workbook else None

    for col_idx, col_name in enumerate(dataframe.columns):
        max_len = max(
            len(str(col_name)),
            max((len(str(v)) for v in dataframe[col_name] if v is not None), default=0)
        ) + 2

        if workbook and col_name in percent_cols:
            worksheet.set_column(col_idx, col_idx, max_len, percent_format)
        elif workbook and pd.api.types.is_float_dtype(dataframe[col_name]):
            worksheet.set_column(col_idx, col_idx, max_len, number_format)
        else:
            worksheet.set_column(col_idx, col_idx, max_len)


def export_to_excel(selected_players, duel_df, expected_df, simulation_df, elo_control_df, output_file):
    players_df = pd.DataFrame(
        [
            {
                "player": p["player"],
                "elo_source": float(p["points"]),
                "games": p.get("games"),
                "inactivity": p.get("inactivity"),
            }
            for p in selected_players
        ]
    ).sort_values(["elo_source", "player"], ascending=[False, True]).reset_index(drop=True)

    duel_percent_cols = set(duel_df.columns) - {"player"}
    simulation_percent_cols = {c for c in simulation_df.columns if c.startswith("Top")}

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        players_df.to_excel(writer, sheet_name="joueurs", index=False)
        elo_control_df.to_excel(writer, sheet_name="elo_control", index=False)
        duel_df.to_excel(writer, sheet_name="duels", index=False)
        expected_df.to_excel(writer, sheet_name="expected_points", index=False)
        simulation_df.to_excel(writer, sheet_name="simulation_rr", index=False)

        workbook = writer.book

        autosize_columns(writer.sheets["joueurs"], players_df, workbook=workbook)
        autosize_columns(writer.sheets["elo_control"], elo_control_df, workbook=workbook)
        autosize_columns(
            writer.sheets["duels"],
            duel_df,
            percent_cols=duel_percent_cols,
            workbook=workbook
        )
        autosize_columns(
            writer.sheets["expected_points"],
            expected_df,
            workbook=workbook
        )
        autosize_columns(
            writer.sheets["simulation_rr"],
            simulation_df,
            percent_cols=simulation_percent_cols,
            workbook=workbook
        )


# =========================================================
# MAIN
# =========================================================

def main():
    random.seed(RANDOM_SEED)

    runtime_config = load_runtime_config()

    n_simulations = int(
        runtime_config.get("master_n_simulations", DEFAULT_N_SIMULATIONS)
    )

    print(f"Simulations : {n_simulations}")

    print("Chargement des joueurs...")
    all_players = load_players(PLAYERS_FILE)

    print("Chargement de la sélection...")
    selected_names = load_selected_names(SELECTION_FILE)

    print("Chargement des overrides...")
    overrides = load_overrides(OVERRIDES_FILE)
    elo_divisor = float(overrides.get("global", {}).get("elo_divisor", 400.0))

    print("Sélection des joueurs du tournoi...")
    selected_players = select_players(all_players, selected_names)

    print(f"{len(selected_players)} joueurs retenus :")
    for p in selected_players:
        print(f" - {p['player']} ({p['points']} Elo source)")

    print("Construction des Elos effectifs...")
    player_elos = build_player_elos(selected_players, overrides)

    print("Calcul de la matrice des duels...")
    duel_df = build_duel_matrix(player_elos, elo_divisor)

    print("Calcul des expected points...")
    expected_df = compute_expected_points(player_elos, elo_divisor)

    print(f"Simulation du tournoi tous-contre-tous ({n_simulations} simulations)...")
    simulation_df = round_robin_probability_matrix(
        player_elos,
        n_simulations=n_simulations,
        elo_divisor=elo_divisor
    )

    print("Construction du contrôle Elo...")
    elo_control_df = build_elo_control_df(selected_players, overrides)

    print("Export Excel...")
    export_to_excel(
        selected_players=selected_players,
        duel_df=duel_df,
        expected_df=expected_df,
        simulation_df=simulation_df,
        elo_control_df=elo_control_df,
        output_file=OUTPUT_FILE
    )
    post_df = simulation_df.copy()

    elo_map = {
        row["player"]: row["elo_effective"]
        for _, row in elo_control_df.iterrows()
    }

    expected_points_map = {
        row["player"]: row["expected_points"]
        for _, row in expected_df.iterrows()
    }

    post_df["elo_effective"] = post_df["player"].map(elo_map)
    post_df["expected_points"] = post_df["player"].map(expected_points_map)

    cols = ["player", "elo_effective", "expected_points"]
    for c in ["Top1", "Top2", "Top3", "Top4", "Top5", "Top8", "Top<=3", "Top<=5", "Top<=8"]:
        if c in post_df.columns:
            cols.append(c)

    post_df = post_df[cols].copy()
    post_df.insert(0, "rank", range(1, len(post_df) + 1))
    post_df.to_csv(POST_DATA_FILE, index=False, encoding="utf-8")

    print(f"Terminé. Fichier généré : {OUTPUT_FILE}")

    


if __name__ == "__main__":
    main()