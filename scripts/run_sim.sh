#!/usr/bin/env bash
# Launch the iMETRO CLR environment. Usage: run_sim.sh [mujoco|kinematic]
set -euo pipefail
source "$(dirname "$0")/_common.sh"
case "${1:-mujoco}" in
  mujoco)    LAUNCH="ros2 launch clr_mujoco_config clr_mujoco.launch.py";;
  kinematic) LAUNCH="ros2 launch clr_deploy clr_sim.launch.py";;
  *) echo "Usage: $0 [mujoco|kinematic]"; exit 1;;
esac
docker compose exec sim bash -lc "$LAUNCH"
