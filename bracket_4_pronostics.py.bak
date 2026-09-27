import json
from pathlib import Path

import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PLAYERS_FILE = "data/players.json"
SELECTION_FILE = "data/bracket_selection.txt"
OVERRIDES_FILE = "data/overrides.json"
OUTPUT_FILE = "outputs/excel/bracket_pronostics.xlsx"
POST_DATA_FILE = "outputs/csv/bracket_post_data.csv"

# Ordres standards de bracket selon le nombre de joueurs
BRACKET_SEED_ORDERS = {
    4: [1, 4, 2, 3],                  # SF
    8: [1, 8, 4, 5, 2, 7, 3, 6],      # QF
}


# =========================================================
# OUTILS
# =========================================================

def normalize_name(name):
    return " ".join(name.strip().lower().split())


def load_players(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("players.json doit contenir une liste JSON de joueurs.")

    for i, player in enumerate(data, start=1):
        if not isinstance(player, dict):
            raise ValueError(f"Entrée invalide à l'index {i} dans players.json.")
        if "player" not in player or "points" not in player:
            raise ValueError(
                f"Le joueur à l'index {i} doit contenir au minimum 'player' et 'points'."
            )

    return data


def load_selected_names(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with path.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    if len(names) not in BRACKET_SEED_ORDERS:
        allowed = ", ".join(str(k) for k in sorted(BRACKET_SEED_ORDERS))
        raise ValueError(
            f"bracket_selection.txt doit contenir exactement {allowed} joueurs."
        )

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


def select_players_by_seed(all_players, selected_names):
    players_map = {}
    duplicates = []

    for player in all_players:
        key = normalize_name(player["player"])
        if key in players_map:
            duplicates.append(player["player"])
        else:
            players_map[key] = player

    if duplicates:
        raise ValueError(
            "Doublons détectés dans players.json : " + ", ".join(sorted(duplicates))
        )

    selected_players = []
    missing = []

    for seed, name in enumerate(selected_names, start=1):
        key = normalize_name(name)
        if key not in players_map:
            missing.append(name)
            continue

        player = dict(players_map[key])
        player["seed"] = seed
        selected_players.append(player)

    if missing:
        raise ValueError(
            "Joueurs introuvables dans players.json :\n- " + "\n- ".join(missing)
        )

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
# BRACKET EXACT
# =========================================================

def reorder_players_for_bracket(seed_players):
    bracket_size = len(seed_players)
    order = BRACKET_SEED_ORDERS[bracket_size]
    by_seed = {p["seed"]: p for p in seed_players}
    return [by_seed[s] for s in order]


def compute_subtree_distribution(players_in_subtree, player_elos, elo_divisor=400.0):
    n = len(players_in_subtree)

    if n == 1:
        return {players_in_subtree[0]: 1.0}

    mid = n // 2
    left = players_in_subtree[:mid]
    right = players_in_subtree[mid:]

    left_dist = compute_subtree_distribution(left, player_elos, elo_divisor)
    right_dist = compute_subtree_distribution(right, player_elos, elo_divisor)

    result = {}

    for a, p_a_reach in left_dist.items():
        total = 0.0
        for b, p_b_reach in right_dist.items():
            total += p_b_reach * elo_win_probability(
                player_elos[a], player_elos[b], elo_divisor
            )
        result[a] = p_a_reach * total

    for b, p_b_reach in right_dist.items():
        total = 0.0
        for a, p_a_reach in left_dist.items():
            total += p_a_reach * elo_win_probability(
                player_elos[b], player_elos[a], elo_divisor
            )
        result[b] = p_b_reach * total

    return result


def compute_round_reach_probabilities(bracket_players, player_elos, elo_divisor=400.0):
    names = [p["player"] for p in bracket_players]
    bracket_size = len(names)

    probs = {name: {"win": 0.0} for name in names}

    if bracket_size == 4:
        for name in names:
            probs[name]["Top4"] = 1.0
            probs[name]["Top2"] = 0.0

        # demi-finales -> finale
        sf_groups = [names[i:i + 2] for i in range(0, 4, 2)]
        for group in sf_groups:
            dist = compute_subtree_distribution(group, player_elos, elo_divisor)
            for player, p in dist.items():
                probs[player]["Top2"] = p

        # finale -> champion
        final_dist = compute_subtree_distribution(names, player_elos, elo_divisor)
        for player, p in final_dist.items():
            probs[player]["win"] = p

    elif bracket_size == 8:
        for name in names:
            probs[name]["Top8"] = 1.0
            probs[name]["Top4"] = 0.0
            probs[name]["Top2"] = 0.0

        # quarts -> demies
        qf_groups = [names[i:i + 2] for i in range(0, 8, 2)]
        for group in qf_groups:
            dist = compute_subtree_distribution(group, player_elos, elo_divisor)
            for player, p in dist.items():
                probs[player]["Top4"] = p

        # demies -> finale
        sf_groups = [names[i:i + 4] for i in range(0, 8, 4)]
        for group in sf_groups:
            dist = compute_subtree_distribution(group, player_elos, elo_divisor)
            for player, p in dist.items():
                probs[player]["Top2"] = p

        # finale -> champion
        final_dist = compute_subtree_distribution(names, player_elos, elo_divisor)
        for player, p in final_dist.items():
            probs[player]["win"] = p

    else:
        raise ValueError(f"Format bracket non géré : {bracket_size}")

    return probs


def build_bracket_probability_table(bracket_players, player_elos, elo_divisor=400.0):
    probs = compute_round_reach_probabilities(bracket_players, player_elos, elo_divisor)
    bracket_size = len(bracket_players)

    rows = []
    for p in bracket_players:
        name = p["player"]
        seed = p["seed"]
        elo = player_elos[name]

        row = {
            "seed": seed,
            "player": name,
            "elo": elo,
            "Top1": probs[name]["win"],
            "Top2": probs[name]["Top2"],
            "champion": probs[name]["win"],
        }

        if bracket_size == 4:
            row["Top4"] = 1.0
            row["elim_SF"] = 1.0 - probs[name]["Top2"]
            row["finalist_lost"] = probs[name]["Top2"] - probs[name]["win"]

        elif bracket_size == 8:
            row["Top4"] = probs[name]["Top4"]
            row["Top8"] = 1.0
            row["elim_QF"] = 1.0 - probs[name]["Top4"]
            row["elim_SF"] = probs[name]["Top4"] - probs[name]["Top2"]
            row["finalist_lost"] = probs[name]["Top2"] - probs[name]["win"]

        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values(["Top1", "elo"], ascending=[False, False]).reset_index(drop=True)
    return df


def build_bracket_matches_view(bracket_players):
    names = [p["player"] for p in bracket_players]
    seeds = [p["seed"] for p in bracket_players]
    bracket_size = len(bracket_players)

    rows = []

    if bracket_size == 4:
        for i in range(0, 4, 2):
            rows.append({
                "round": "SF",
                "match": (i // 2) + 1,
                "seed_a": seeds[i],
                "player_a": names[i],
                "seed_b": seeds[i + 1],
                "player_b": names[i + 1],
            })

    elif bracket_size == 8:
        for i in range(0, 8, 2):
            rows.append({
                "round": "QF",
                "match": (i // 2) + 1,
                "seed_a": seeds[i],
                "player_a": names[i],
                "seed_b": seeds[i + 1],
                "player_b": names[i + 1],
            })

    else:
        raise ValueError(f"Format bracket non géré : {bracket_size}")

    return pd.DataFrame(rows)


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
            "seed": player["seed"],
            "player": name,
            "elo_original": original_elo,
            "manual_elo": manual_elo,
            "elo_effective": effective_elo,
            "manual_override": manual_elo is not None,
            "games": player.get("games"),
            "inactivity": player.get("inactivity"),
        })

    df = pd.DataFrame(rows)
    return df.sort_values("seed").reset_index(drop=True)


# =========================================================
# EXPORT
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


def export_to_excel(players_df, elo_control_df, bracket_df, matches_df, duel_df, output_file):
    percent_cols_bracket = {
        "Top1", "Top2", "Top4", "Top8",
        "elim_QF", "elim_SF", "finalist_lost", "champion"
    }
    percent_cols_duels = set(duel_df.columns) - {"player"}

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        players_df.to_excel(writer, sheet_name="players", index=False)
        elo_control_df.to_excel(writer, sheet_name="elo_control", index=False)
        matches_df.to_excel(writer, sheet_name="bracket", index=False)
        bracket_df.to_excel(writer, sheet_name="probabilities", index=False)
        duel_df.to_excel(writer, sheet_name="duels", index=False)

        workbook = writer.book
        autosize_columns(writer.sheets["players"], players_df, workbook=workbook)
        autosize_columns(writer.sheets["elo_control"], elo_control_df, workbook=workbook)
        autosize_columns(writer.sheets["bracket"], matches_df, workbook=workbook)
        autosize_columns(
            writer.sheets["probabilities"],
            bracket_df,
            percent_cols=percent_cols_bracket,
            workbook=workbook,
        )
        autosize_columns(
            writer.sheets["duels"],
            duel_df,
            percent_cols=percent_cols_duels,
            workbook=workbook,
        )


# =========================================================
# MAIN
# =========================================================

def main():
    print("Chargement des joueurs...")
    all_players = load_players(PLAYERS_FILE)

    print("Chargement du bracket...")
    selected_names = load_selected_names(SELECTION_FILE)
    bracket_size = len(selected_names)

    print("Chargement des overrides...")
    overrides = load_overrides(OVERRIDES_FILE)
    elo_divisor = float(overrides.get("global", {}).get("elo_divisor", 400.0))

    print(f"Sélection des {bracket_size} joueurs...")
    selected_players = select_players_by_seed(all_players, selected_names)

    print("Réorganisation dans le tableau standard...")
    bracket_players = reorder_players_for_bracket(selected_players)

    print("Joueurs du bracket :")
    for p in bracket_players:
        print(f"Seed {p['seed']:>2} - {p['player']} ({p['points']} Elo source)")

    print("Construction des Elos effectifs...")
    player_elos = build_player_elos(bracket_players, overrides)

    print("Calcul de la matrice des duels...")
    duel_df = build_duel_matrix(player_elos, elo_divisor)

    print("Calcul exact des probabilités du bracket...")
    bracket_df = build_bracket_probability_table(bracket_players, player_elos, elo_divisor)

    print("Préparation de la vue du tableau...")
    matches_df = build_bracket_matches_view(bracket_players)

    print("Construction du contrôle Elo...")
    elo_control_df = build_elo_control_df(selected_players, overrides)

    players_df = pd.DataFrame(
        [
            {
                "seed": p["seed"],
                "player": p["player"],
                "elo_source": float(p["points"]),
                "games": p.get("games"),
                "inactivity": p.get("inactivity"),
            }
            for p in selected_players
        ]
    ).sort_values("seed").reset_index(drop=True)

    print("Export Excel...")
    export_to_excel(players_df, elo_control_df, bracket_df, matches_df, duel_df, OUTPUT_FILE)

    Path(POST_DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    post_df = bracket_df.copy()
    post_df.to_csv(POST_DATA_FILE, index=False, encoding="utf-8")

    print(f"Terminé. Fichier généré : {OUTPUT_FILE}")
    print(f"CSV post généré : {POST_DATA_FILE}")


if __name__ == "__main__":
    main()