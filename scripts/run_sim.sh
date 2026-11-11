#!/usr/bin/env bash
# Launch the iMETRO CLR environment. Usage: run_sim.sh [mujoco|mujoco-gui|kinematic]  (mujoco is headless; mockup doors/handles are simulated so the dashboard can set them)
set -euo pipefail
source "$(dirname "$0")/_common.sh"
case "${1:-mujoco}" in
  mujoco)     LAUNCH="ros2 launch clr_mujoco_config clr_mujoco.launch.py headless:=true include_mockup_state_interfaces:=true";;
  mujoco-gui) LAUNCH="ros2 launch clr_mujoco_config clr_mujoco.launch.py include_mockup_state_interfaces:=true";;
  kinematic) LAUNCH="ros2 launch clr_deploy clr_sim.launch.py";;
  *) echo "Usage: $0 [mujoco|mujoco-gui|kinematic]"; exit 1;;
esac
docker compose exec sim bash -lc "$LAUNCH"
