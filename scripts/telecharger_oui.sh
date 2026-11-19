#!/bin/sh
# Télécharge la liste officielle des préfixes constructeurs (OUI) de l'IEEE.
# Le fichier (~6 Mo) est placé dans data/oui.txt et n'est pas versionné.
set -e
cd "$(dirname "$0")/.."
mkdir -p data
curl -fL --retry 3 -o data/oui.txt https://standards-oui.ieee.org/oui/oui.txt
echo "Fichier OUI enregistré : data/oui.txt ($(grep -c '(hex)' data/oui.txt) constructeurs)"
