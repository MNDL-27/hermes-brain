#!/usr/bin/env bash
# hermes-brain installer
# Usage: curl -fsSL https://raw.githubusercontent.com/MNDL-27/hermes-brain/main/scripts/install.sh | bash
#
# What this does:
#   1. Detects Python 3.11+ (installs if missing on common distros)
#   2. Clones hermes-brain to ~/.hermes-brain
#   3. Installs the package
#   4. Prompts for NOTION_API_KEY and HERMES_HOME
#   5. Bootstraps the Notion workspace (creates "Hermes Brain" page + 7 databases)
#   6. Verifies installation
#
# Supports: Ubuntu, Debian, Fedora, RHEL, Rocky, Alma. macOS/Windows not supported.

set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}  $1${NC}"; }
ok()      { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
fail()    { echo -e "${RED}✗ $1${NC}" >&2; }

# ─── Defaults ────────────────────────────────────────────────────────────
REPO_URL="https://github.com/MNDL-27/hermes-brain.git"
INSTALL_DIR="${HERMES_BRAIN_DIR:-$HOME/.hermes-brain}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SHELL_RC=""
PYTHON_PKG="python3"

# ─── Helpers ─────────────────────────────────────────────────────────────
command_exists() { command -v "$1" &>/dev/null; }

is_root() { [ "$(id -u)" -eq 0 ]; }

detect_shell_rc() {
    case "${SHELL##*/}" in
        bash)  SHELL_RC="$HOME/.bashrc" ;;
        zsh)   SHELL_RC="$HOME/.zshrc" ;;
        fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
        *)     SHELL_RC="$HOME/.profile" ;;
    esac
}

# ─── Header ──────────────────────────────────────────────────────────────
echo ""
info "╔══════════════════════════════════════════════════════════╗"
info "║           hermes-brain — Guided Installer                ║"
info "║   Persistent long-term memory for the Hermes AI agent    ║"
info "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Step 0: Not root ────────────────────────────────────────────────────
if is_root; then
    fail "Do not run this installer as root. Re-run as a regular user."
    exit 1
fi

# ─── Step 1: Detect distro & package manager ─────────────────────────────
info "Detecting system…"

PKG_MANAGER=""
PYTHON_PKG="python3"
PIP_CMD=""

if command_exists apt-get; then
    PKG_MANAGER="apt-get"
elif command_exists dnf; then
    PKG_MANAGER="dnf"
elif command_exists yum; then
    PKG_MANAGER="yum"
elif command_exists pacman; then
    PKG_MANAGER="pacman"
else
    warn "Unknown package manager. You may need to install Python 3.11+ manually."
fi

# ─── Step 2: Python 3.11+ ────────────────────────────────────────────────
info "Checking Python version…"

if command_exists python3; then
    PY_VER=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' || echo "0.0")
    MAJOR=${PY_VER%%.*}
    MINOR=${PY_VER##*.}
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        ok "Python $PY_VER found"
        PYTHON_PKG="python3"
    else
        warn "Python $PY_VER is too old (need 3.11+). Attempting to install 3.11…"
        case "$PKG_MANAGER" in
            apt-get)
                sudo apt-get update
                sudo apt-get install -y python3.11 python3.11-venv python3-pip
                PYTHON_PKG="python3.11"
                ;;
            dnf|yum)
                sudo "$PKG_MANAGER" install -y python3.11 python3.11-pip
                PYTHON_PKG="python3.11"
                ;;
            pacman)
                sudo pacman -S --noconfirm python
                PYTHON_PKG="python3"
                ;;
            *)
                fail "Could not install Python 3.11 automatically."
                echo "  Please install Python 3.11+ manually, then re-run this script."
                echo "  https://www.python.org/downloads/"
                exit 1
                ;;
        esac
        if command_exists "$PYTHON_PKG"; then
            ok "Python $($PYTHON_PKG --version) installed"
        else
            fail "Python 3.11 install failed. Install manually and re-run."
            exit 1
        fi
    fi
else
    warn "Python not found. Installing Python 3.11…"
    case "$PKG_MANAGER" in
        apt-get)
            sudo apt-get update
            sudo apt-get install -y python3.11 python3.11-venv python3-pip
            PYTHON_PKG="python3.11"
            ;;
        dnf|yum)
            sudo "$PKG_MANAGER" install -y python3.11 python3.11-pip
            PYTHON_PKG="python3.11"
            ;;
        pacman)
            sudo pacman -S --noconfirm python
            PYTHON_PKG="python3"
            ;;
        *)
            fail "Could not install Python automatically."
            echo "  https://www.python.org/downloads/"
            exit 1
            ;;
    esac
    ok "Python $($PYTHON_PKG --version) installed"
fi

# pip helper — always use $PYTHON_PKG -m pip so it works regardless of pip path
run_pip() {
    "$PYTHON_PKG" -m pip "$@"
}
ok "pip ready: $($PYTHON_PKG -m pip --version)"

# ─── Step 3: git ─────────────────────────────────────────────────────────
if ! command_exists git; then
    warn "git not found. Installing…"
    case "$PKG_MANAGER" in
        apt-get) sudo apt-get install -y git ;;
        dnf|yum) sudo "$PKG_MANAGER" install -y git ;;
        pacman)  sudo pacman -S --noconfirm git ;;
    esac
    ok "git installed"
fi

# ─── Step 4: Clone repo ──────────────────────────────────────────────────
info "Installing hermes-brain…"

