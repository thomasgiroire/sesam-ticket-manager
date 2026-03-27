#!/usr/bin/env bash
# package.sh - Crée une archive ZIP propre du projet sesam-ticket-manager

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="sesam-ticket-manager"
DATE=$(date +%Y-%m-%d)
OUTPUT="${SCRIPT_DIR}/${PROJECT_NAME}-${DATE}.zip"

# Option --desktop
if [[ "${1:-}" == "--desktop" ]]; then
  OUTPUT="${HOME}/Desktop/${PROJECT_NAME}-${DATE}.zip"
fi

# Vérification qu'on est bien à la racine du projet
if [[ ! -f "${SCRIPT_DIR}/main.py" ]]; then
  echo "❌ Erreur : exécuter depuis la racine du projet sesam-ticket-manager"
  exit 1
fi

# Supprime un éventuel ZIP existant du même nom
[[ -f "$OUTPUT" ]] && rm "$OUTPUT"

echo "📦 Création de l'archive : $(basename "$OUTPUT")"

cd "$SCRIPT_DIR"

# Fichiers/dossiers à inclure explicitement (utilisateur final, pas dev)
INCLUDE=(
  "main.py" "portal.py" "web_app.py" "config.py" "utils.py" "exceptions.py"
  "requirements.txt" ".env.example" "README.md"
  "start.sh" "install.sh"
  "templates/" "static/"
  "docs/USER_GUIDE_WEBAPP.md" "docs/EXAMPLES.md"
)

# Construction de la liste réelle (filtre les inexistants)
ITEMS=()
for item in "${INCLUDE[@]}"; do
  [[ -e "$item" ]] && ITEMS+=("$item")
done

zip -r "$OUTPUT" "${ITEMS[@]}" \
  --exclude "**/__pycache__/*" \
  --exclude "**/*.pyc" \
  --exclude "**/.pytest_cache/*"

echo ""
echo "✅ Archive créée : $OUTPUT"
echo "   Taille : $(du -sh "$OUTPUT" | cut -f1)"
echo ""
echo "📋 Contenu :"
zip -sf "$OUTPUT"
