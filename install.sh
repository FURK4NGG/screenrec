#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="ScreenRec"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.config/scripts"
SCREENREC_SRC="$PROJECT_DIR/screenrec.sh"
UI_SRC="$PROJECT_DIR/screenrec-ui.py"
SCREENREC_DST="$TARGET_DIR/screenrec.sh"
UI_DST="$TARGET_DIR/screenrec-ui.py"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; RESET='\033[0m'
step() { printf "\n${BLUE}==>${RESET} %s\n" "$*"; }
ok()   { printf "${GREEN}[OK]${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}[WARNING]${RESET} %s\n" "$*"; }
err()  { printf "${RED}[ERROR]${RESET} %s\n" "$*" >&2; }
die()  { err "$*"; exit 1; }
trap 'rc=$?; err "Installation stopped unexpectedly (line: $LINENO, exit code: $rc)."; exit "$rc"' ERR

printf '%s\n' '====================================' "        $APP_NAME Installer" '===================================='

step "Checking source files"
[[ -f "$SCREENREC_SRC" ]] || die "Source file not found: $SCREENREC_SRC"
[[ -f "$UI_SRC" ]] || die "Source file not found: $UI_SRC"
command -v python3 >/dev/null 2>&1 || die "Required command not found: python3"
ok "screenrec.sh and screenrec-ui.py were found in: $PROJECT_DIR"

step "Creating target directory"
mkdir -p "$TARGET_DIR"
ok "Target directory is ready: $TARGET_DIR"

step "Installing ScreenRec files"
install -m 755 "$SCREENREC_SRC" "$SCREENREC_DST"
install -m 755 "$UI_SRC" "$UI_DST"
ok "Installed both screenrec.sh and screenrec-ui.py to $TARGET_DIR"

step "Checking script syntax"
bash -n "$SCREENREC_DST"
ok "screenrec.sh passed the Bash syntax check."

step "Checking Python syntax"
python3 -m py_compile "$UI_DST"
ok "screenrec-ui.py passed the Python syntax check."

step "Checking runtime dependencies"
for cmd in wf-recorder slurp notify-send; do
    if command -v "$cmd" >/dev/null 2>&1; then ok "$cmd is installed."; else warn "$cmd was not found. Some features may require it."; fi
done
python3 - <<'PY'
import importlib.util
for module in ("gi", "evdev"):
    if importlib.util.find_spec(module):
        print(f"[OK] Python module {module} is available.")
    else:
        print(f"[WARNING] Python module {module} was not found. The UI or key capture may not work.")
PY

printf '\n====================================\n'
printf "${GREEN}Installation completed.${RESET}\n"
printf 'Launcher: %s\n' "$SCREENREC_DST"
printf 'Settings UI: %s\n' "$UI_DST"
printf "To open the UI:\n  python3 '%s'\n" "$UI_DST"
printf '====================================\n'
