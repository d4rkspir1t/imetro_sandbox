"""The GUI panel: read-only status and the live joint table. Controls live in ``controls.py``."""

from __future__ import annotations

import viser

from imetro_dashboard.cell import Snapshot

STALE_S = 1.0


class Panel:
    def __init__(self, server: viser.ViserServer) -> None:
        gui = server.gui
        with gui.add_folder("Status"):
            self._conn = gui.add_markdown("Waiting for the cell…")
        with gui.add_folder("Joints", expand_by_default=False):
            self._joints = gui.add_markdown("")

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
