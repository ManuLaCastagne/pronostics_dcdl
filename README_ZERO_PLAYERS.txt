DCDL — VERSION ZÉRO players.json

1. Décompresse ce ZIP à la RACINE de ton repo (au même niveau que app.py).
2. Dans le terminal :

   python3 patch_zero_players.py

3. Teste :

   streamlit run app.py

4. Si tout fonctionne :

   git rm data/players.json
   git add .
   git commit -m "Use CLAX directly without players.json"
   git push

Le patch crée des .bak avant modification.
CLAX devient la source directe de tous les scripts.
overrides.json reste utilisé pour elo_divisor, manual_elo et joueurs absents de CLAX.
