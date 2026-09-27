import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

PLAYERS_FILE = BASE_DIR / "data" / "players.json"

RUNTIME_CONFIG_FILE = BASE_DIR / "data" / "runtime_config.json"

OVERRIDES_FILE = BASE_DIR / "data" / "overrides.json"

MASTER_SELECTION_FILE = BASE_DIR / "data" / "master_selection.txt"
ELO_SELECTION_FILE = BASE_DIR / "data" / "selection.txt"
BRACKET_SELECTION_FILE = BASE_DIR / "data" / "bracket_selection.txt"

MASTER_IMAGE = BASE_DIR / "outputs" / "images" / "instagram_top5_master.png"
BRACKET_IMAGE = BASE_DIR / "outputs" / "images" / "instagram_results_bracket.png"

SCRIPT_MASTER = "master_pronostics.py"
SCRIPT_ELO = "elo_pronostics.py"
SCRIPT_PREPARE = "prepare_post_data.py"
SCRIPT_IMAGE_MASTER = "generate_instagram_post_master.py"
SCRIPT_IMAGE_BRACKET = "generate_instagram_post_bracket.py"

CLAX_ELO_URL = "https://dcdl-laxou.fr/ts/elo/#/global"

BRACKET_SCRIPTS = {
    2: "match_pronostics.py",
    4: "bracket_4_pronostics.py",
    8: "bracket_8_pronostics.py",
    16: "bracket_16_pronostics.py",
}


# =========================================================
# STREAMLIT
# =========================================================

st.set_page_config(
    page_title="Elo-Clax Pronostics",
    page_icon="🏆",
    layout="wide"
)


# =========================================================
# OUTILS
# =========================================================

