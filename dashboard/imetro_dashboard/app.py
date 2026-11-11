"""Entry point: wires the cell, the scene and the panel together and runs the render loop."""

from __future__ import annotations

import argparse
import logging
import time

import viser

from imetro_dashboard.actions import Actions
from imetro_dashboard.cell import Cell
from imetro_dashboard.panel import Panel
from imetro_dashboard.scene import RobotScene

LOGGER = logging.getLogger("imetro_dashboard")

SCENE_HZ = 20.0
PANEL_HZ = 4.0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    cell = Cell()
    server = viser.ViserServer(host=args.host, port=args.port)
    server.scene.set_up_direction("+z")
    server.scene.add_grid("/grid", width=6.0, height=6.0, plane="xy")
    panel = Panel(server, Actions(cell, read_only=True))

    scene: RobotScene | None = None
    next_panel = 0.0
    LOGGER.info("dashboard on http://localhost:%d", args.port)
    try:
        while True:
            snap = cell.snapshot()
            if scene is None and snap.description is not None:
                try:
                    scene = RobotScene(server, snap.description)
                    LOGGER.info("robot loaded: %d actuated joints", len(scene.joint_names))
                except Exception:
                    LOGGER.exception("could not load the robot description")
                    time.sleep(2.0)
            if scene is not None:
                scene.pose(snap.joints)
            now = time.monotonic()
            if now >= next_panel:
                panel.update(snap, scene is not None)
                next_panel = now + 1.0 / PANEL_HZ
            time.sleep(1.0 / SCENE_HZ)
    except KeyboardInterrupt:
        pass
    finally:
        cell.close()
        server.stop()


if __name__ == "__main__":
    main()
