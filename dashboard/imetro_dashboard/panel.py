"""The GUI panel: a read-only status section now, with a slot for control buttons."""

from __future__ import annotations

import viser

from imetro_dashboard.actions import Actions
from imetro_dashboard.cell import Snapshot

STALE_S = 1.0


class Panel:
    def __init__(self, server: viser.ViserServer, actions: Actions) -> None:
        self._server = server
        self._actions = actions
        gui = server.gui
        with gui.add_folder("Status"):
            self._conn = gui.add_markdown("Waiting for the cell…")
        with gui.add_folder("Joints", expand_by_default=False):
            self._joints = gui.add_markdown("")
        self._controls = gui.add_folder("Controls")
        self._buttons: dict[str, viser.GuiButtonHandle] = {}
        self._status = None
        self._build_controls()

    def _build_controls(self) -> None:
        gui = self._server.gui
        with self._controls:
            actions = self._actions.all()
            if not actions:
                gui.add_markdown("_Read-only: no controls enabled._")
                return
            for action in actions:
                button = gui.add_button(action.label)
                button.on_click(lambda _e, key=action.key: self._actions.trigger(key))
                self._buttons[action.key] = button
            self._status = gui.add_markdown("")

    def update(self, snap: Snapshot, scene_ready: bool) -> None:
        """Refresh text and enable-state; call at a few Hz from the render thread."""
        if snap.description is None:
            desc = "waiting for `/robot_description`"
        else:
            desc = "loaded" if scene_ready else "loading meshes…"
        if snap.joint_age_s is None:
            joints = "waiting for `/joint_states`"
        elif snap.joint_age_s > STALE_S:
            joints = f"**stale** ({snap.joint_age_s:.0f} s ago)"
        else:
            joints = f"live, {snap.joint_rate_hz:.0f} Hz"
        sim = "—" if snap.sim_time_s is None else f"{snap.sim_time_s:.1f} s"
        rtf = "—" if snap.real_time_factor is None else f"{snap.real_time_factor:.2f}×"
        self._conn.content = (
            f"- Description: {desc}\n- Joint states: {joints}\n- Sim time: {sim}\n- Real-time factor: {rtf}"
        )
        rows = "\n".join(f"| {n} | {v:+.3f} |" for n, v in sorted(snap.joints.items()))
        self._joints.content = f"| joint | position |\n|---|---|\n{rows}" if rows else "_no data_"
        for action in self._actions.all():
            self._buttons[action.key].disabled = not action.enabled(snap)
        if self._status is not None:
            self._status.content = "\n".join(f"- {k}: {v}" for k, v in self._actions.status.items())
