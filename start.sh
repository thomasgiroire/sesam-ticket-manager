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

# ─── Mise à jour automatique ──────────────────────────────────────────────────
_RELEASE_SHA1="https://github.com/thomasgiroire/sesam-ticket-manager/releases/download/latest/sesam-ticket-manager.sha1"
_RELEASE_ZIP="https://github.com/thomasgiroire/sesam-ticket-manager/releases/download/latest/sesam-ticket-manager.zip"    
_VERSION_FILE="$RUN_DIR/.version"
_do_update=true
for _arg in "$@"; do [[ "$_arg" == "--no-update" ]] && _do_update=false; done

if [[ "$_do_update" == true ]] && command -v curl &>/dev/null; then

  echo -e "${CYAN}Vérification des mises à jour...${RESET}"

  _REMOTE_SHA=$(curl -sL --max-time 10 "$_RELEASE_SHA1")

  if [[ -z "$_REMOTE_SHA" ]]; then
    echo -e "${YELLOW}⚠ Impossible de vérifier les mises à jour (pas de réseau ?).${RESET}"
  else
    _LOCAL_SHA=""
    [[ -f "$_VERSION_FILE" ]] && _LOCAL_SHA=$(cat "$_VERSION_FILE" | tr -d '[:space:]')

    if [[ "$_LOCAL_SHA" == "$_REMOTE_SHA" ]]; then
      echo -e "${GREEN}✓ Application à jour.${RESET}"
    else
      echo -e "${GREEN}→ Nouvelle version détectée. Mise à jour en cours...${RESET}"
      _TMP_DIR=$(mktemp -d)
      if curl -sL --max-time 60 "$_RELEASE_ZIP" \
              -o "$_TMP_DIR/update.zip" \
          && unzip -q "$_TMP_DIR/update.zip" -d "$_TMP_DIR/extracted"; then

        # Snapshot requirements.txt avant remplacement
        _REQ_BEFORE=$(md5 -q "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
                      || md5sum "$SCRIPT_DIR/requirements.txt" 2>/dev/null | awk '{print $1}')

        # Copier les fichiers applicatifs (pas run/, install.sh, docs/)
        cp "$_TMP_DIR/extracted"/*.py            "$SCRIPT_DIR/"
        cp "$_TMP_DIR/extracted/requirements.txt" "$SCRIPT_DIR/"
        cp -r "$_TMP_DIR/extracted/templates"    "$SCRIPT_DIR/"
        cp -r "$_TMP_DIR/extracted/static"       "$SCRIPT_DIR/"
        if [[ -d "$_TMP_DIR/extracted/bin" ]]; then
          mkdir -p "$SCRIPT_DIR/bin"
          cp -R "$_TMP_DIR/extracted/bin/." "$SCRIPT_DIR/bin/"
          chmod +x "$SCRIPT_DIR/bin/"* 2>/dev/null || true
        fi

        # Mise à jour de start.sh — avec validation syntaxique pour
        # éviter de remplacer par un script cassé. L'ancien est conservé
        # en start.sh.bak en cas de rollback manuel nécessaire.
        if [[ -f "$_TMP_DIR/extracted/start.sh" ]]; then
          if bash -n "$_TMP_DIR/extracted/start.sh" 2>/dev/null; then
            cp "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/start.sh.bak" 2>/dev/null || true
            cp "$_TMP_DIR/extracted/start.sh" "$SCRIPT_DIR/start.sh"
            chmod +x "$SCRIPT_DIR/start.sh" 2>/dev/null || true
            echo -e "${CYAN}→ start.sh mis à jour (ancien sauvegardé en start.sh.bak)${RESET}"
          else
            echo -e "${YELLOW}⚠ Nouveau start.sh invalide — conservation de la version actuelle.${RESET}"
          fi
        fi

        _REQ_AFTER=$(md5 -q "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
                     || md5sum "$SCRIPT_DIR/requirements.txt" 2>/dev/null | awk '{print $1}')

        # Réinstaller les dépendances si requirements.txt a changé
        if [[ "$_REQ_BEFORE" != "$_REQ_AFTER" && -d "$RUN_DIR/.venv" ]]; then
          echo -e "${CYAN}→ Nouvelles dépendances. Installation...${RESET}"
          "$RUN_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
        fi

        echo "$_REMOTE_SHA" > "$_VERSION_FILE"
        echo -e "${GREEN}✓ Application mise à jour.${RESET}"
      else
        echo -e "${YELLOW}⚠ Téléchargement échoué. Démarrage avec la version actuelle.${RESET}"
      fi

      rm -rf "$_TMP_DIR"
    fi
  fi
fi

# ─── Migration silencieuse : commandes globales 'sesam' et 'sesam-ui' ────────
# Pour les utilisateurs déjà installés (avant l'ajout du dossier bin/) :
# on crée best-effort le marqueur ~/.sesam/home et les symlinks globaux, à
# condition que rien n'existe déjà à la cible (pour ne pas écraser un autre
# outil nommé `sesam`).
if [[ -x "$SCRIPT_DIR/bin/sesam" ]]; then
  # Marqueur ~/.sesam/home (toujours sûr — fichier qui nous appartient)
  if [[ ! -f "$HOME/.sesam/home" ]]; then
    mkdir -p "$HOME/.sesam" 2>/dev/null
    echo "$SCRIPT_DIR" > "$HOME/.sesam/home" 2>/dev/null && \
      echo -e "${CYAN}→ Marqueur d'installation enregistré (~/.sesam/home)${RESET}"
  fi

  # Symlinks /usr/local/bin (Intel), /opt/homebrew/bin (Apple Silicon),
  # ou fallback ~/.local/bin si nécessaire
  _migrate_target_dir=""
  for d in /usr/local/bin /opt/homebrew/bin; do
    if [[ -d "$d" && -w "$d" ]]; then
      _migrate_target_dir="$d"
      break
    fi
  done
  if [[ -z "$_migrate_target_dir" && -d "$HOME/.local/bin" ]]; then
    _migrate_target_dir="$HOME/.local/bin"
  fi

  if [[ -n "$_migrate_target_dir" ]]; then
    for _name in sesam sesam-ui; do
      _target="$_migrate_target_dir/$_name"
      _src="$SCRIPT_DIR/bin/$_name"
      if [[ -x "$_src" && ! -e "$_target" && ! -L "$_target" ]]; then
        if ln -s "$_src" "$_target" 2>/dev/null; then
          echo -e "${GREEN}✓ Commande globale installée : $_target${RESET}"
        fi
      fi
    done
  fi
fi

# ─── Aide ─────────────────────────────────────────────────────────────────────
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
  echo ""
  echo -e "${BOLD}SESAM Ticket Manager — Aide rapide${RESET}"
  echo ""
  echo -e "${BOLD}UTILISATION${RESET}"
  echo -e "  ${GREEN}./start.sh${RESET}             Démarrer l'application web"
  echo -e "  ${GREEN}./start.sh --no-update${RESET} Démarrer sans vérifier les mises à jour"
  echo -e "  ${GREEN}./start.sh --help${RESET}      Afficher cette aide"
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
  echo -e "  ${CYAN}docs/USER_GUIDE_WEBAPP.md${RESET}     Guide d'utilisation de l'interface web"
  echo -e "  ${CYAN}docs/CLI_USER_GUIDE.md${RESET}        Guide CLI (commandes, options, exemples)"
  echo ""
  exit 0
fi

# ─── Vérification ─────────────────────────────────────────────────────────────
# Vérifier que run/ est initialisé
if [[ ! -f "$RUN_DIR/.env" || ! -d "$RUN_DIR/.venv" ]]; then
  echo "Erreur : run/ non initialisé. Lance d'abord : ./install.sh"
  exit 1
fi

# Vérifier que l'interpréteur Python du venv est toujours valide
_VENV_PYTHON=$(head -1 "$RUN_DIR/.venv/bin/uvicorn" 2>/dev/null | sed 's/^#!//')
if [[ -n "$_VENV_PYTHON" && ! -x "$_VENV_PYTHON" ]]; then
  echo -e "${YELLOW}⚠ L'interpréteur Python du venv est introuvable ($_VENV_PYTHON).${RESET}"
  echo -e "${CYAN}→ Reconstruction du virtualenv avec $(python3 --version 2>&1)...${RESET}"
  rm -rf "$RUN_DIR/.venv"
  if ! python3 -m venv "$RUN_DIR/.venv"; then
    echo "Erreur : impossible de créer le virtualenv. Vérifie que python3 est installé."
    exit 1
  fi
  echo -e "${CYAN}→ Installation des dépendances...${RESET}"
  "$RUN_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
  echo -e "${GREEN}✓ Virtualenv reconstruit avec succès.${RESET}"
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
