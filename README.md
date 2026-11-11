# imetro-sandbox

Self-contained Docker setup for NASA JSC's iMETRO simulation (the `clr_ws`
workspace: UR10e on a column lift and Vention rail, MuJoCo dynamic sim, MoveIt,
hatch / bench mockups). `clr_ws` is included as a pinned git submodule; nothing
upstream is modified.

## Quick start

```bash
# Host needs: git, git-lfs, docker (with compose v2)
git init -b main && git lfs install
git submodule add -b jazzy-devel https://github.com/NASA-JSC-Robotics/clr_ws clr_ws
git submodule update --init --recursive

chmod +x scripts/*.sh docker/*.sh
./scripts/setup.sh --display x11 --gpu none     # writes .env and COMPOSE_FILE
docker compose build                            # first build is slow (MoveIt, MuJoCo bridge)
./scripts/smoke_test.sh                         # package + LFS checks

./scripts/run_sim.sh                            # terminal 1: MuJoCo + controllers
./scripts/run_moveit.sh                         # terminal 2: MoveIt + RViz
```

## Options (pick at setup time)

| Need | Flag |
|---|---|
| Host display (X11 / XWayland) | `--display x11` (default) |
| Browser dashboard (viser 3D view + status, MuJoCo headless) | `--display web` then open http://localhost:8080 |
| Browser display, no host X needed (software rendering) | `--display novnc` then open http://localhost:6080/vnc.html |
| NVIDIA GPU (needs NVIDIA Container Toolkit) | `--gpu nvidia` |
| Intel / AMD GPU | `--gpu dri` |
| Edit `clr_ws/src` on the host, rebuild in the container | `--dev` |

Re-run `setup.sh` with different flags any time, then `docker compose up -d --build`.
Kinematic-only simulation: `./scripts/run_sim.sh kinematic`.

## Web dashboard

```bash
./scripts/setup.sh --display web && docker compose up -d --build
./scripts/run_sim.sh          # terminal 1: MuJoCo, headless
./scripts/run_dashboard.sh    # terminal 2: dashboard, then open http://localhost:8080
```

The robot, lift, rail and mockups are posed live from `/joint_states`, with status (description,
joint-state rate, sim time, real-time factor). The code is in `dashboard/` and is bind-mounted into
the container, so edits only need a restart of `run_dashboard.sh`.

Controls (side panel):
- **Robot control**: sliders and a Move button each for the arm, rail and lift (limits from the
  URDF, speed slider, Stop). These send `FollowJointTrajectory` goals to the active controllers.
- **Environment**: pick a door, handle, latch or drawer and set its angle or travel inside MuJoCo,
  e.g. open a cabinet before the robot reaches for it. This uses MuJoCo's `reset_world` service,
  so the sim must run with mockup state interfaces (`run_sim.sh` does this). Blocked while the
  robot moves. "Reset environment" returns doors and objects to their initial state; the robot
  keeps its last commanded pose.

New commands go in `commands.py` (ROS calls) and `controls.py` (widgets); `actions.py` runs them on
worker threads so the GUI never blocks.
`./scripts/run_sim.sh mujoco-gui` gives the MuJoCo window; MoveIt's RViz is off unless
`RVIZ=true ./scripts/run_moveit.sh`. Use a GPU-accelerated browser: the scene is ~365k triangles.

## Reproducibility and offline use

- The submodule SHA is the pin. Update deliberately with
  `git -C clr_ws pull && git add clr_ws`, then rebuild and run the smoke test.
- Pin the base image digest via `ROS_IMAGE` in `.env`.
- After building, `./scripts/save_image.sh` writes a tarball; restore elsewhere
  with `docker load < dist/imetro-sandbox-latest.tar.gz`.
- Building itself needs the network (apt, rosdep, ROS packages).

## Assumptions to verify (I could not read upstream's Dockerfile)

1. `clr_ws/src` and `clr_ws/config` exist (config/colcon-defaults.yaml is optional).
2. `rosdep install` resolves every dependency. If the build fails on a missing
   package, compare with `clr_ws/Dockerfile` and add what it installs to the
   `apt-get install` list in `docker/Dockerfile`.
3. Launch files and package names (`clr_mujoco_config`, `clr_moveit_config`,
   `clr_deploy`) are taken from upstream's README.
4. The smoke test's `--launch` check assumes the default controller manager name.

## Troubleshooting

- Meshes missing or "LFS pointer" error: `git lfs install`, then
  `git submodule foreach --recursive 'git lfs pull'`.
- No window appears: confirm `echo $DISPLAY` on the host and `xhost +local:docker`.
- Slow rendering: use `--gpu nvidia` or `--gpu dri`; see clr_ws/docs/TROUBLESHOOTING.md.
- Build runs out of memory: lower `BUILD_JOBS` in `.env`.
