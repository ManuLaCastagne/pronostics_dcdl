import csv
import json
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

PLAYERS_FILE = BASE_DIR / "data" / "players.json"
VISUALS_FILE = BASE_DIR / "data" / "players_visuals.csv"
CLUBS_FILE = BASE_DIR / "data" / "player_clubs_regions.tsv"

DEFAULT_FLAG = "assets/flags/fr.png"
DEFAULT_PHOTO_DIR = "assets/players"
DEFAULT_CLUB_LOGO = "assets/clubs/default.png"
DEFAULT_COLOR = "#444444"

REGION_COLORS = {
    "ARA": "#1D4ED8",
    "Belgique": "#F59E0B",
    "Est": "#7C3AED",
    "Grand Ouest": "#059669",
    "Ouest": "#0F766E",
    "HDF": "#DC2626",
    "IDF": "#111827",
    "Normandie": "#2563EB",
    "Occitanie": "#EA580C",
    "PACA": "#DB2777",
    "Suisse": "#B91C1C",
    "ACL": "#6B7280",
    "": DEFAULT_COLOR,
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text


def normalize_spaces(text: str) -> str:
    return " ".join(str(text).strip().split())


def normalize_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", normalize_spaces(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower()


def canonical_player_key(full_name: str) -> str:
    return normalize_name(full_name)


def canonical_split_key(last_name: str, first_name: str) -> str:
    return normalize_name(f"{last_name} {first_name}")


def load_players(filepath: Path) -> list:
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")
    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("players.json doit contenir une liste JSON.")
    return data


def load_existing_visuals(filepath: Path) -> dict:
    if not filepath.exists():
        return {}

    with filepath.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    result = {}
    for row in rows:
        player = row.get("player", "").strip()
        if player:
            result[player] = row
    return result


def load_clubs_regions(filepath: Path) -> dict:
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    text = filepath.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Fichier vide : {filepath}")

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    header = lines[0].strip().lower()

    rows = []

    # Cas 1 : TSV standard
    if "\t" in header:
        reader = csv.DictReader(lines, delimiter="\t")
        rows = list(reader)

    # Cas 2 : CSV séparé par ;
    elif ";" in header:
        reader = csv.DictReader(lines, delimiter=";")
        rows = list(reader)

    # Cas 3 : pas d'en-tête exploitable, on suppose 4 colonnes en séparant
    # sur 2 espaces ou plus
    else:
        data_lines = lines

        if "nom" in header and "prenom" in header and "club" in header and "region" in header:
            data_lines = lines[1:]

        parsed = []
        for line in data_lines:
            parts = re.split(r"\s{2,}|\t", line.strip())
            parts = [p.strip() for p in parts]

            if len(parts) == 4:
                nom, prenom, club, region = parts
            else:
                tokens = line.strip().split()
                if len(tokens) < 3:
                    continue
                region = tokens[-1]
                club = tokens[-2] if len(tokens) >= 4 else ""
                nom = tokens[0]
                prenom = " ".join(tokens[1:-2]) if len(tokens) > 3 else tokens[1]

            parsed.append({
                "nom": nom,
                "prenom": prenom,
                "club": club,
                "region": region,
            })

        rows = parsed

    if not rows:
        raise ValueError(f"Aucune ligne exploitable trouvée dans {filepath.name}")

    normalized_rows = []
    for row in rows:
        normalized_row = {str(k).strip().lower(): (v if v is not None else "") for k, v in row.items()}
        normalized_rows.append(normalized_row)

    required = {"nom", "prenom", "club", "region"}
    first_keys = set(normalized_rows[0].keys())
    missing = required - first_keys
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {filepath.name} : {sorted(missing)} ; colonnes trouvées : {sorted(first_keys)}"
        )

    mapping = {}
    duplicates = []

    for row in normalized_rows:
        nom = normalize_spaces(row.get("nom", ""))
        prenom = normalize_spaces(row.get("prenom", ""))
        club = normalize_spaces(row.get("club", ""))
        region = normalize_spaces(row.get("region", ""))

        if not nom or not prenom:
            continue

        key = canonical_split_key(nom, prenom)
        if key in mapping:
            duplicates.append(f"{nom} {prenom}")

        mapping[key] = {
            "club": club,
            "region": region,
        }

    if duplicates:
        print("Attention, doublons dans le fichier clubs/régions :")
        for d in sorted(set(duplicates)):
            print(" -", d)

    return mapping


def build_photo_path(player_name: str) -> str:
    return f"{DEFAULT_PHOTO_DIR}/{slugify(player_name)}.png"


def build_club_logo_path(club: str) -> str:
    club = normalize_spaces(club)
    if not club:
        return DEFAULT_CLUB_LOGO
    return f"assets/clubs/{slugify(club)}.png"


def build_flag_path(region: str) -> str:
    region = normalize_spaces(region)
    if region == "Belgique":
        return "assets/flags/be.png"
    if region == "Suisse":
        return "assets/flags/ch.png"
    return DEFAULT_FLAG


def build_theme_color(region: str) -> str:
    return REGION_COLORS.get(normalize_spaces(region), DEFAULT_COLOR)


def build_row(player_name: str, existing_row: dict, clubs_map: dict) -> dict:
    key = canonical_player_key(player_name)
    ref = clubs_map.get(key, {})

    club = ref.get("club", "")
    region = ref.get("region", "")

    default_row = {
        "player": player_name,
        "display_name": player_name,
        "photo": build_photo_path(player_name),
        "flag": build_flag_path(region),
        "club_logo": build_club_logo_path(club),
        "club": club,
        "theme_color": build_theme_color(region),
    }

    # On conserve les champs éditables à la main si déjà présents
    if existing_row:
        default_row["display_name"] = existing_row.get("display_name") or player_name
        default_row["photo"] = existing_row.get("photo") or build_photo_path(player_name)

        # si club est déjà rempli dans le CSV existant, on le garde
        existing_club = normalize_spaces(existing_row.get("club", ""))
        if existing_club:
            default_row["club"] = existing_club
            default_row["club_logo"] = build_club_logo_path(existing_club)

    return default_row


def write_visuals(rows: list, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["player", "display_name", "photo", "flag", "club_logo", "club", "theme_color"]

    with filepath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    players = load_players(PLAYERS_FILE)
    existing_visuals = load_existing_visuals(VISUALS_FILE)
    clubs_map = load_clubs_regions(CLUBS_FILE)

    seen = set()
    rows = []
    missing_from_tsv = []

    for player in players:
        player_name = normalize_spaces(player.get("player", ""))
        if not player_name or player_name in seen:
            continue
        seen.add(player_name)

        if canonical_player_key(player_name) not in clubs_map:
            missing_from_tsv.append(player_name)

        row = build_row(
            player_name=player_name,
            existing_row=existing_visuals.get(player_name, {}),
            clubs_map=clubs_map,
        )
        rows.append(row)

    rows.sort(key=lambda r: r["player"])
    write_visuals(rows, VISUALS_FILE)

    print(f"OK : {VISUALS_FILE}")
    print(f"{len(rows)} joueurs écrits.")

    if missing_from_tsv:
        print("\nJoueurs sans club/région trouvés dans le TSV :")
        for name in sorted(missing_from_tsv)[:100]:
            print(" -", name)
        if len(missing_from_tsv) > 100:
            print(f"... et {len(missing_from_tsv) - 100} autres")


if __name__ == "__main__":
    main()