if [ -d "$INSTALL_DIR" ]; then
    ok "Directory $INSTALL_DIR already exists — pulling latest"
    (cd "$INSTALL_DIR" && git pull --rebase)
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Cloned to $INSTALL_DIR"
fi

# ─── Step 5: pip install ─────────────────────────────────────────────────
info "Installing Python package…"

# Clean stale build artifacts that break pip (may need sudo if owned by root)
rm -rf "$INSTALL_DIR/hermes_brain.egg-info" "$INSTALL_DIR/build" "$INSTALL_DIR/dist" 2>/dev/null \
    || sudo rm -rf "$INSTALL_DIR/hermes_brain.egg-info" "$INSTALL_DIR/build" "$INSTALL_DIR/dist" 2>/dev/null \
    || true

PIP_INSTALL_OUTPUT=""
if PIP_INSTALL_OUTPUT=$(run_pip install --user "$INSTALL_DIR" 2>&1); then
    ok "Package installed"
elif PIP_INSTALL_OUTPUT=$(run_pip install --user --break-system-packages "$INSTALL_DIR" 2>&1); then
    ok "Package installed (with --break-system-packages)"
else
    fail "pip install failed:"
    echo "$PIP_INSTALL_OUTPUT" | sed 's/^/  /'
    exit 1
fi

# ─── Step 6: Environment variables ───────────────────────────────────────
info "Configuring environment…"

detect_shell_rc

# Check if already set
EXISTING_KEY="${NOTION_API_KEY:-}"
EXISTING_HOME="${HERMES_HOME:-}"

if [ -z "$EXISTING_KEY" ]; then
    echo ""
    echo -e "${CYAN}  Enter your Notion Internal Integration Token:${NC}"
    echo "  (Create one at https://www.notion.so/my-integrations)"
    echo "  Token starts with: ntn_"
    echo ""
    read -rp "  NOTION_API_KEY=" -s NOTION_API_KEY </dev/tty
    echo ""
    if [ -z "$NOTION_API_KEY" ]; then
        fail "No token provided. You can set it later:"
        echo "  export NOTION_API_KEY=ntn_xxxxx"
        exit 1
    fi
    ok "Token received"
else
    ok "NOTION_API_KEY already set in environment"
    NOTION_API_KEY="$EXISTING_KEY"
fi

if [ -z "$EXISTING_HOME" ]; then
    HERMES_HOME="$HOME/.hermes"
fi

# Write to shell rc (idempotent)
if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    if ! grep -q "HERMES_HOME=" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# hermes-brain" >> "$SHELL_RC"
        echo "export HERMES_HOME=\"$HERMES_HOME\"" >> "$SHELL_RC"
        echo "export NOTION_API_KEY=\"$NOTION_API_KEY\"" >> "$SHELL_RC"
        ok "Env vars added to $SHELL_RC"
    else
        # Update existing values
        tmp=$(mktemp)
        sed "s|^export HERMES_HOME=.*|export HERMES_HOME=\"$HERMES_HOME\"|" "$SHELL_RC" | \
        sed "s|^export NOTION_API_KEY=.*|export NOTION_API_KEY=\"$NOTION_API_KEY\"|" > "$tmp"
        mv "$tmp" "$SHELL_RC"
        ok "Env vars updated in $SHELL_RC"
    fi
fi

# Also write to $HERMES_HOME/.env for the package to read
mkdir -p "$HERMES_HOME"
cat > "$HERMES_HOME/.env" <<EOF
NOTION_API_KEY=$NOTION_API_KEY
HERMES_HOME=$HERMES_HOME
EOF
chmod 600 "$HERMES_HOME/.env"
ok "Env vars written to $HERMES_HOME/.env"

# ─── Step 7: Bootstrap ───────────────────────────────────────────────────
info "Bootstrapping Notion workspace…"
echo "  This creates the 'Hermes Brain' page and 7 databases in your Notion workspace."
echo ""

export NOTION_API_KEY
export HERMES_HOME

if "$PYTHON_PKG" -m notion_brain health &>/dev/null; then
    ok "Bootstrap complete"
    URL=$("$PYTHON_PKG" -m notion_brain url 2>/dev/null || echo "check your Notion workspace")
    echo ""
    info "Hermes Brain page: $URL"
else
    warn "Bootstrap encountered an issue. Run manually:"
    echo "  python -m notion_brain health"
    echo "  Troubleshooting: https://github.com/MNDL-27/hermes-brain/blob/main/docs/troubleshooting.md"
fi

# ─── Step 8: Verify ──────────────────────────────────────────────────────
info "Verifying installation…"

if "$PYTHON_PKG" -c "import notion_brain; print(notion_brain.__file__)" &>/dev/null; then
    ok "notion_brain is importable"
else
    fail "Import check failed"
    exit 1
fi

# ─── Done ────────────────────────────────────────────────────────────────
echo ""
info "╔══════════════════════════════════════════════════════════╗"
info "║                   Installation complete!                 ║"
info "╚══════════════════════════════════════════════════════════╝"
echo ""
info "Next steps:"
info "  1. Open your Notion workspace — you should see 'Hermes Brain'"
info "  2. Share the 'Hermes Brain' page with your integration:"
info "     Page → ••• → Connections → Add your integration"
info "  3. Run: python examples/quickstart.py"
info ""
info "Docs: https://github.com/MNDL-27/hermes-brain"
info "Troubleshooting: https://github.com/MNDL-27/hermes-brain/blob/main/docs/troubleshooting.md"
echo ""