def load_json_file(path: Path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Erreur lecture JSON : {path}")
        st.exception(e)
        return default


def save_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_runtime_config():
    return load_json_file(
        RUNTIME_CONFIG_FILE,
        {
            "master_n_simulations": 1000
        }
    )


def save_runtime_config(data):
    save_json_file(RUNTIME_CONFIG_FILE, data)


def load_overrides():
    data = load_json_file(OVERRIDES_FILE, {"global": {}, "players": {}})
    data.setdefault("global", {})
    data.setdefault("players", {})
    return data


def save_overrides(overrides):
    save_json_file(OVERRIDES_FILE, overrides)


def normalize_player_name(name: str) -> str:
    return " ".join(str(name).strip().split())


def parse_int(value, default=0):
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (ValueError, TypeError):
        return default


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_players_from_clax():
    """
    Récupère automatiquement le classement Elo global depuis CLAX.

    Le résultat est mis en cache Streamlit pendant 1 heure.
    """

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(CLAX_ELO_URL)

        WebDriverWait(driver, 20).until(
            lambda d: len(d.find_elements(By.TAG_NAME, "table")) > 0
        )

        html = driver.page_source

    finally:
        driver.quit()

    tables = pd.read_html(StringIO(html))

    if not tables:
        raise RuntimeError("Aucun tableau trouvé sur la page Elo CLAX.")

    elo_df = None

    for table in tables:
        if isinstance(table.columns, pd.MultiIndex):
            table.columns = [
                " ".join(
                    str(part)
                    for part in col
                    if str(part).lower() != "nan"
                ).strip()
                for col in table.columns
            ]

        columns = [
            str(col).strip().lower()
            for col in table.columns
        ]

        has_player_column = any(
            any(keyword in col for keyword in ["joueur", "nom", "player"])
            for col in columns
        )

        has_elo_column = any(
            any(keyword in col for keyword in ["elo", "points"])
            for col in columns
        )

        if has_player_column and has_elo_column:
            elo_df = table.copy()
            break

    if elo_df is None:
        raise RuntimeError(
            "Impossible d'identifier automatiquement le tableau Elo CLAX."
        )

    def find_column(keywords):
        for column in elo_df.columns:
            normalized = str(column).strip().lower()

            if any(keyword in normalized for keyword in keywords):
                return column

        return None

    player_col = find_column(["joueur", "nom", "player"])
    elo_col = find_column(["elo", "points"])
    games_col = find_column(["match", "partie", "games"])
    inactivity_col = find_column(["inactiv"])

    if player_col is None:
        raise RuntimeError(
            f"Colonne joueur introuvable. Colonnes CLAX : {list(elo_df.columns)}"
        )

    if elo_col is None:
        raise RuntimeError(
            f"Colonne Elo introuvable. Colonnes CLAX : {list(elo_df.columns)}"
        )

    players = []

    for _, row in elo_df.iterrows():
        player_name = normalize_player_name(row[player_col])

        if not player_name or player_name.lower() == "nan":
            continue

        elo_value = parse_int(row[elo_col], default=None)

        if elo_value is None:
            continue

        games = parse_int(row[games_col], 0) if games_col is not None else 0
        inactivity = parse_int(row[inactivity_col], 0) if inactivity_col is not None else 0

        players.append({
            "player": player_name,
            "points": elo_value,
            "games": games,
            "inactivity": inactivity,
            "history": []
        })

    # Sécurité : ne pas écraser le cache local avec un résultat manifestement incomplet.
    if len(players) < 20:
        raise RuntimeError(
            f"Seulement {len(players)} joueurs récupérés depuis CLAX. "
            "Mise à jour annulée."
        )

    return players


def sync_players_from_clax():
    """
    Met à jour players.json avec le classement CLAX.
    En cas d'erreur, players.json existant est conservé.
    """

    try:
        players = fetch_players_from_clax()
        save_json_file(PLAYERS_FILE, players)
        return True, len(players), None

    except Exception as e:
        return False, 0, str(e)


def load_players():
    if not PLAYERS_FILE.exists():
        st.error(f"Fichier introuvable : {PLAYERS_FILE}")
        return pd.DataFrame(
            columns=["player", "points", "games", "inactivity"]
        )

    try:
        with PLAYERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

    except Exception as e:
        st.error("Erreur de lecture de players.json")
        st.exception(e)

        return pd.DataFrame(
            columns=["player", "points", "games", "inactivity"]
        )

    players = {}

    # -----------------------------------------------------
    # JOUEURS CLAX
    # -----------------------------------------------------
    for p in data:
        player_name = normalize_player_name(p.get("player", ""))

        if not player_name:
            continue

        players[player_name] = {
            "player": player_name,
            "points": p.get("points", 1500),
            "games": p.get("games", 0),
            "inactivity": p.get("inactivity", 0),
        }

    # -----------------------------------------------------
    # OVERRIDES + JOUEURS MANUELS
    # -----------------------------------------------------
    overrides = load_overrides()

    manual_players = overrides.get("players", {})

    for player_name, cfg in manual_players.items():
        clean_name = normalize_player_name(player_name)
        manual_elo = cfg.get("manual_elo")

        if manual_elo is None:
            continue

        if clean_name in players:
            players[clean_name]["points"] = int(manual_elo)

        else:
            players[clean_name] = {
                "player": clean_name,
                "points": int(manual_elo),
                "games": 0,
                "inactivity": 0,
            }

    df = pd.DataFrame(players.values())

    if df.empty:
        return df

    return (
        df
        .sort_values(
            ["points", "player"],
            ascending=[False, True]
        )
        .reset_index(drop=True)
    )

def apply_overrides_to_players_json():
    """
    Fusionne temporairement les overrides dans players.json
    afin que les scripts externes (master_pronostics.py, etc.)
    voient exactement les mêmes joueurs que l'interface Streamlit.
    """

    players = load_json_file(PLAYERS_FILE, [])
    overrides = load_overrides()

    players_by_name = {}

    for p in players:
        name = normalize_player_name(p.get("player", ""))

        if not name:
            continue

        players_by_name[name] = p.copy()
        players_by_name[name]["player"] = name

    for player_name, cfg in overrides.get("players", {}).items():
        clean_name = normalize_player_name(player_name)

        manual_elo = cfg.get("manual_elo")

        if manual_elo is None:
            continue

        if clean_name in players_by_name:
            players_by_name[clean_name]["points"] = int(manual_elo)

        else:
            players_by_name[clean_name] = {
                "player": clean_name,
                "points": int(manual_elo),
                "games": 0,
                "inactivity": 0,
                "history": []
            }

    merged_players = list(players_by_name.values())

    save_json_file(
        PLAYERS_FILE,
        merged_players
    )

def write_selection_file(path: Path, players):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(players), encoding="utf-8")


