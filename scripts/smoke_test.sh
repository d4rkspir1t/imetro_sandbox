#!/usr/bin/env bash
# Checks the image. Add --launch to also start the MuJoCo sim (needs a display).
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
check() { if "$@"; then echo "PASS: ${*: -1}"; else echo "FAIL: ${*: -1}"; fail=1; fi; }
EXEC=(docker compose exec -T sim bash -lc)

docker compose up -d

for pkg in clr_deploy clr_mujoco_config clr_moveit_config mujoco_ros2_control; do
  check "${EXEC[@]}" "ros2 pkg prefix $pkg >/dev/null"
done
check "${EXEC[@]}" '! grep -rIqs --include=*.stl --include=*.dae --include=*.obj "git-lfs.github.com/spec" "$WS/src"'

if [[ "${1:-}" == "--launch" ]]; then
  docker compose exec -T -d sim bash -lc 'ros2 launch clr_mujoco_config clr_mujoco.launch.py > /tmp/sim.log 2>&1'
  sleep 45
  check "${EXEC[@]}" 'ros2 control list_controllers | grep -q active'
  docker compose exec -T sim pkill -f clr_mujoco.launch || true
fi

[[ $fail -eq 0 ]] && echo "ALL CHECKS PASSED" || { echo "SOME CHECKS FAILED"; exit 1; }
