#!/bin/bash
#
# install.sh — Installation guidée de SESAM Ticket Manager (macOS)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_DIR="$SCRIPT_DIR/run"

# ─── Couleurs ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
fi

ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
warn() { echo -e "  ${YELLOW}!${RESET} $*"; }
err()  { echo -e "  ${RED}✗${RESET} $*" >&2; }
info() { echo -e "  ${CYAN}→${RESET} $*"; }
step() { echo ""; echo -e "${BOLD}${BLUE}$*${RESET}"; printf '%0.s─' {1..52}; echo; }

ask() {
  local prompt="$1" default="${2:-}" value
  if [[ -n "$default" ]]; then
    printf "  %s [%s]: " "$prompt" "$default" >&2
  else
    printf "  %s: " "$prompt" >&2
  fi
  read -r value
  printf '%s' "${value:-${default}}"
}

read_secret() {
  local _varname="$1" _secret_val
  printf "  %s: " "$2" >&2
  read -r _secret_val
  eval "${_varname}=\${_secret_val}"
}

ask_yn() {
  local prompt="$1" default="${2:-Y}" answer
  printf "  %s [%s] " "$prompt" "$default"
  read -r answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy] ]]
}

find_free_port() {
  local port
  for _ in {1..100}; do
    port=$((RANDOM % 1000 + 8001))
    if ! lsof -ti :"$port" &>/dev/null 2>&1; then
      echo "$port"
      return 0
    fi
  done
  echo "8080"
}

write_env_var() {
  local key="$1" value="$2"
  local escaped="${value//\'/\'\\\'\'}"
  printf "%s='%s'\n" "$key" "$escaped"
}

# ─── Bannière ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║    SESAM Ticket Manager — Installation macOS       ║${RESET}"
echo -e "${BOLD}╚════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Ce script va configurer l'application pas à pas."
echo -e "  Les fichiers d'exécution seront créés dans : ${CYAN}run/${RESET}"
echo -e "  Durée estimée : ${BOLD}2–5 minutes${RESET}"

# ─── Étape 1 : Homebrew ───────────────────────────────────────────────────────
step "[1/6] Homebrew"

if command -v brew &>/dev/null; then
  ok "Homebrew déjà installé ($(brew --version 2>/dev/null | head -1))"
else
  warn "Homebrew n'est pas installé."
  echo ""
  if ask_yn "Installer Homebrew maintenant ?" "Y"; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -f /opt/homebrew/bin/brew ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
      echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    ok "Homebrew installé."
  else
    err "Homebrew est requis pour la suite. Installation annulée."
    exit 1
  fi
fi

# ─── Étape 2 : Python 3.11+ ───────────────────────────────────────────────────
step "[2/6] Python 3.11+"

PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11; do
  if command -v "$cmd" &>/dev/null; then
    PYTHON_CMD="$cmd"
    break
  fi
done

if [[ -z "$PYTHON_CMD" ]] && command -v python3 &>/dev/null; then
  PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
  PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
  if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 11 ]]; then
    PYTHON_CMD="python3"
  fi
fi

if [[ -n "$PYTHON_CMD" ]]; then
  ok "Python trouvé : $("$PYTHON_CMD" --version 2>&1)"
else
  warn "Python 3.11+ non trouvé."
  echo ""
  if ask_yn "Installer Python 3.11 via Homebrew ?" "Y"; then
    brew install python@3.11
    PYTHON_CMD="$(brew --prefix python@3.11)/bin/python3.11"
    ok "Python 3.11 installé."
  else
    err "Python 3.11+ est requis. Installation annulée."
    exit 1
  fi
fi

# ─── Étape 3 : Dossier run/ + Virtualenv + dépendances ────────────────────────
step "[3/6] Environnement Python (run/)"

mkdir -p "$RUN_DIR"
ok "Dossier run/ prêt."

if [[ ! -d "$RUN_DIR/.venv" ]]; then
  info "Création du virtualenv dans run/.venv ..."
  "$PYTHON_CMD" -m venv "$RUN_DIR/.venv"
  ok "Virtualenv créé."
else
  ok "Virtualenv existant trouvé (run/.venv)."
fi

info "Installation des dépendances (peut prendre 1–2 min)..."
"$RUN_DIR/.venv/bin/pip" install --quiet --upgrade pip 2>&1 | tail -1 || true
"$RUN_DIR/.venv/bin/pip" install --quiet -r requirements.txt
ok "Dépendances installées."

# ─── Étape 4 : Port web ───────────────────────────────────────────────────────
step "[4/6] Port web"

DEFAULT_PORT=8473
CHOSEN_PORT=$DEFAULT_PORT

