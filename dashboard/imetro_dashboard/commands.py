"""What the dashboard can ask the cell to do. Blocking calls: run them via ``Actions.submit``.

- Motion: ``FollowJointTrajectory`` goals to the arm, rail and lift controllers.
- Environment: MuJoCo's ``reset_world`` service with per-joint overrides, the only way to set
  a door or handle's state inside the physics. It resets everything it is not told about, so
  ``set_environment`` re-states every joint at its current value and changes just the one asked.
  Needs the sim launched with ``include_mockup_state_interfaces:=true``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from mujoco_ros2_control_msgs.srv import ResetWorld
from rclpy.action import ActionClient
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from imetro_dashboard.cell import Cell

RESET_WORLD = "/mujoco_ros2_control_node/reset_world"
MIN_MOVE_S = 1.0
RESULT_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class Group:
    """A set of joints driven by one trajectory controller."""

    key: str
    label: str
    controller: str
    joints: tuple[str, ...]
    max_speed: float  # rad/s or m/s at speed scale 1.0; the URDF limit is used if lower


GROUPS = {
    g.key: g
    for g in (
        Group(
            "arm",
            "Arm",
            "joint_trajectory_controller",
            (
                "shoulder_pan_joint",
                "shoulder_lift_joint",
                "elbow_joint",
                "wrist_1_joint",
                "wrist_2_joint",
                "wrist_3_joint",
            ),
            1.0,
        ),
        Group("rail", "Rail", "rail_position_trajectory_controller", ("vention_rail_base_to_carriage",), 0.15),
        Group("lift", "Lift", "lift_position_trajectory_controller", ("ewellix_lift_lower_to_higher",), 0.05),
    )
}
FINGER_JOINTS = ("finger_1_joint",)


class Commands:
    def __init__(self, cell: Cell, limits: dict[str, tuple[float, float, float]]) -> None:
        """``limits`` maps joint name to (lower, upper, velocity) from the URDF."""
        self._cell = cell
        self._limits = limits
        self._clients = {
            k: ActionClient(cell.node, FollowJointTrajectory, f"/{g.controller}/follow_joint_trajectory")
            for k, g in GROUPS.items()
        }
        self._reset = cell.node.create_client(ResetWorld, RESET_WORLD)
        self._goals: dict[str, object] = {}

    # -- readiness, for enabling buttons -------------------------------------------------
    def motion_ready(self, key: str) -> bool:
        return self._clients[key].server_is_ready()

    def environment_ready(self) -> bool:
        return self._reset.service_is_ready()

    def moving(self) -> bool:
        return bool(self._goals)

    # -- motion --------------------------------------------------------------------------
    def move(self, key: str, targets: dict[str, float], speed_scale: float) -> str:
        """Drive a group to ``targets`` (clamped to limits) and wait for the result."""
        group, client = GROUPS[key], self._clients[key]
        if not client.wait_for_server(timeout_sec=2.0):
            return f"{group.label} controller is not available"
        current = self._cell.snapshot().joints
        goal_pos, travel = [], 0.0
        for name in group.joints:
            lo, hi, vel = self._limits.get(name, (-1e9, 1e9, group.max_speed))
            want = min(max(targets.get(name, current.get(name, 0.0)), lo), hi)
            goal_pos.append(want)
            speed = min(group.max_speed, vel) * max(speed_scale, 0.05)
            travel = max(travel, abs(want - current.get(name, want)) / speed)
        duration = max(travel, MIN_MOVE_S)

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory(joint_names=list(group.joints))
        sec = int(duration)
        goal.trajectory.points = [
            JointTrajectoryPoint(
                positions=goal_pos,
                time_from_start=Duration(sec=sec, nanosec=int((duration - sec) * 1e9)),
            )
        ]
        handle = self._wait(client.send_goal_async(goal), 5.0)
        if handle is None or not handle.accepted:
            return f"{group.label}: goal rejected"
        self._goals[key] = handle
        try:
            result = self._wait(handle.get_result_async(), duration + RESULT_TIMEOUT_S)
        finally:
            self._goals.pop(key, None)
        if result is None:
            return f"{group.label}: no result"
        code = result.result.error_code
        status = result.status  # 4 = succeeded, 5 = canceled
        if status == 5:
            return f"{group.label}: stopped"
        return f"{group.label}: reached target ({duration:.1f} s)" if code == 0 else f"{group.label}: failed (code {code})"

    def stop(self) -> str:
        """Cancel every active trajectory; the controllers hold the current position."""
        handles = list(self._goals.values())
        for handle in handles:
            handle.cancel_goal_async()
        return f"cancelled {len(handles)} motion(s)"

    # -- environment ---------------------------------------------------------------------
    def set_environment(self, joint: str, value: float) -> str:
        """Set one mockup joint (door, handle, latch, drawer) inside MuJoCo."""
        if self.moving():
            return "refused: the robot is moving (wait or press Stop)"
        lo, hi, _ = self._limits.get(joint, (-1e9, 1e9, 0.0))
        value = min(max(value, lo), hi)
        joints = self._cell.snapshot().joints
        if joint not in joints:
            return f"unknown joint {joint}"
        overrides = {**joints, joint: value}
        return self._call_reset(overrides, f"{joint} = {value:.3f}")

    def reset_world(self) -> str:
        """Doors, handles and objects back to their initial state. The controllers keep holding
        the robot at its last commanded pose, so it does not go home."""
        if self.moving():
            return "refused: the robot is moving (wait or press Stop)"
        return self._call_reset({}, "environment reset")

    def _call_reset(self, overrides: dict[str, float], done: str) -> str:
        if not self._reset.wait_for_service(timeout_sec=2.0):
            return "MuJoCo reset_world is not available"
        req = ResetWorld.Request()
        names = list(overrides)
        req.state_overrides.joint_states.name = names
        req.state_overrides.joint_states.position = [overrides[n] for n in names]
        req.state_overrides.joint_states.velocity = [0.0] * len(names)
        res = self._wait(self._reset.call_async(req), 10.0)
        if res is None:
            return "reset_world timed out"
        return done if res.success else f"failed: {res.message}"

    @staticmethod
    def _wait(future, timeout: float):
        end = time.monotonic() + timeout
        while not future.done():
            if time.monotonic() > end:
                return None
            time.sleep(0.02)
        return future.result()
