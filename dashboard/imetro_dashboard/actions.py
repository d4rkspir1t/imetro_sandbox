"""Operator actions: the extension point for control buttons.

Read-only for now: nothing is registered, so the panel shows no controls. To add one later,
register an ``Action`` (e.g. a MoveIt goal or a controller switch) against the ``Cell``'s node:

    actions.register(Action("home", "Go home", run=lambda: send_named_pose("home"),
                            enabled=lambda snap: snap.joint_age_s is not None))

Contract the panel relies on: ``run`` is called on a worker thread, never the render thread,
so it may block on ROS futures; exceptions are caught and surfaced as the action's status.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from imetro_dashboard.cell import Cell, Snapshot

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    run: Callable[[], str | None]  # returns an optional status message
    enabled: Callable[[Snapshot], bool] = lambda _snap: True
    group: str = "Controls"


class Actions:
    """Registry plus a worker that runs actions off the GUI/render threads."""

    def __init__(self, cell: Cell, read_only: bool = True) -> None:
        self.cell = cell
        self.read_only = read_only
        self._actions: dict[str, Action] = {}
        self.status: dict[str, str] = {}

    def register(self, action: Action) -> None:
        self._actions[action.key] = action

    def all(self) -> list[Action]:
        return [] if self.read_only else list(self._actions.values())

    def trigger(self, key: str) -> None:
        action = self._actions[key]
        threading.Thread(target=self._run, args=(action,), name=f"action-{key}", daemon=True).start()

    def _run(self, action: Action) -> None:
        self.status[action.key] = "running"
        try:
            self.status[action.key] = action.run() or "done"
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator, not swallowed
            LOGGER.exception("action %s failed", action.key)
            self.status[action.key] = f"failed: {exc}"
