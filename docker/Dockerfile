# syntax=docker/dockerfile:1.7
# Builds the iMETRO clr_ws workspace (git submodule) into a self-contained image.
# Build context is the wrapper repo root (see compose.yaml).
#
# Targets: sim (default, workspace baked in)  |  vnc (sim + virtual display + noVNC)

ARG ROS_IMAGE=ros:jazzy

# ---------------------------------------------------------------- base ----
FROM ${ROS_IMAGE} AS base
ARG USERNAME=imetro
ARG USER_UID=1000
ARG USER_GID=1000
ENV DEBIAN_FRONTEND=noninteractive \
    USERNAME=${USERNAME} \
    WS=/home/${USERNAME}/ws

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git git-lfs ccache curl \
        python3-pip python3-colcon-common-extensions python3-colcon-mixin python3-rosdep python3-vcstool \
        mesa-utils libgl1 libglx-mesa0 libgl1-mesa-dri libegl1 \
        x11-utils x11-apps libxkbcommon-x11-0 \
        ros-${ROS_DISTRO}-rviz2 ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Non-root user matching the host UID/GID. The Ubuntu 24.04 base ships an
# "ubuntu" user at UID 1000, so remove whatever owns the UID first.
RUN set -eux; \
    if getent passwd "${USER_UID}" >/dev/null; then \
        userdel -r "$(getent passwd "${USER_UID}" | cut -d: -f1)"; \
    fi; \
    if ! getent group "${USER_GID}" >/dev/null; then groupadd -g "${USER_GID}" "${USERNAME}"; fi; \
    useradd -m -u "${USER_UID}" -g "${USER_GID}" -s /bin/bash "${USERNAME}"; \
    usermod -aG video "${USERNAME}"; \
    mkdir -p "${WS}" "/home/${USERNAME}/.ros/log"; \
    chown -R "${USER_UID}:${USER_GID}" "/home/${USERNAME}"

# Source ROS + workspace for login shells (docker compose exec ... bash -lc)
# and interactive shells.
RUN printf '%s\n' \
      '. /opt/ros/${ROS_DISTRO}/setup.bash' \
      '[ -f "${WS}/install/setup.bash" ] && . "${WS}/install/setup.bash"' \
      > /etc/profile.d/10-ros.sh \
    && echo '. /etc/profile.d/10-ros.sh' >> "/home/${USERNAME}/.bashrc"

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ----------------------------------------------------------- manifests ----
# Only package.xml / ignore markers, so the rosdep layer is not invalidated by
# source edits.
FROM base AS manifests
COPY clr_ws/src /src
RUN find /src -type f ! -name package.xml ! -name COLCON_IGNORE ! -name AMENT_IGNORE -delete \
    && find /src -type d -empty -delete

# ----------------------------------------------------------------- sim ----
FROM base AS sim
ARG USER_UID=1000
ARG USER_GID=1000
ARG BUILD_JOBS=4
WORKDIR ${WS}

COPY --from=manifests --chown=${USER_UID}:${USER_GID} /src ${WS}/src

# Python deps that rosdep does not cover (mirrors clr_ws/Dockerfile): the MJCF
# conversion script imports mujoco at launch, and nanobind is needed to build.
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_BREAK_SYSTEM_PACKAGES=1 pip3 install \
        mujoco==3.12.0 nanobind 'numpy<2' obj2mjcf pupil-apriltags \
        pycollada scipy trimesh viser

# System dependencies for every package in the workspace.
# PIP_BREAK_SYSTEM_PACKAGES: rosdep pip installs are PEP 668 "externally managed" on Ubuntu 24.04.
RUN export PIP_BREAK_SYSTEM_PACKAGES=1 \
    && apt-get update \
    && ( [ -f /etc/ros/rosdep/sources.list.d/20-default.list ] || rosdep init ) \
    && rosdep update --rosdistro "${ROS_DISTRO}" \
    && rosdep install --from-paths src --ignore-src -r -y --rosdistro "${ROS_DISTRO}" \
    && rm -rf /var/lib/apt/lists/*

USER ${USERNAME}
ENV CCACHE_DIR=/home/${USERNAME}/.ccache \
    CMAKE_C_COMPILER_LAUNCHER=ccache \
    CMAKE_CXX_COMPILER_LAUNCHER=ccache \
    MAKEFLAGS=-j${BUILD_JOBS} \
    CMAKE_BUILD_PARALLEL_LEVEL=${BUILD_JOBS}

# The workspace's colcon-defaults.yaml references mixins from the default index.
RUN colcon mixin add default https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml \
    && colcon mixin update default

# Build the (rarely changing) external packages first so edits to the clr_demos /
# clr_functional_tests packages do not recompile them.
COPY --chown=${USER_UID}:${USER_GID} clr_ws/config ${WS}/config
COPY --chown=${USER_UID}:${USER_GID} clr_ws/src/external ${WS}/src/external

RUN --mount=type=cache,target=/home/${USERNAME}/.ccache,uid=${USER_UID},gid=${USER_GID} \
    . /opt/ros/${ROS_DISTRO}/setup.sh && \
    export COLCON_DEFAULTS_FILE="${WS}/config/colcon-defaults.yaml" && \
    colcon build --base-paths src/external

COPY --chown=${USER_UID}:${USER_GID} clr_ws/src ${WS}/src

# Fail early if git-lfs did not fetch the real meshes (pointer files are text).
RUN if grep -rIqs --include='*.stl' --include='*.STL' --include='*.dae' --include='*.obj' \
        'git-lfs.github.com/spec' "${WS}/src"; then \
        echo "ERROR: LFS pointer files found. Run 'git lfs install && git lfs pull' in clr_ws and its submodules, then rebuild." >&2; \
        exit 1; \
    fi

RUN --mount=type=cache,target=/home/${USERNAME}/.ccache,uid=${USER_UID},gid=${USER_GID} \
    . /opt/ros/${ROS_DISTRO}/setup.sh && \
    export COLCON_DEFAULTS_FILE="${WS}/config/colcon-defaults.yaml" && \
    colcon build --packages-skip-build-finished

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]

# ----------------------------------------------------------------- vnc ----
FROM sim AS vnc
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify openbox \
    && rm -rf /var/lib/apt/lists/*
COPY docker/entrypoint-vnc.sh /entrypoint-vnc.sh
RUN chmod +x /entrypoint-vnc.sh
USER ${USERNAME}
ENV DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1
EXPOSE 6080
ENTRYPOINT ["/entrypoint-vnc.sh"]
CMD ["sleep", "infinity"]
