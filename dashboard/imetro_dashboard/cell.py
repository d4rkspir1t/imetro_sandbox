"""The ROS side: subscribes to the cell and keeps the latest state as a snapshot.

The dashboard is a viewer and a trigger, never the owner of cell state. Callbacks only swap
references under a lock (``/joint_states`` arrives at ~450 Hz); the render thread reads
``Cell.snapshot()`` at its own rate. The node and executor are exposed so ``actions.py`` can
add clients and publishers later without touching this module.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import String

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)


@dataclass(frozen=True)
class Snapshot:
    """An immutable copy of what the cell last told us."""

    description: str | None = None
    joints: dict[str, float] = field(default_factory=dict)
    joint_age_s: float | None = None  # wall seconds since the last /joint_states
    joint_rate_hz: float = 0.0
    sim_time_s: float | None = None
    real_time_factor: float | None = None


class Cell:
    """Connection to the running simulation."""

    def __init__(self, node_name: str = "imetro_dashboard") -> None:
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(node_name)
        self.executor = MultiThreadedExecutor(num_threads=2)
        self.executor.add_node(self.node)

        self._lock = threading.Lock()
        self._description: str | None = None
        self._joints: dict[str, float] = {}
        self._last_joint_wall: float | None = None
        self._joint_count = 0
        self._rate_mark = (time.monotonic(), 0)
        self._joint_rate = 0.0
        self._sim_time: float | None = None
        self._rtf_mark: tuple[float, float] | None = None
        self._rtf: float | None = None

        self.node.create_subscription(String, "/robot_description", self._on_description, LATCHED)
        self.node.create_subscription(JointState, "/joint_states", self._on_joints, 10)
        self.node.create_subscription(Clock, "/clock", self._on_clock, 10)

        self._thread = threading.Thread(target=self.executor.spin, name="ros-spin", daemon=True)
        self._thread.start()

    def _on_description(self, msg: String) -> None:
        with self._lock:
            self._description = msg.data

    def _on_joints(self, msg: JointState) -> None:
        joints = dict(zip(msg.name, msg.position, strict=False))
        with self._lock:
            self._joints.update(joints)
            self._last_joint_wall = time.monotonic()
            self._joint_count += 1

    def _on_clock(self, msg: Clock) -> None:
        with self._lock:
            self._sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9

    def snapshot(self) -> Snapshot:
        """Copy the current state; also refreshes the rate estimates (call at a few Hz)."""
        now = time.monotonic()
        with self._lock:
            t0, n0 = self._rate_mark
            if now - t0 >= 1.0:
                self._joint_rate = (self._joint_count - n0) / (now - t0)
                self._rate_mark = (now, self._joint_count)
            if self._sim_time is not None:
                if self._rtf_mark is None:
                    self._rtf_mark = (now, self._sim_time)
                elif now - self._rtf_mark[0] >= 1.0:
                    self._rtf = (self._sim_time - self._rtf_mark[1]) / (now - self._rtf_mark[0])
                    self._rtf_mark = (now, self._sim_time)
            age = None if self._last_joint_wall is None else now - self._last_joint_wall
            return Snapshot(
                description=self._description,
                joints=dict(self._joints),
                joint_age_s=age,
                joint_rate_hz=self._joint_rate,
                sim_time_s=self._sim_time,
                real_time_factor=self._rtf,
            )

    def close(self) -> None:
        self.executor.shutdown()
        self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
