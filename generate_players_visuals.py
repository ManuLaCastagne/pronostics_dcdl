import json
import csv
import unicodedata
import re
from pathlib import Path


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

PLAYERS_FILE = BASE_DIR / "data" / "players.json"
OUTPUT_FILE = BASE_DIR / "data" / "players_visuals.csv"

DEFAULT_FLAG = "assets/flags/fr.png"
DEFAULT_CLUB_LOGO = "assets/clubs/default.png"
PHOTO_DIR = "assets/players"

# Palette stable et propre
COLOR_PALETTE = [
    "#D4AF37",  # or
    "#2F6BFF",  # bleu
    "#E63946",  # rouge
    "#FFB703",  # jaune
    "#3A86FF",  # bleu clair
    "#8338EC",  # violet
    "#06D6A0",  # vert menthe
    "#FB5607",  # orange
    "#118AB2",  # bleu pétrole
    "#EF476F",  # rose rouge
    "#8D99AE",  # gris bleuté
    "#43AA8B",  # vert
]


# =========================================================
# OUTILS
# =========================================================

def slugify_name(name: str) -> str:
    """
    Transforme 'LECLÈRE Christophe' -> 'leclere-christophe'
    """
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text


def load_players(filepath: Path) -> list:
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("players.json doit contenir une liste JSON de joueurs.")

    for i, player in enumerate(data, start=1):
        if not isinstance(player, dict):
            raise ValueError(f"Entrée invalide à l'index {i} dans players.json.")
        if "player" not in player:
            raise ValueError(f"Le joueur à l'index {i} ne contient pas la clé 'player'.")

    return data


def choose_theme_color(player_name: str) -> str:
    """
    Attribue une couleur stable à partir du nom.
    """
    index = sum(ord(c) for c in player_name) % len(COLOR_PALETTE)
    return COLOR_PALETTE[index]


def build_visual_row(player_name: str) -> dict:
    slug = slugify_name(player_name)

    return {
        "player": player_name,
        "display_name": player_name,
        "photo": f"{PHOTO_DIR}/{slug}.png",
        "flag": DEFAULT_FLAG,
        "club_logo": DEFAULT_CLUB_LOGO,
        "theme_color": choose_theme_color(player_name),
    }


def write_players_visuals(rows: list, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["player", "display_name", "photo", "flag", "club_logo", "theme_color"]

    with filepath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# =========================================================
# MAIN
# =========================================================

def main():
    players = load_players(PLAYERS_FILE)

    seen = set()
    rows = []

    for player in players:
        player_name = str(player["player"]).strip()

        if not player_name:
            continue

        if player_name in seen:
            continue

        seen.add(player_name)
        rows.append(build_visual_row(player_name))

    rows = sorted(rows, key=lambda r: r["player"])

    write_players_visuals(rows, OUTPUT_FILE)

    print(f"OK : {OUTPUT_FILE}")
    print(f"{len(rows)} joueurs exportés.")


if __name__ == "__main__":
    main()