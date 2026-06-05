#!/bin/bash
#
# uninstall.sh — Désinstallation de SESAM Ticket Manager (macOS)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Résoudre le vrai répertoire d'installation via ~/.sesam/home si disponible
# (le script peut être lancé depuis le repo de dev, pas depuis l'install réelle)
INSTALL_DIR="$SCRIPT_DIR"
if [[ -f "$HOME/.sesam/home" ]]; then
  _h=$(tr -d '[:space:]' < "$HOME/.sesam/home")
  [[ -f "$_h/main.py" ]] && INSTALL_DIR="$_h"
fi

RUN_DIR="$INSTALL_DIR/run"

# ─── Couleurs ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
fi

ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
warn() { echo -e "  ${YELLOW}!${RESET} $*"; }
info() { echo -e "  ${CYAN}→${RESET} $*"; }
step() { echo ""; echo -e "${BOLD}${BLUE}$*${RESET}"; printf '%0.s─' {1..52}; echo; }

ask_yn() {
  local prompt="$1" default="${2:-Y}" answer
  printf "  %s [%s] " "$prompt" "$default"
  read -r answer </dev/tty
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy] ]]
}

# ─── Options ──────────────────────────────────────────────────────────────────
FORCE=false
for _arg in "$@"; do [[ "$_arg" == "--force" ]] && FORCE=true; done

# ─── Bannière ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║    SESAM Ticket Manager — Désinstallation          ║${RESET}"
echo -e "${BOLD}╚════════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── Étape 1 : Détecter les symlinks installés ────────────────────────────────
step "[1/3] Détection de l'installation"

BIN_DIRS=(/usr/local/bin /opt/homebrew/bin "$HOME/.local/bin")
FOUND_SYMLINKS=()

for dir in "${BIN_DIRS[@]}"; do
  for name in sesam sesam-ui; do
    target="$dir/$name"
    if [[ -L "$target" ]]; then
      resolved=$(readlink "$target")
      # Ne supprimer que les symlinks qui pointent vers ce projet
      if [[ "$resolved" == "$INSTALL_DIR"* ]]; then
        FOUND_SYMLINKS+=("$target")
        info "Trouvé : $target → $resolved"
      elif [[ "$FORCE" == true ]]; then
        FOUND_SYMLINKS+=("$target")
        warn "Forcé : $target → $resolved"
      else
        warn "Ignoré (pointe ailleurs) : $target → $resolved (--force pour supprimer quand même)"
      fi
    fi
  done
done

if [[ -d "$RUN_DIR" ]]; then
  info "Trouvé : $RUN_DIR/ (virtualenv + configuration)"
fi

if [[ -f "$HOME/.sesam/home" ]]; then
  info "Trouvé : ~/.sesam/home (localisation d'installation)"
fi

# ─── Étape 2 : Confirmation ───────────────────────────────────────────────────
step "[2/3] Confirmation"

echo ""
echo -e "  Ce qui sera supprimé :"
for sym in "${FOUND_SYMLINKS[@]}"; do
  echo -e "    ${RED}✗${RESET} $sym"
done
[[ -d "$RUN_DIR" ]]              && echo -e "    ${RED}✗${RESET} $RUN_DIR/ (venv, .env, état local)"
[[ -f "$HOME/.sesam/home" ]]     && echo -e "    ${RED}✗${RESET} ~/.sesam/home"
echo ""
echo -e "  Ce qui sera ${BOLD}conservé${RESET} :"
echo -e "    ${GREEN}✓${RESET} Le code source ($INSTALL_DIR/)"
echo ""

if ! ask_yn "Confirmer la désinstallation ?" "N"; then
  echo ""
  info "Désinstallation annulée."
  exit 0
fi

# ─── Étape 3 : Suppression ────────────────────────────────────────────────────
step "[3/3] Suppression"

for sym in "${FOUND_SYMLINKS[@]}"; do
  rm -f "$sym"
  ok "Supprimé : $sym"
done

if [[ -d "$RUN_DIR" ]]; then
  rm -rf "$RUN_DIR"
  ok "Supprimé : $RUN_DIR/"
fi

if [[ -f "$HOME/.sesam/home" ]]; then
  rm -f "$HOME/.sesam/home"
  # Supprimer ~/.sesam/ si elle est vide
  rmdir "$HOME/.sesam" 2>/dev/null && ok "Supprimé : ~/.sesam/" || ok "Supprimé : ~/.sesam/home"
fi

echo ""
echo -e "  ${BOLD}┌──────────────────────────────────────────────────────┐${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}│  Désinstallation terminée.                           │${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}│  Pour réinstaller :                                  │${RESET}"
echo -e "  ${BOLD}│  ${CYAN}curl -fsSL$RESET"
echo -e "  ${BOLD}│    .../releases/latest/download/setup.sh | bash      │${RESET}"
echo -e "  ${BOLD}│                                                      │${RESET}"
echo -e "  ${BOLD}└──────────────────────────────────────────────────────┘${RESET}"
echo ""
