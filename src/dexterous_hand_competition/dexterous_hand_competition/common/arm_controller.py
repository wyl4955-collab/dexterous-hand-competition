"""Safe arm-control abstraction with dry-run as the default.

TODO_REAL_ROBOT: connect ``command_sink`` to the verified Tianyi arm command
message only after limits, directions, units and feedback are confirmed.
"""

from collections.abc import Callable
import math
import time

from .contracts import ActionResult, ResultCode
from .robot_state import RobotState


CommandSink = Callable[[dict[int, float]], bool]
SafetyCheck = Callable[[], bool]


class ArmController:
    def __init__(
        self,
        state: RobotState,
        joint_limits: dict[int, tuple[float, float]],
        named_poses: dict[str, dict[int, float]],
        command_sink: CommandSink | None = None,
        safety_check: SafetyCheck | None = None,
        dry_run: bool = True,
        control_hz: float = 50.0,
    ):
        self.state = state
        self.joint_limits = joint_limits
        self.named_poses = named_poses
        self.command_sink = command_sink
        self.safety_check = safety_check or (lambda: True)
        self.dry_run = bool(dry_run)
        self.control_hz = max(1.0, float(control_hz))

    def _validate_target(self, target: dict[int, float]) -> ActionResult:
        if not target:
            return ActionResult.failure(
                ResultCode.INVALID_ARGUMENT, 'empty joint target'
            )
        for joint_id, position in target.items():
            if not math.isfinite(float(position)):
                return ActionResult.failure(
                    ResultCode.INVALID_ARGUMENT,
                    f'joint {joint_id} target is not finite',
                )
            if joint_id not in self.joint_limits:
                return ActionResult.failure(
                    ResultCode.OUT_OF_LIMITS,
                    f'joint {joint_id} has no verified limit',
                )
            lower, upper = self.joint_limits[joint_id]
            if position < lower or position > upper:
                return ActionResult.failure(
                    ResultCode.OUT_OF_LIMITS,
                    f'joint {joint_id} target {position:.4f} outside '
                    f'[{lower:.4f}, {upper:.4f}]',
                )
        return ActionResult.success('target validated')

    def move_to_joints(
        self,
        target: dict[int, float],
        duration_sec: float,
        timeout_sec: float,
    ) -> ActionResult:
        started = time.monotonic()
        validated = self._validate_target(target)
        if not validated.ok:
            return validated
        if duration_sec <= 0.0 or timeout_sec <= 0.0:
            return ActionResult.failure(
                ResultCode.INVALID_ARGUMENT,
                'duration and timeout must be positive',
            )
        if not self.safety_check():
            return ActionResult.failure(
                ResultCode.SAFETY_LOCKED, 'safety latch is not clear'
            )

        if self.dry_run:
            return ActionResult.dry_run(
                f'would move {len(target)} joints in {duration_sec:.2f}s',
                time.monotonic() - started,
            )

        if self.command_sink is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING,
                'real SDK arm command adapter is not implemented',
            )
        if not self.state.feedback_is_fresh():
            return ActionResult.failure(
                ResultCode.NO_FEEDBACK, 'joint feedback is missing or stale'
            )

        current = {
            joint_id: self.state.get_joint_position(joint_id)
            for joint_id in target
        }
        if any(value is None for value in current.values()):
            return ActionResult.failure(
                ResultCode.NO_FEEDBACK, 'one or more joint positions are missing'
            )

        steps = max(2, int(duration_sec * self.control_hz))
        period = 1.0 / self.control_hz
        for step in range(1, steps + 1):
            if not self.safety_check():
                return ActionResult.failure(
                    ResultCode.SAFETY_LOCKED,
                    'safety latch triggered during motion',
                    time.monotonic() - started,
                )
            if time.monotonic() - started > timeout_sec:
                return ActionResult.failure(
                    ResultCode.TIMEOUT,
                    'motion timed out',
                    time.monotonic() - started,
                )
            ratio = step / steps
            smooth = ratio * ratio * (3.0 - 2.0 * ratio)
            command = {
                joint_id: float(current[joint_id])
                + (target[joint_id] - float(current[joint_id])) * smooth
                for joint_id in target
            }
            if not self.command_sink(command):
                return ActionResult.failure(
                    ResultCode.SDK_REJECTED,
                    'SDK rejected arm command',
                    time.monotonic() - started,
                )
            time.sleep(period)

        return ActionResult.success(
            'motion commands sent', time.monotonic() - started
        )

    def move_named_pose(
        self,
        name: str,
        timeout_sec: float = 10.0,
    ) -> ActionResult:
        target = self.named_poses.get(name)
        if target is None:
            return ActionResult.failure(
                ResultCode.NOT_CALIBRATED, f'named pose not found: {name}'
            )
        return self.move_to_joints(target, duration_sec=3.0, timeout_sec=timeout_sec)

    def stop_motion(self, reason: str):
        # TODO_REAL_ROBOT: use the verified SDK stop/hold mechanism. Do not
        # publish an unverified neutral pose here.
        _ = reason