if lsof -ti :"$DEFAULT_PORT" &>/dev/null 2>&1; then
  PROCESS_CMD=$(lsof -ti :"$DEFAULT_PORT" | head -1 | xargs -I{} ps -p {} -o args= 2>/dev/null || echo "inconnu")
  if echo "$PROCESS_CMD" | grep -q "uvicorn" && echo "$PROCESS_CMD" | grep -q "web_app"; then
    ok "Le port $DEFAULT_PORT est déjà utilisé par l'application elle-même (déjà en cours d'exécution)."
    echo ""
    echo -e "  ${BOLD}┌──────────────────────────────────────────────────────┐${RESET}"
    echo -e "  ${BOLD}│                                                      │${RESET}"
    echo -e "  ${BOLD}│  L'application tourne déjà sur :                     │${RESET}"
    echo -e "  ${BOLD}│                                                      │${RESET}"
    echo -e "  ${BOLD}│    ${GREEN}http://localhost:${DEFAULT_PORT}${RESET}${BOLD}                          │${RESET}"
    echo -e "  ${BOLD}│                                                      │${RESET}"
    echo -e "  ${BOLD}└──────────────────────────────────────────────────────┘${RESET}"
    echo ""
    exit 0
  else
    warn "Le port $DEFAULT_PORT est déjà utilisé par : $PROCESS_CMD"
    SUGGESTED_PORT=$(find_free_port)
    echo ""
    if ask_yn "Utiliser le port $SUGGESTED_PORT à la place ?" "Y"; then
      CHOSEN_PORT=$SUGGESTED_PORT
    else
      CHOSEN_PORT=$(ask "Entrez un numéro de port" "8080")
      if ! [[ "$CHOSEN_PORT" =~ ^[0-9]+$ ]] || [[ "$CHOSEN_PORT" -lt 1024 ]] || [[ "$CHOSEN_PORT" -gt 65535 ]]; then
        warn "Port invalide, utilisation du port $SUGGESTED_PORT."
        CHOSEN_PORT=$SUGGESTED_PORT
      fi
    fi
  fi
fi
ok "Port $CHOSEN_PORT sélectionné."

# ─── Étape 5 : Configuration run/.env ─────────────────────────────────────────
step "[5/6] Configuration"

CONFIGURE_ENV=true
if [[ -f "$RUN_DIR/.env" ]]; then
  warn "Un fichier run/.env existe déjà."
  echo ""
  if ask_yn "Le reconfigurer ?" "N"; then
    CONFIGURE_ENV=true
  else
    CONFIGURE_ENV=false
    ok "Configuration existante conservée."
    if grep -q "^PORT=" "$RUN_DIR/.env" 2>/dev/null; then
      sed -i '' "s/^PORT=.*/PORT=$CHOSEN_PORT/" "$RUN_DIR/.env"
    else
      echo "" >> "$RUN_DIR/.env"
      write_env_var "PORT" "$CHOSEN_PORT" >> "$RUN_DIR/.env"
    fi
  fi
fi

if [[ "$CONFIGURE_ENV" == true ]]; then

  echo ""
  echo -e "  ${BOLD}── Portail SESAM-Vitale ────────────────────────────────${RESET}"
  echo -e "  ${CYAN}URL :${RESET} https://portail-support.sesam-vitale.fr"
  echo ""

  while true; do
    SESAM_USERNAME=""
    SESAM_PASSWORD=""

    while [[ -z "$SESAM_USERNAME" ]]; do
      SESAM_USERNAME=$(ask "Identifiant (login)")
      [[ -z "$SESAM_USERNAME" ]] && warn "L'identifiant ne peut pas être vide."
    done

    while [[ -z "$SESAM_PASSWORD" ]]; do
      read_secret SESAM_PASSWORD "Mot de passe"
      [[ -z "$SESAM_PASSWORD" ]] && warn "Le mot de passe ne peut pas être vide."
    done

    info "Vérification des identifiants..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
      -X POST "https://portail-support.sesam-vitale.fr/gsvextranet/api/authenticate" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      --max-time 15 \
      -d "{\"username\":\"${SESAM_USERNAME}\",\"password\":\"${SESAM_PASSWORD}\",\"rememberMe\":true}" \
      2>/dev/null)

    if [[ "$HTTP_CODE" == "200" ]]; then
      ok "Connexion réussie."
      break
    elif [[ "$HTTP_CODE" == "401" ]]; then
      warn "Identifiants incorrects. Veuillez réessayer."
    elif [[ -z "$HTTP_CODE" || "$HTTP_CODE" == "000" ]]; then
      warn "Impossible de joindre le portail. Vérifiez votre connexion internet."
    else
      warn "Erreur inattendue (HTTP $HTTP_CODE). Veuillez réessayer."
    fi
  done

  {
    echo "# ─────────────────────────────────────────────"
    echo "# Portail SESAM-Vitale"
    echo "# ─────────────────────────────────────────────"
    write_env_var "SESAM_URL" "https://portail-support.sesam-vitale.fr/gsvextranet/#/all-requests"
    write_env_var "SESAM_USERNAME" "$SESAM_USERNAME"
    write_env_var "SESAM_PASSWORD" "$SESAM_PASSWORD"
    echo "SESAM_HEADLESS=true"
    echo ""
    echo "# ─────────────────────────────────────────────"
    echo "# Stockage local (relatif à la racine du projet)"
    echo "# ─────────────────────────────────────────────"
    echo "STATE_FILE=run/.sesam_state.json"
    echo ""
    echo "# ─────────────────────────────────────────────"
    echo "# Serveur web"
    echo "# ─────────────────────────────────────────────"
    echo "PORT=$CHOSEN_PORT"
  } > "$RUN_DIR/.env"

  ok "run/.env créé."
fi

# ─── Étape 6 : Résumé ─────────────────────────────────────────────────────────
step "[6/6] Prêt !"
echo ""
ok "Python installé"
ok "Dépendances installées (run/.venv)"
ok "run/.env configuré"
ok "Port $CHOSEN_PORT sélectionné"
echo ""
echo -e "  ${BOLD}┌──────────────────────────────────────────────────────┐${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}│  Pour lancer l'application :                         │${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}│    ${GREEN}./start.sh${RESET}${BOLD}                                       │${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}│  L'app s'ouvrira automatiquement dans votre          │${RESET}"
echo -e "  ${BOLD}│  navigateur sur http://localhost:${CHOSEN_PORT}              │${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}└──────────────────────────────────────────────────────┘${RESET}"
echo ""

# ─── Aide rapide ──────────────────────────────────────────────────────────────
"$SCRIPT_DIR/start.sh" --help
