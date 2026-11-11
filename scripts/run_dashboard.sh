#!/usr/bin/env bash
# Start the web dashboard (read-only viewer). Run after run_sim.sh. Usage: run_dashboard.sh [--port N]
set -euo pipefail
source "$(dirname "$0")/_common.sh"
docker compose exec sim bash -lc "python3 -m imetro_dashboard $*"
