"""The control widgets: motion sliders for the arm, rail and lift, and the environment editor.

Widgets only collect values and submit actions; nothing here talks to ROS directly. Sliders start
from the live pose the first time joint states arrive, and "Sync" re-reads it.
"""

from __future__ import annotations

import viser

from imetro_dashboard.actions import Actions
from imetro_dashboard.cell import Cell, Snapshot
from imetro_dashboard.commands import FINGER_JOINTS, GROUPS, Commands


def _step(name: str, lo: float, hi: float) -> float:
    return 0.001 if (hi - lo) <= 3.0 and name in ("vention_rail_base_to_carriage", "ewellix_lift_lower_to_higher") else 0.01


class Controls:
    def __init__(
        self,
        server: viser.ViserServer,
        cell: Cell,
        commands: Commands,
        actions: Actions,
        limits: dict[str, tuple[float, float, float]],
        joint_names: list[str],
    ) -> None:
        self._cell, self._cmd, self._actions, self._limits = cell, commands, actions, limits
        gui = server.gui
        robot_joints = {j for g in GROUPS.values() for j in g.joints} | set(FINGER_JOINTS)
        env_joints = sorted(j for j in joint_names if j not in robot_joints)

        self._sliders: dict[str, viser.GuiInputHandle] = {}
        self._go: dict[str, viser.GuiButtonHandle] = {}
        self._synced = False

        with gui.add_folder("Robot control"):
            self._speed = gui.add_slider("Speed", min=0.1, max=1.0, step=0.05, initial_value=0.5)
            for key, group in GROUPS.items():
                with gui.add_folder(group.label, expand_by_default=key == "arm"):
                    for name in group.joints:
                        lo, hi, _ = limits[name]
                        self._sliders[name] = gui.add_slider(
                            name.replace("_joint", ""), min=lo, max=hi, step=_step(name, lo, hi), initial_value=0.0
                        )
                    go = gui.add_button(f"Move {group.label.lower()}")
                    go.on_click(lambda _e, key=key: self._move(key))
                    self._go[key] = go
            self._sync = gui.add_button("Sync sliders to robot")
            self._sync.on_click(lambda _e: self._sync_sliders(self._cell.snapshot()))
            self._stop = gui.add_button("Stop", color="red")
            self._stop.on_click(lambda _e: self._actions.submit("stop", self._cmd.stop))

        with gui.add_folder("Environment", expand_by_default=False):
            gui.add_markdown(
                "Sets a door, handle, latch or drawer inside the simulation, e.g. to open a "
                "cabinet before the robot reaches for it. Blocked while the robot moves."
            )
            first = env_joints[0] if env_joints else ""
            self._env_joint = gui.add_dropdown("Joint", options=tuple(env_joints) or ("",), initial_value=first)
            lo, hi, _ = limits.get(first, (0.0, 1.0, 0.0))
            self._env_value = gui.add_slider("Value", min=lo, max=hi, step=0.005, initial_value=lo)
            self._env_apply = gui.add_button("Apply")
            self._env_min = gui.add_button("To minimum")
            self._env_max = gui.add_button("To maximum")
            self._reset = gui.add_button("Reset environment", color="orange")
            self._env_joint.on_update(lambda _e: self._pick_env_joint())
            self._env_apply.on_click(lambda _e: self._set_env(self._env_value.value))
            self._env_min.on_click(lambda _e: self._set_env(self._limits[self._env_joint.value][0]))
            self._env_max.on_click(lambda _e: self._set_env(self._limits[self._env_joint.value][1]))
            self._reset.on_click(lambda _e: self._actions.submit("environment", self._cmd.reset_world))

        with gui.add_folder("Last action"):
            self._status = gui.add_markdown("_none yet_")

    # -- handlers (GUI thread: submit and return) ------------------------------------------
    def _move(self, key: str) -> None:
        targets = {j: self._sliders[j].value for j in GROUPS[key].joints}
        self._actions.submit(f"move-{key}", lambda: self._cmd.move(key, targets, self._speed.value))

    def _set_env(self, value: float) -> None:
        joint = self._env_joint.value
        lo, hi, _ = self._limits.get(joint, (0.0, 1.0, 0.0))
        self._env_value.value = min(max(float(value), lo), hi)
        self._actions.submit("environment", lambda: self._cmd.set_environment(joint, float(value)))

    def _pick_env_joint(self) -> None:
        lo, hi, _ = self._limits.get(self._env_joint.value, (0.0, 1.0, 0.0))
        self._env_value.min, self._env_value.max = lo, hi
        current = self._cell.snapshot().joints.get(self._env_joint.value, lo)
        self._env_value.value = min(max(current, lo), hi)

    def _sync_sliders(self, snap: Snapshot) -> None:
        for name, slider in self._sliders.items():
            if name in snap.joints:
                lo, hi, _ = self._limits[name]
                slider.value = min(max(snap.joints[name], lo), hi)
        self._pick_env_joint()

    # -- render thread ---------------------------------------------------------------------
    def update(self, snap: Snapshot) -> None:
        if not self._synced and all(j in snap.joints for j in self._sliders):
            self._sync_sliders(snap)
            self._synced = True
        moving = self._cmd.moving()
        for key, button in self._go.items():
            button.disabled = not self._cmd.motion_ready(key) or self._actions.busy(f"move-{key}")
        self._stop.disabled = not moving
        env_ok = self._cmd.environment_ready() and not moving and not self._actions.busy("environment")
        for button in (self._env_apply, self._env_min, self._env_max, self._reset):
            button.disabled = not env_ok
        status = self._actions.status()
        self._status.content = "\n".join(f"- **{k}**: {v}" for k, v in status.items()) or "_none yet_"
