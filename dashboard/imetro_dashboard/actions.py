"""Runs operator actions off the GUI and render threads and tracks their status.

Click handlers must return quickly, and a ROS call can block for seconds, so every action goes
through ``Actions.submit``: it runs the callable on a worker thread, refuses a second copy of
the same key while one is running, and records the outcome (an exception becomes a message the
operator sees rather than a dead button). The commands themselves live in ``commands.py``.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)


class Actions:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: set[str] = set()
        self._status: dict[str, str] = {}

    def submit(self, key: str, fn: Callable[[], str | None]) -> bool:
        """Run ``fn`` on a worker. Returns False if ``key`` is already running."""
        with self._lock:
            if key in self._running:
                return False
            self._running.add(key)
            self._status[key] = "running…"
        threading.Thread(target=self._run, args=(key, fn), name=f"action-{key}", daemon=True).start()
        return True

    def _run(self, key: str, fn: Callable[[], str | None]) -> None:
        try:
            outcome = fn() or "done"
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator, not swallowed
            LOGGER.exception("action %s failed", key)
            outcome = f"failed: {exc}"
        with self._lock:
            self._running.discard(key)
            self._status[key] = outcome

    def status(self) -> dict[str, str]:
        with self._lock:
            return dict(self._status)

    def busy(self, key: str) -> bool:
        with self._lock:
            return key in self._running
