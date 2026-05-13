import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


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

def load_runtime_config():
    return load_json_file(
        RUNTIME_CONFIG_FILE,
        {
            "master_n_simulations": 1000
        }
    )

def save_runtime_config(data):
    save_json_file(RUNTIME_CONFIG_FILE, data)

def save_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_overrides():
    data = load_json_file(OVERRIDES_FILE, {"global": {}, "players": {}})
    data.setdefault("global", {})
    data.setdefault("players", {})
    return data


def save_overrides(overrides):
    save_json_file(OVERRIDES_FILE, overrides)


def add_player_to_players_json(player_name, points=1500):
    players = load_json_file(PLAYERS_FILE, [])

    existing = {
        " ".join(p.get("player", "").lower().split())
        for p in players
    }

    key = " ".join(player_name.lower().split())

    if key in existing:
        return False, "Ce joueur existe déjà dans players.json."

    players.append({
        "player": player_name,
        "points": int(points),
        "games": 0,
        "inactivity": 0,
        "history": []
    })

    save_json_file(PLAYERS_FILE, players)
    return True, f"{player_name} ajouté à players.json."

def load_players():
    if not PLAYERS_FILE.exists():
        st.error(f"Fichier introuvable : {PLAYERS_FILE}")
        return pd.DataFrame(columns=["player", "points", "games", "inactivity"])

    try:
        with PLAYERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.error("Erreur de lecture de players.json")
        st.exception(e)
        return pd.DataFrame(columns=["player", "points", "games", "inactivity"])

    rows = []
    for p in data:
        rows.append({
            "player": p.get("player", ""),
            "points": p.get("points", 0),
            "games": p.get("games", 0),
            "inactivity": p.get("inactivity", 0),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    return df.sort_values(["points", "player"], ascending=[False, True]).reset_index(drop=True)


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
    ok = run_command(SCRIPT_MASTER)
    if ok:
        ok = run_command(SCRIPT_PREPARE)
    if ok:
        ok = run_command(SCRIPT_IMAGE_MASTER)
    return ok


def run_elo_pipeline():
    ok = run_command(SCRIPT_ELO)
    if ok:
        ok = run_command(SCRIPT_PREPARE)
    if ok:
        ok = run_command(SCRIPT_IMAGE_MASTER)
    return ok


def run_bracket_pipeline(bracket_size):
    script = BRACKET_SCRIPTS.get(bracket_size)

    if script is None:
        st.error(f"Format bracket non géré : {bracket_size}")
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

players_df = load_players()

if players_df.empty:
    st.stop()

all_players = players_df["player"].tolist()

with st.expander("Voir la base joueurs"):
    st.dataframe(players_df, use_container_width=True)


tab_master, tab_bracket, tab_elo, tab_settings = st.tabs([
    "Master",
    "Bracket / Match",
    "Elo brut",
    "Paramètres"
])


# =========================================================
# MASTER
# =========================================================

with tab_master:
    st.header("Pronostic Master")

    st.caption("Utilise master_pronostics.py puis génère le visuel Master.")

    default_master = all_players[:24] if len(all_players) >= 24 else all_players

    selected_master_players = st.multiselect(
        "Joueurs du tournoi",
        all_players,
        default=default_master,
        key="master_players"
    )

    st.write(f"{len(selected_master_players)} joueur(s) sélectionné(s).")

    if st.button("Générer le visuel Master", type="primary"):
        if len(selected_master_players) < 2:
            st.error("Sélectionne au moins 2 joueurs.")
        else:
            write_selection_file(MASTER_SELECTION_FILE, selected_master_players)

            ok = run_master_pipeline()

            if ok:
                display_image_if_exists(MASTER_IMAGE, "image Master")


# =========================================================
# BRACKET / MATCH
# =========================================================

with tab_bracket:
    st.header("Pronostic Bracket / Match")

    st.caption("Les joueurs doivent être choisis dans l'ordre des seeds.")

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

    default_bracket = all_players[:bracket_size] if len(all_players) >= bracket_size else all_players

    selected_bracket_players = st.multiselect(
        f"Joueurs du bracket ({bracket_size})",
        all_players,
        default=default_bracket,
        key="bracket_players"
    )

    if len(selected_bracket_players) != bracket_size:
        st.warning(f"Tu dois sélectionner exactement {bracket_size} joueurs.")

    st.subheader("Ordre des seeds")

    if selected_bracket_players:
        seed_df = pd.DataFrame({
            "seed": list(range(1, len(selected_bracket_players) + 1)),
            "player": selected_bracket_players
        })
        st.dataframe(seed_df, use_container_width=True, hide_index=True)

    if st.button("Générer le visuel Bracket / Match", type="primary"):
        if len(selected_bracket_players) != bracket_size:
            st.error(f"Sélectionne exactement {bracket_size} joueurs.")
        else:
            write_selection_file(BRACKET_SELECTION_FILE, selected_bracket_players)

            ok = run_bracket_pipeline(bracket_size)

            if ok:
                display_image_if_exists(BRACKET_IMAGE, "image Bracket")


# =========================================================
# ELO BRUT
# =========================================================

with tab_elo:
    st.header("Pronostic Elo brut")

    st.caption("Utilise elo_pronostics.py. Attention : ton générateur Master doit lire pronostic_elo_post_ready.csv si tu veux ce rendu.")

    default_elo = all_players[:24] if len(all_players) >= 24 else all_players

    selected_elo_players = st.multiselect(
        "Joueurs",
        all_players,
        default=default_elo,
        key="elo_players"
    )

    st.write(f"{len(selected_elo_players)} joueur(s) sélectionné(s).")

    if st.button("Générer le visuel Elo brut", type="primary"):
        if len(selected_elo_players) < 2:
            st.error("Sélectionne au moins 2 joueurs.")
        else:
            write_selection_file(ELO_SELECTION_FILE, selected_elo_players)

            ok = run_elo_pipeline()

            if ok:
                display_image_if_exists(MASTER_IMAGE, "image Elo brut")

# =========================================================
# PARAMÈTRES
# =========================================================

with tab_settings:
    st.header("Paramètres Elo")

    overrides = load_overrides()

    st.subheader("Force du Elo")

    current_divisor = float(overrides.get("global", {}).get("elo_divisor", 400))

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
        overrides["global"]["elo_divisor"] = int(elo_divisor)
        save_overrides(overrides)
        st.success("elo_divisor sauvegardé.")

    st.divider()

    st.subheader("Manual Elo par joueur")

    selected_player = st.selectbox(
        "Joueur",
        all_players,
        key="manual_elo_player"
    )

    player_cfg = overrides.get("players", {}).get(selected_player, {})
    current_manual = player_cfg.get("manual_elo", None)

    manual_elo = st.number_input(
        "manual_elo",
        min_value=500,
        max_value=3000,
        value=int(current_manual) if current_manual is not None else 1500,
        step=10
    )

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Sauvegarder manual_elo"):
            overrides.setdefault("players", {})
            overrides["players"].setdefault(selected_player, {})
            overrides["players"][selected_player]["manual_elo"] = int(manual_elo)
            save_overrides(overrides)
            st.success(f"manual_elo sauvegardé pour {selected_player}.")

    with col_b:
        if st.button("Supprimer manual_elo"):
            if selected_player in overrides.get("players", {}):
                overrides["players"].pop(selected_player, None)
                save_overrides(overrides)
                st.success(f"manual_elo supprimé pour {selected_player}.")

    if overrides.get("players"):
        st.write("Overrides actuels")
        overrides_df = pd.DataFrame([
            {
                "player": player,
                "manual_elo": cfg.get("manual_elo")
            }
            for player, cfg in overrides["players"].items()
        ])
        st.dataframe(overrides_df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Ajouter un joueur non référencé")

    new_player_name = st.text_input(
        "Nom du joueur au format NOM Prénom",
        placeholder="RAVEL Paul"
    )

    new_player_elo = st.number_input(
        "Elo initial",
        min_value=500,
        max_value=3000,
        value=1500,
        step=10,
        key="new_player_elo"
    )

    if st.button("Ajouter au players.json"):
        clean_name = " ".join(new_player_name.strip().split())

        if not clean_name:
            st.error("Nom vide.")
        else:
            ok, msg = add_player_to_players_json(clean_name, new_player_elo)

            if ok:
                st.success(msg)
                st.info("Recharge la page Streamlit pour voir le joueur dans les listes.")
            else:
                st.warning(msg)
    
    st.divider()

    st.subheader("Simulation Master")

    runtime_config = load_runtime_config()

    current_n_simulations = int(
        runtime_config.get("master_n_simulations", 1000)
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

    if st.button("Sauvegarder N_SIMULATIONS"):
        runtime_config["master_n_simulations"] = int(master_n_simulations)
        save_runtime_config(runtime_config)

        st.success(
            f"N_SIMULATIONS = {master_n_simulations}"
        )

    st.divider()

    st.subheader("Titres des visuels")

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

    if st.button("Sauvegarder les titres"):
        runtime_config["post_title"] = post_title
        runtime_config["post_subtitle"] = post_subtitle

        save_runtime_config(runtime_config)

        st.success("Titres sauvegardés.")

    if st.button("Réinitialiser les titres"):
        runtime_config = load_runtime_config()
        runtime_config["post_title"] = "Probabilité de victoire"
        runtime_config["post_subtitle"] = ""
        save_runtime_config(runtime_config)
        st.success("Titres réinitialisés.")