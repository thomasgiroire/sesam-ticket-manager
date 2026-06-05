#!/bin/bash
#
# setup.sh — Installateur bootstrap de SESAM Ticket Manager
#
# Usage :
#   curl -fsSL https://github.com/thomasgiroire/sesam-ticket-manager/releases/latest/download/setup.sh | bash
#
# Options (via variables d'environnement) :
#   SESAM_INSTALL_DIR  Répertoire d'installation (défaut: ~/Applications/sesam-ticket-manager)
#
set -euo pipefail

# ─── Couleurs ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
  RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'
else
  GREEN=''; YELLOW=''; CYAN=''; RED=''; BOLD=''; RESET=''
fi

ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
info() { echo -e "  ${CYAN}→${RESET} $*"; }
warn() { echo -e "  ${YELLOW}!${RESET} $*"; }
err()  { echo -e "  ${RED}✗${RESET} $*" >&2; exit 1; }

echo ""
echo -e "${BOLD}SESAM Ticket Manager — Installation${RESET}"
echo ""

# ─── Répertoire d'installation ────────────────────────────────────────────────
INSTALL_DIR="${SESAM_INSTALL_DIR:-$HOME/Applications/sesam-ticket-manager}"

# Réinstallation : détecter une install existante
if [[ -f "$HOME/.sesam/home" ]]; then
  _existing=$(tr -d '[:space:]' < "$HOME/.sesam/home")
  if [[ -f "$_existing/main.py" ]]; then
    warn "Installation existante détectée : $_existing"
    warn "Utilisez 'sesam --update' pour mettre à jour."
    exit 0
  fi
fi

info "Répertoire d'installation : $INSTALL_DIR"

# ─── Prérequis ────────────────────────────────────────────────────────────────
command -v curl  &>/dev/null || err "curl est requis (brew install curl)"
command -v unzip &>/dev/null || err "unzip est requis"
command -v python3 &>/dev/null || err "Python 3 est requis (brew install python)"

_PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
_PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
if (( _PY_MAJOR < 3 || (_PY_MAJOR == 3 && _PY_MINOR < 11) )); then
  err "Python 3.11+ requis (version actuelle : $_PY_MAJOR.$_PY_MINOR)"
fi
ok "Python $_PY_MAJOR.$_PY_MINOR détecté"

# ─── Téléchargement ───────────────────────────────────────────────────────────
_RELEASE_BASE="https://github.com/thomasgiroire/sesam-ticket-manager/releases/latest/download"
_ZIP_URL="$_RELEASE_BASE/sesam-ticket-manager.zip"

_TMP_DIR=$(mktemp -d)
trap 'rm -rf "$_TMP_DIR"' EXIT

info "Téléchargement de la dernière version..."
if ! curl -fsSL --max-time 60 "$_ZIP_URL" -o "$_TMP_DIR/sesam.zip"; then
  err "Impossible de télécharger $_ZIP_URL"
fi

info "Extraction..."
unzip -q "$_TMP_DIR/sesam.zip" -d "$_TMP_DIR/extracted"

# Lire la version depuis le ZIP
_VERSION="?"
[[ -f "$_TMP_DIR/extracted/VERSION" ]] && \
  _VERSION=$(tr -d '[:space:]' < "$_TMP_DIR/extracted/VERSION")
ok "Version $BOLD v${_VERSION}${RESET} téléchargée"

# ─── Installation ─────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
cp -R "$_TMP_DIR/extracted/." "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/install.sh" "$INSTALL_DIR/start.sh" 2>/dev/null || true
find "$INSTALL_DIR/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

ok "Fichiers copiés dans $INSTALL_DIR"

# ─── Lancement de l'installation guidée ──────────────────────────────────────
echo ""
cd "$INSTALL_DIR"
exec bash install.sh
