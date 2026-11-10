# Sourced by run_*.sh
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "${COMPOSE_FILE:-}$(grep -s '^COMPOSE_FILE=' .env)" == *x11* ]] && command -v xhost >/dev/null; then
  xhost +local:docker >/dev/null || true
fi
docker compose up -d
