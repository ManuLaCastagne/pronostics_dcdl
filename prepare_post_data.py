import pandas as pd
from pathlib import Path


# =========================================================
# CONFIG
# =========================================================

INPUT_MASTER_FILE = "outputs/csv/master_post_data.csv"
INPUT_BRACKET_FILE = "outputs/csv/bracket_post_data.csv"
INPUT_ELO_FILE = "outputs/csv/pronostic_elo_post_data.csv"

VISUALS_FILE = "data/players_visuals.csv"

OUTPUT_MASTER_READY = "outputs/csv/master_post_ready.csv"
OUTPUT_BRACKET_READY = "outputs/csv/bracket_post_ready.csv"
OUTPUT_ELO_READY = "outputs/csv/pronostic_elo_post_ready.csv"

DEFAULT_PHOTO = "assets/players/default.png"
DEFAULT_FLAG = "assets/flags/default.png"
DEFAULT_CLUB = "assets/clubs/default.png"
DEFAULT_COLOR = "#444444"
DEFAULT_CLUB_NAME = ""


# =========================================================
# OUTILS
# =========================================================

def normalize_name(name):
    return " ".join(str(name).strip().lower().split())


def ensure_parent_dir(filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)


def load_csv(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")
    return pd.read_csv(path)


def prepare_visuals_df(visuals_df):
    required_cols = ["player", "display_name", "photo", "flag", "club_logo", "theme_color"]
    for col in required_cols:
        if col not in visuals_df.columns:
            raise ValueError(f"Colonne manquante dans players_visuals.csv : {col}")

    visuals_df = visuals_df.copy()

    # colonne optionnelle mais utile
    if "club" not in visuals_df.columns:
        visuals_df["club"] = DEFAULT_CLUB_NAME

    visuals_df["player_key"] = visuals_df["player"].apply(normalize_name)
    return visuals_df


def merge_post_data(post_df, visuals_df):
    post_df = post_df.copy()

    if "player" not in post_df.columns:
        raise ValueError("Le fichier post_data doit contenir une colonne 'player'.")

    post_df["player_key"] = post_df["player"].apply(normalize_name)

    merged = post_df.merge(
        visuals_df.drop(columns=["player"]),
        on="player_key",
        how="left"
    )

    merged["display_name"] = merged["display_name"].fillna(merged["player"])
    merged["photo"] = merged["photo"].fillna(DEFAULT_PHOTO)
    merged["flag"] = merged["flag"].fillna(DEFAULT_FLAG)
    merged["club_logo"] = merged["club_logo"].fillna(DEFAULT_CLUB)
    merged["theme_color"] = merged["theme_color"].fillna(DEFAULT_COLOR)

    if "club" not in merged.columns:
        merged["club"] = DEFAULT_CLUB_NAME
    merged["club"] = merged["club"].fillna(DEFAULT_CLUB_NAME)

    merged = merged.drop(columns=["player_key"])
    return merged


def process_one(input_file, output_file, visuals_df, label):
    input_path = Path(input_file)
    if not input_path.exists():
        return

    df = load_csv(input_file)
    ready_df = merge_post_data(df, visuals_df)

    ensure_parent_dir(output_file)
    ready_df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"OK : {output_file} ({label})")


# =========================================================
# MAIN
# =========================================================

def main():
    visuals_df = load_csv(VISUALS_FILE)
    visuals_df = prepare_visuals_df(visuals_df)

    process_one(
        INPUT_MASTER_FILE,
        OUTPUT_MASTER_READY,
        visuals_df,
        "master"
    )

    process_one(
        INPUT_BRACKET_FILE,
        OUTPUT_BRACKET_READY,
        visuals_df,
        "bracket"
    )

    process_one(
        INPUT_ELO_FILE,
        OUTPUT_ELO_READY,
        visuals_df,
        "elo"
    )


if __name__ == "__main__":
    main()