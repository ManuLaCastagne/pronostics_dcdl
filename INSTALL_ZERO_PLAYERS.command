#!/bin/bash
cd "$(dirname "$0")" || exit 1
python3 patch_zero_players.py
echo
echo "Appuie sur Entrée pour fermer."
read
