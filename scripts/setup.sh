#!/usr/bin/env bash
# One-time setup: submodules, git-lfs, .env.
# Usage: scripts/setup.sh [--display x11|novnc|web] [--gpu none|nvidia|dri] [--dev]
set -euo pipefail
cd "$(dirname "$0")/.."

DISPLAY_MODE=x11; GPU=none; DEV=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --display) DISPLAY_MODE="$2"; shift 2;;
    --gpu)     GPU="$2"; shift 2;;
    --dev)     DEV=1; shift;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

command -v docker >/dev/null || { echo "docker not found"; exit 1; }
docker compose version >/dev/null || { echo "docker compose v2 not found"; exit 1; }
command -v git-lfs >/dev/null || { echo "git-lfs not found: sudo apt-get install git-lfs"; exit 1; }
[[ "$(id -u)" -ne 0 ]] || { echo "Run as a normal user, not root"; exit 1; }

git lfs install
git submodule update --init --recursive
git submodule foreach --recursive 'git lfs pull || true'

# Verify the meshes are real files, not LFS pointers.
if grep -rIqs --include='*.stl' --include='*.STL' --include='*.dae' --include='*.obj' \
     'git-lfs.github.com/spec' clr_ws/src; then
  echo "ERROR: LFS pointer files remain in clr_ws/src. Check git-lfs and network access." >&2
  exit 1
fi

[[ -f .env ]] || cp .env.default .env
set_env() { grep -q "^$1=" .env && sed -i "s|^$1=.*|$1=$2|" .env || echo "$1=$2" >> .env; }
set_env USER_UID "$(id -u)"
set_env USER_GID "$(id -g)"
set_env VIDEO_GID  "$(getent group video  | cut -d: -f3 || echo 44)"
set_env RENDER_GID "$(getent group render | cut -d: -f3 || echo 109)"

files="compose.yaml"
case "$DISPLAY_MODE" in
  x11)   files+=":compose.x11.yaml";;
  novnc) files+=":compose.novnc.yaml";;
  web)   files+=":compose.web.yaml";;
  *) echo "--display must be x11, novnc or web"; exit 1;;
esac
case "$GPU" in
  none)   ;;
  nvidia) files+=":compose.gpu.yaml";;
  dri)    files+=":compose.dri.yaml";;
  *) echo "--gpu must be none, nvidia or dri"; exit 1;;
esac
[[ "$DEV" -eq 1 ]] && files+=":compose.dev.yaml"
set_env COMPOSE_FILE "$files"

echo "Setup done. COMPOSE_FILE=$files"
echo "Next: docker compose build"
