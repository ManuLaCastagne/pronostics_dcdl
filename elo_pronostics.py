import json
from pathlib import Path

import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PLAYERS_FILE = "data/players.json"
SELECTION_FILE = "data/selection.txt"
OVERRIDES_FILE = "data/overrides.json"

OUTPUT_EXCEL = "outputs/excel/pronostic_elo.xlsx"
OUTPUT_CSV = "outputs/csv/pronostic_elo.csv"
POST_DATA_FILE = "outputs/csv/pronostic_elo_post_data.csv"


# =========================================================
# OUTILS
# =========================================================

def normalize_name(name):
    return " ".join(str(name).strip().lower().split())


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
            "Joueurs introuvables dans players.json :\n- " + "\n- ".join(missing)
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


def elo_to_force(elo, divisor=400.0):
    return 10 ** (float(elo) / float(divisor))


def compute_tournament_win_probabilities(selected_players, overrides, divisor=400.0):
    overrides_map = build_overrides_map(overrides)

    rows = []
    total_force = 0.0

    for player in selected_players:
        name = player["player"]
        elo_source = float(player["points"])
        elo_effective = compute_effective_elo(player, overrides_map)
        force = elo_to_force(elo_effective, divisor)

        total_force += force

        rows.append({
            "player": name,
            "elo_source": elo_source,
            "elo_effective": elo_effective,
            "games": player.get("games"),
            "inactivity": player.get("inactivity"),
            "force": force,
        })

    for row in rows:
        row["win_probability"] = row["force"] / total_force if total_force > 0 else 0.0

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["win_probability", "elo_effective", "player"],
        ascending=[False, False, True]
    ).reset_index(drop=True)

    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def build_post_data(df):
    post_df = df.copy()

    # harmonisation avec le reste de ta pipeline
    post_df["Top1"] = post_df["win_probability"]

    cols = [
        "rank",
        "player",
        "elo_effective",
        "win_probability",
        "Top1",
    ]

    available_cols = [c for c in cols if c in post_df.columns]
    post_df = post_df[available_cols].copy()

    return post_df


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


def export_results(df, post_df, output_excel, output_csv, post_data_file):
    Path(output_excel).parent.mkdir(parents=True, exist_ok=True)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(post_data_file).parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_csv, index=False, encoding="utf-8")
    post_df.to_csv(post_data_file, index=False, encoding="utf-8")

    with pd.ExcelWriter(output_excel, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="pronostic_elo", index=False)
        post_df.to_excel(writer, sheet_name="post_data", index=False)

        workbook = writer.book
        autosize_columns(
            writer.sheets["pronostic_elo"],
            df,
            percent_cols={"win_probability"},
            workbook=workbook
        )
        autosize_columns(
            writer.sheets["post_data"],
            post_df,
            percent_cols={"win_probability", "Top1"},
            workbook=workbook
        )


# =========================================================
# MAIN
# =========================================================

def main():
    print("Chargement des joueurs...")
    all_players = load_players(PLAYERS_FILE)

    print("Chargement de la sélection...")
    selected_names = load_selected_names(SELECTION_FILE)

    print("Chargement des overrides...")
    overrides = load_overrides(OVERRIDES_FILE)

    divisor = float(overrides.get("global", {}).get("elo_divisor", ELO_DIVISOR))

    print("Sélection des joueurs...")
    selected_players = select_players(all_players, selected_names)

    print(f"{len(selected_players)} joueurs retenus.")

    print("Calcul des probabilités basées uniquement sur l'Elo...")
    df = compute_tournament_win_probabilities(
        selected_players=selected_players,
        overrides=overrides,
        divisor=divisor
    )

    print("Construction du post_data...")
    post_df = build_post_data(df)

    print("Export des résultats...")
    export_results(
        df=df,
        post_df=post_df,
        output_excel=OUTPUT_EXCEL,
        output_csv=OUTPUT_CSV,
        post_data_file=POST_DATA_FILE
    )

    print(f"Terminé. Excel     : {OUTPUT_EXCEL}")
    print(f"Terminé. CSV       : {OUTPUT_CSV}")
    print(f"Terminé. Post data : {POST_DATA_FILE}")


if __name__ == "__main__":
    main()