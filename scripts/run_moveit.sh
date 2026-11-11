#!/usr/bin/env bash
# Launch MoveIt for the running simulation (run in a second terminal).
# RViz is off by default (use the web dashboard); RVIZ=true ./scripts/run_moveit.sh to open it.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
docker compose exec sim bash -lc \
  "ros2 launch clr_moveit_config clr_moveit.launch.py include_mockups_in_description:=true use_sim_time:=true launch_rviz:=${RVIZ:-false}"