def run_command(script_name):
    script_path = BASE_DIR / script_name

    if not script_path.exists():
        st.error(f"Script introuvable : {script_name}")
        return False

    with st.spinner(f"Exécution : {script_name}"):
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=BASE_DIR,
            capture_output=True,
            text=True
        )

    if result.returncode != 0:
        st.error(f"Erreur dans {script_name}")

        if result.stdout:
            st.code(result.stdout)

        if result.stderr:
            st.code(result.stderr)

        return False

    st.success(f"OK : {script_name}")

    if result.stdout:
        with st.expander(f"Logs {script_name}"):
            st.code(result.stdout)

    return True


def display_image_if_exists(image_path: Path, label: str):
    if image_path.exists():
        st.image(str(image_path), use_container_width=True)

        with image_path.open("rb") as f:
            st.download_button(
                label=f"Télécharger {label}",
                data=f,
                file_name=image_path.name,
                mime="image/png"
            )
    else:
        st.warning(f"Image non trouvée : {image_path}")


def run_master_pipeline():

    apply_overrides_to_players_json()

    ok = run_command(SCRIPT_MASTER)

    if ok:
        ok = run_command(SCRIPT_PREPARE)

    if ok:
        ok = run_command(SCRIPT_IMAGE_MASTER)

    return ok


def run_elo_pipeline():

    apply_overrides_to_players_json()

    ok = run_command(SCRIPT_ELO)

    if ok:
        ok = run_command(SCRIPT_PREPARE)

    if ok:
        ok = run_command(SCRIPT_IMAGE_MASTER)

    return ok


def run_bracket_pipeline(bracket_size):

    apply_overrides_to_players_json()

    script = BRACKET_SCRIPTS.get(bracket_size)

    if script is None:
        st.error(
            f"Format bracket non géré : {bracket_size}"
        )
        return False

    ok = run_command(script)

    if ok:
        ok = run_command(SCRIPT_PREPARE)

    if ok:
        ok = run_command(SCRIPT_IMAGE_BRACKET)

    return ok


# =========================================================
# APP
# =========================================================

st.title("🏆 Elo-Clax — Générateur de pronostics")

with st.spinner("Synchronisation du classement Elo CLAX..."):
    sync_ok, synced_count, sync_error = sync_players_from_clax()

players_df = load_players()

if players_df.empty:
    st.error(
        "Impossible de charger la base joueurs. "
        "Vérifie players.json ou la synchronisation CLAX."
    )
    st.stop()

all_players = players_df["player"].tolist()

if sync_ok:
    st.caption(
        f"🟢 Elo CLAX synchronisé — {synced_count} joueurs"
    )
else:
    st.caption(
        "🟠 Impossible de synchroniser CLAX — "
        "utilisation du dernier classement enregistré."
    )

    with st.expander("Voir l'erreur de synchronisation CLAX"):
        st.code(sync_error or "Erreur inconnue")

with st.expander("Voir la base joueurs"):
    st.dataframe(players_df, use_container_width=True)


tab_master, tab_bracket, tab_settings = st.tabs([
    "Master",
    "Bracket / Match",
    "Paramètres"
])


# =========================================================
# MASTER
# =========================================================

with tab_master:
    st.header("Pronostic Master")

    st.caption(
        "Utilise master_pronostics.py puis génère le visuel Master."
    )

    default_master = (
        all_players[:24]
        if len(all_players) >= 24
        else all_players
    )

    selected_master_players = st.multiselect(
        "Joueurs du tournoi",
        all_players,
        default=default_master,
        key="master_players"
    )

    st.write(
        f"{len(selected_master_players)} joueur(s) sélectionné(s)."
    )

    if st.button(
        "Générer le visuel Master",
        type="primary"
    ):
        if len(selected_master_players) < 2:
            st.error(
                "Sélectionne au moins 2 joueurs."
            )
        else:
            write_selection_file(
                MASTER_SELECTION_FILE,
                selected_master_players
            )

            ok = run_master_pipeline()

            if ok:
                display_image_if_exists(
                    MASTER_IMAGE,
                    "image Master"
                )


