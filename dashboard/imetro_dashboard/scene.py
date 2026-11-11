"""The 3D scene: the robot description loaded into viser and posed from joint states."""

from __future__ import annotations

import io
import logging
import os
from functools import lru_cache
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

import numpy as np
import viser
import yourdfpy
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from viser.extras import ViserUrdf

LOGGER = logging.getLogger(__name__)

ROBOT_ROOT = "/robot"

# 20 m room planes drawn at 7.5% alpha in RViz. viser draws them opaque, and the ceiling then
# hides the whole scene from the default camera. Their links stay (TF is unchanged); only the
# visuals are dropped.
HIDDEN_VISUALS = ("ground_plane", "room_ceiling")


@lru_cache(maxsize=None)
def _share(package: str) -> str | None:
    try:
        return get_package_share_directory(package)
    except PackageNotFoundError:
        LOGGER.warning("package %r not found; its meshes will be skipped", package)
        return None


def resolve_uri(fname: str) -> str:
    """Map ``package://`` and ``file://`` mesh URIs to local paths."""
    parsed = urlparse(fname)
    if parsed.scheme == "package":
        share = _share(parsed.netloc)
        return os.path.join(share, unquote(parsed.path.lstrip("/"))) if share else fname
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return fname


def strip_visuals(description: str, links: tuple[str, ...] = HIDDEN_VISUALS) -> str:
    """Remove the visuals of the named links from a URDF string."""
    root = ElementTree.fromstring(description)
    for link in root.iter("link"):
        if link.get("name") in links:
            for visual in link.findall("visual"):
                link.remove(visual)
    return ElementTree.tostring(root, encoding="unicode")


class RobotScene:
    """The robot (and any mockups in its description) drawn in a viser server."""

    def __init__(self, server: viser.ViserServer, description: str) -> None:
        self._urdf = yourdfpy.URDF.load(
            io.StringIO(strip_visuals(description)),
            filename_handler=resolve_uri,
            build_collision_scene_graph=False,
            load_collision_meshes=False,
        )
        self._viser = ViserUrdf(server, self._urdf, root_node_name=ROBOT_ROOT)
        self._names = list(self._urdf.actuated_joint_names)
        self._cfg = np.zeros(len(self._names))
        self._applied: np.ndarray | None = None

    @property
    def joint_names(self) -> list[str]:
        return self._names

    def pose(self, joints: dict[str, float]) -> None:
        """Move the robot; an unchanged pose costs nothing to send."""
        for i, name in enumerate(self._names):
            if name in joints:
                self._cfg[i] = joints[name]
        if self._applied is None or not np.array_equal(self._cfg, self._applied):
            self._viser.update_cfg(self._cfg)
            self._applied = self._cfg.copy()
