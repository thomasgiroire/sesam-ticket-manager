#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_DIR="$SCRIPT_DIR/run"

# ─── Couleurs ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
  BOLD='\033[1m'; RESET='\033[0m'
else
  GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

# ─── Aide ─────────────────────────────────────────────────────────────────────
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
  echo ""
  echo -e "${BOLD}SESAM Ticket Manager — Aide rapide${RESET}"
  echo ""
  echo -e "${BOLD}UTILISATION${RESET}"
  echo -e "  ${GREEN}./start.sh${RESET}          Démarrer l'application web"
  echo -e "  ${GREEN}./start.sh --help${RESET}   Afficher cette aide"
  echo ""
  echo -e "${BOLD}PREMIER DÉMARRAGE${RESET}"
  echo -e "  Si l'application n'est pas encore installée, lancez d'abord :"
  echo -e "  ${CYAN}./install.sh${RESET}"
  echo ""
  echo -e "${BOLD}FONCTIONNEMENT${RESET}"
  echo -e "  • L'application s'ouvre automatiquement dans votre navigateur"
  echo -e "  • Utilisez ${BOLD}Ctrl+C${RESET} pour arrêter le serveur"
  echo -e "  • Le port est configurable dans ${CYAN}run/.env${RESET} (variable PORT)"
  echo ""
  echo -e "${BOLD}CLI — EXEMPLES D'USAGE${RESET}"
  echo -e "  La CLI s'utilise via le virtualenv de l'environnement d'exécution :"
  echo -e "  ${CYAN}source run/.venv/bin/activate${RESET}"
  echo ""
  echo -e "  ${BOLD}Consulter les tickets${RESET}"
  echo -e "  ${GREEN}python main.py list${RESET}                         Lister tous les tickets"
  echo -e "  ${GREEN}python main.py list --open-only${RESET}              Uniquement les tickets ouverts"
  echo -e "  ${GREEN}python main.py list --status \"En cours\"${RESET}      Filtrer par statut"
  echo -e "  ${GREEN}python main.py list --type Incident${RESET}          Filtrer par type"
  echo ""
  echo -e "  ${BOLD}Détail et messages${RESET}"
  echo -e "  ${GREEN}python main.py show 26-083-026025${RESET}            Détail d'un ticket"
  echo -e "  ${GREEN}python main.py messages 26-083-026025${RESET}        Historique des messages"
  echo -e "  ${GREEN}python main.py show 26-083-026025 --json-output${RESET}  Export JSON brut"
  echo ""
  echo -e "  ${BOLD}Répondre et exporter${RESET}"
  echo -e "  ${GREEN}python main.py reply 26-083-026025${RESET}           Répondre à un ticket (interactif)"
  echo -e "  ${GREEN}python main.py export 26-083-026025${RESET}          Exporter en Markdown"
  echo -e "  ${GREEN}python main.py export 26-083-026025 --format json${RESET}  Exporter en JSON"
  echo ""
  echo -e "  ${BOLD}Synchronisation et état${RESET}"
  echo -e "  ${GREEN}python main.py sync${RESET}                          Détecter les nouveaux tickets"
  echo -e "  ${GREEN}python main.py sync --all${RESET}                    Traiter tous les tickets"
  echo -e "  ${GREEN}python main.py sync --dry-run${RESET}                Simuler sans modifier l'état"
  echo -e "  ${GREEN}python main.py status${RESET}                        Vérifier la connexion"
  echo ""
  echo -e "  ${YELLOW}Note :${RESET} la référence ticket est au format XX-YYY-NNNNNN (ex: 26-083-026025)"
  echo ""
  echo -e "${BOLD}DOCUMENTATION${RESET}"
  echo -e "  ${CYAN}docs/USER_GUIDE_WEBAPP.md${RESET}   Guide d'utilisation de l'interface web"
  echo -e "  ${CYAN}docs/README.md${RESET}              Guide CLI (commandes, options, exemples)"
  echo ""
  exit 0
fi

# ─── Vérification ─────────────────────────────────────────────────────────────
# Vérifier que run/ est initialisé
if [[ ! -f "$RUN_DIR/.env" || ! -d "$RUN_DIR/.venv" ]]; then
  echo "Erreur : run/ non initialisé. Lance d'abord : ./install.sh"
  exit 1
fi

# Lire le PORT depuis run/.env (défaut : 8473)
PORT=8473
_ENV_PORT=$(grep -E '^PORT=' "$RUN_DIR/.env" | head -1 | sed "s/^PORT=//; s/['\"]//g" | tr -d '[:space:]')
if [[ -n "$_ENV_PORT" && "$_ENV_PORT" =~ ^[0-9]+$ ]]; then
  PORT="$_ENV_PORT"
fi

# Trap Ctrl+C
cleanup() {
  echo ""
  echo "Stopping server..."
  kill "$SERVER_PID" 2>/dev/null
  wait "$SERVER_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

# Libérer le port si occupé
if lsof -ti :"$PORT" &>/dev/null; then
  echo "Port $PORT already in use. Stopping existing process..."
  lsof -ti :"$PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "Starting server on http://localhost:$PORT ..."

# Exporter les variables de run/.env dans l'environnement
# (load_dotenv() en Python ne les écrasera pas)
set -a
# shellcheck disable=SC1091
source "$RUN_DIR/.env"
set +a

# Activer le virtualenv
# shellcheck disable=SC1091
source "$RUN_DIR/.venv/bin/activate"

# Démarrer le serveur web en arrière-plan
uvicorn web_app:app --reload --port "$PORT" &
SERVER_PID=$!

# Attendre que le serveur soit prêt, puis ouvrir le navigateur
(
  for i in {1..20}; do
    sleep 0.5
    if curl -sf "http://localhost:$PORT/" >/dev/null 2>&1; then
      echo "✓ Application prête — ouverture dans le navigateur..."
      open "http://localhost:$PORT"
      exit 0
    fi
  done
  open "http://localhost:$PORT"
) &

wait "$SERVER_PID"
