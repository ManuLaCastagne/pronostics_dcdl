from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
SCRIPTS = [
    "master_pronostics.py", "elo_pronostics.py", "match_pronostics.py",
    "bracket_4_pronostics.py", "bracket_8_pronostics.py", "bracket_16_pronostics.py",
]

def backup(path):
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)

def add_import(text, line):
    if line in text:
        return text
    marker = "import pandas as pd\n"
    return text.replace(marker, marker + line + "\n", 1) if marker in text else line + "\n" + text

def patch_script(path):
    text = path.read_text(encoding="utf-8")
    old = text
    text = add_import(text, "from elo_source import get_players")
    text = re.sub(r'all_players\s*=\s*load_players\(\s*PLAYERS_FILE\s*\)', 'all_players = get_players(OVERRIDES_FILE)', text)
    text = re.sub(r'^\s*PLAYERS_FILE\s*=\s*["\']data/players\.json["\']\s*\n', '', text, flags=re.M)
    text = text.replace("Joueurs introuvables dans players.json", "Joueurs introuvables dans CLAX / overrides.json")
    text = text.replace("Doublons détectés dans players.json", "Doublons détectés dans la source joueurs")
    if text != old:
        backup(path)
        path.write_text(text, encoding="utf-8")
        print("[OK]", path.name)

def patch_app(path):
    text = path.read_text(encoding="utf-8")
    old = text
    text = add_import(text, "from elo_source import get_players_dataframe")
    text = re.sub(r'^\s*PLAYERS_FILE\s*=\s*BASE_DIR\s*/\s*"data"\s*/\s*"players\.json"\s*\n', '', text, flags=re.M)
    text = text.replace("    apply_overrides_to_players_json()\n\n", "")

    start = text.find('with st.spinner("Synchronisation du classement Elo CLAX...")')
    end_marker = 'with st.expander("Voir la base joueurs"):\n    st.dataframe(players_df, use_container_width=True)'
    end = text.find(end_marker, start)
    if start != -1 and end != -1:
        end += len(end_marker)
        replacement = '''with st.spinner("Chargement du classement Elo CLAX en direct..."):
    try:
        players_df = get_players_dataframe(OVERRIDES_FILE)
    except Exception as e:
        st.error("Impossible de récupérer le classement Elo CLAX.")
        st.exception(e)
        st.stop()

if players_df.empty:
    st.error("Aucun joueur récupéré depuis CLAX.")
    st.stop()

all_players = players_df["player"].tolist()
st.caption(f"🟢 Source directe CLAX — {len(players_df)} joueurs — aucun players.json")

with st.expander("Voir la base joueurs"):
    st.dataframe(players_df, use_container_width=True)'''
        text = text[:start] + replacement + text[end:]
    else:
        print("[WARN] Bloc démarrage app.py non reconnu")

    s = text.find('    # SYNCHRO CLAX')
    if s != -1:
        block_start = text.rfind('    # -----------------------------------------------------', 0, s)
        divider = text.find('    st.divider()', s)
        if block_start != -1 and divider != -1:
            divider_end = divider + len('    st.divider()')
            replacement = '''    # -----------------------------------------------------
    # SOURCE CLAX
    # -----------------------------------------------------

    st.subheader("Source Elo CLAX")
    st.write(
        "Les joueurs et Elo sont lus directement depuis "
        "https://dcdl-laxou.fr/ts/elo/#/global. Aucun players.json n'est utilisé."
    )
    if st.button("Recharger les Elo depuis CLAX"):
        st.rerun()
    st.divider()'''
            text = text[:block_start] + replacement + text[divider_end:]

    if text != old:
        backup(path)
        path.write_text(text, encoding="utf-8")
        print("[OK] app.py")

def main():
    needed = [ROOT / "app.py"] + [ROOT / n for n in SCRIPTS]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        raise SystemExit("Décompresse ce ZIP à la racine du repo. Manquants: " + ", ".join(missing))
    patch_app(ROOT / "app.py")
    for name in SCRIPTS:
        patch_script(ROOT / name)
    print("\n✅ Patch terminé. Teste avec: streamlit run app.py")
    if (ROOT / "data" / "players.json").exists():
        print("Puis supprime l'ancien fichier avec: git rm data/players.json")

if __name__ == "__main__":
    main()