# =========================================================
# BRACKET / MATCH
# =========================================================

with tab_bracket:
    st.header("Pronostic Bracket / Match")

    st.caption(
        "Les joueurs doivent être choisis dans l'ordre des seeds."
    )

    bracket_size = st.selectbox(
        "Format",
        [2, 4, 8, 16],
        format_func=lambda x: {
            2: "Finale — 2 joueurs",
            4: "Demi-finales — 4 joueurs",
            8: "Quarts — 8 joueurs",
            16: "Huitièmes — 16 joueurs",
        }[x],
        key="bracket_size"
    )

    default_bracket = (
        all_players[:bracket_size]
        if len(all_players) >= bracket_size
        else all_players
    )

    selected_bracket_players = st.multiselect(
        f"Joueurs du bracket ({bracket_size})",
        all_players,
        default=default_bracket,
        key="bracket_players"
    )

    if len(selected_bracket_players) != bracket_size:
        st.warning(
            f"Tu dois sélectionner exactement {bracket_size} joueurs."
        )

    st.subheader("Ordre des seeds")

    if selected_bracket_players:
        seed_df = pd.DataFrame({
            "seed": list(
                range(
                    1,
                    len(selected_bracket_players) + 1
                )
            ),
            "player": selected_bracket_players
        })

        st.dataframe(
            seed_df,
            use_container_width=True,
            hide_index=True
        )

    if st.button(
        "Générer le visuel Bracket / Match",
        type="primary"
    ):
        if len(selected_bracket_players) != bracket_size:
            st.error(
                f"Sélectionne exactement {bracket_size} joueurs."
            )
        else:
            write_selection_file(
                BRACKET_SELECTION_FILE,
                selected_bracket_players
            )

            ok = run_bracket_pipeline(
                bracket_size
            )

            if ok:
                display_image_if_exists(
                    BRACKET_IMAGE,
                    "image Bracket"
                )


# =========================================================
# PARAMÈTRES
# =========================================================

