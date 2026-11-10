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
| Browser display, no host X needed (software rendering) | `--display novnc` then open http://localhost:6080/vnc.html |
| NVIDIA GPU (needs NVIDIA Container Toolkit) | `--gpu nvidia` |
| Intel / AMD GPU | `--gpu dri` |
| Edit `clr_ws/src` on the host, rebuild in the container | `--dev` |

Re-run `setup.sh` with different flags any time, then `docker compose up -d --build`.
Kinematic-only simulation: `./scripts/run_sim.sh kinematic`.

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