with tab_settings:
    st.header("Paramètres Elo")

    overrides = load_overrides()

    # -----------------------------------------------------
    # SYNCHRO CLAX
    # -----------------------------------------------------

    st.subheader("Synchronisation CLAX")

    st.write(
        "La base Elo est automatiquement récupérée depuis CLAX. "
        "Le fichier data/players.json sert désormais de cache local."
    )

    if st.button("Forcer la synchronisation CLAX"):
        fetch_players_from_clax.clear()

        ok, count, error = sync_players_from_clax()

        if ok:
            st.success(
                f"Synchronisation terminée : {count} joueurs récupérés."
            )
            st.rerun()

        else:
            st.error(
                "La synchronisation CLAX a échoué."
            )
            st.code(
                error or "Erreur inconnue"
            )

    st.divider()

    # -----------------------------------------------------
    # FORCE ELO
    # -----------------------------------------------------

    st.subheader("Force du Elo")

    current_divisor = float(
        overrides.get(
            "global",
            {}
        ).get(
            "elo_divisor",
            400
        )
    )

    elo_divisor = st.number_input(
        "elo_divisor",
        min_value=100,
        max_value=1000,
        value=int(current_divisor),
        step=10
    )

    st.caption(
        "Plus le divisor est bas, plus les écarts Elo sont violents. "
        "Ex : 300 = favoris plus forts, 400 = Elo standard."
    )

    if st.button("Sauvegarder elo_divisor"):
        overrides["global"]["elo_divisor"] = int(
            elo_divisor
        )

        save_overrides(overrides)

        st.success(
            "elo_divisor sauvegardé."
        )

    st.divider()

    # -----------------------------------------------------
    # MANUAL ELO
    # -----------------------------------------------------

    st.subheader("Manual Elo par joueur")

    selected_player = st.selectbox(
        "Joueur",
        all_players,
        key="manual_elo_player"
    )

    player_cfg = overrides.get(
        "players",
        {}
    ).get(
        selected_player,
        {}
    )

    current_manual = player_cfg.get(
        "manual_elo",
        None
    )

    current_real_elo = int(
        players_df.loc[
            players_df["player"] == selected_player,
            "points"
        ].iloc[0]
    )

    manual_elo = st.number_input(
        "manual_elo",
        min_value=500,
        max_value=3000,
        value=(
            int(current_manual)
            if current_manual is not None
            else current_real_elo
        ),
        step=10
    )

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Sauvegarder manual_elo"):
            overrides.setdefault(
                "players",
                {}
            )

            overrides["players"].setdefault(
                selected_player,
                {}
            )

            overrides["players"][
                selected_player
            ][
                "manual_elo"
            ] = int(manual_elo)

            save_overrides(
                overrides
            )

            st.success(
                f"manual_elo sauvegardé pour {selected_player}."
            )

    with col_b:
        if st.button("Supprimer manual_elo"):
            if selected_player in overrides.get(
                "players",
                {}
            ):
                overrides["players"].pop(
                    selected_player,
                    None
                )

                save_overrides(
                    overrides
                )

                st.success(
                    f"manual_elo supprimé pour {selected_player}."
                )

    if overrides.get("players"):
        st.write(
            "Overrides actuels"
        )

        overrides_df = pd.DataFrame([
            {
                "player": player,
                "manual_elo": cfg.get(
                    "manual_elo"
                )
            }
            for player, cfg in overrides["players"].items()
        ])

        st.dataframe(
            overrides_df,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # -----------------------------------------------------
    # JOUEUR ABSENT CLAX
    # -----------------------------------------------------

    st.subheader(
        "Ajouter un joueur non référencé dans CLAX"
    )

    new_player_name = st.text_input(
        "Nom du joueur au format NOM Prénom",
        placeholder="RAVEL Paul"
    )

    new_player_elo = st.number_input(
        "Elo manuel",
        min_value=500,
        max_value=3000,
        value=1500,
        step=10,
        key="new_player_elo"
    )

    if st.button("Ajouter le joueur manuel"):
        clean_name = normalize_player_name(
            new_player_name
        )

        if not clean_name:
            st.error("Nom vide.")

        else:
            overrides.setdefault(
                "players",
                {}
            )

            overrides["players"][
                clean_name
            ] = {
                "manual_elo": int(
                    new_player_elo
                )
            }

            save_overrides(
                overrides
            )

            st.success(
                f"{clean_name} ajouté avec un Elo manuel de "
                f"{new_player_elo}."
            )

            st.rerun()

    st.divider()

    # -----------------------------------------------------
    # SIMULATION MASTER
    # -----------------------------------------------------

    st.subheader(
        "Simulation Master"
    )

    runtime_config = load_runtime_config()

    current_n_simulations = int(
        runtime_config.get(
            "master_n_simulations",
            1000
        )
    )

    master_n_simulations = st.number_input(
        "Nombre de simulations Monte Carlo",
        min_value=1,
        max_value=10000,
        value=current_n_simulations,
        step=1
    )

    st.caption(
        "Plus élevé = plus précis mais plus lent. "
        "100 = rapide, 10000 = très stable."
    )

    if st.button(
        "Sauvegarder N_SIMULATIONS"
    ):
        runtime_config[
            "master_n_simulations"
        ] = int(
            master_n_simulations
        )

        save_runtime_config(
            runtime_config
        )

        st.success(
            f"N_SIMULATIONS = {master_n_simulations}"
        )

    st.divider()

    # -----------------------------------------------------
    # TITRES
    # -----------------------------------------------------

    st.subheader(
        "Titres des visuels"
    )

    runtime_config = load_runtime_config()

    current_title = runtime_config.get(
        "post_title",
        "Probabilité de victoire"
    )

    current_subtitle = runtime_config.get(
        "post_subtitle",
        ""
    )

    post_title = st.text_input(
        "Titre",
        value=current_title
    )

    post_subtitle = st.text_input(
        "Sous-titre",
        value=current_subtitle
    )

    if st.button(
        "Sauvegarder les titres"
    ):
        runtime_config[
            "post_title"
        ] = post_title

        runtime_config[
            "post_subtitle"
        ] = post_subtitle

        save_runtime_config(
            runtime_config
        )

        st.success(
            "Titres sauvegardés."
        )
