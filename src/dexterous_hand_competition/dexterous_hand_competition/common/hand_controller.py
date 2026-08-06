"""Inspire Hand abstraction with dry-run as the default."""

from collections.abc import Callable
import time

from .contracts import ActionResult, ResultCode


HandCommandSink = Callable[[str, list[float]], bool]
SafetyCheck = Callable[[], bool]


class HandController:
    def __init__(
        self,
        poses: dict[str, list[float]],
        command_sink: HandCommandSink | None = None,
        safety_check: SafetyCheck | None = None,
        dry_run: bool = True,
    ):
        self.poses = poses
        self.command_sink = command_sink
        self.safety_check = safety_check or (lambda: True)
        self.dry_run = bool(dry_run)

    @staticmethod
    def _validate_values(values: list[float]) -> ActionResult:
        if len(values) != 6:
            return ActionResult.failure(
                ResultCode.INVALID_ARGUMENT,
                f'expected 6 hand ratios, got {len(values)}',
            )
        if any(value < 0.0 or value > 1.0 for value in values):
            return ActionResult.failure(
                ResultCode.INVALID_ARGUMENT,
                'hand ratios must be inside verified range [0, 1]',
            )
        return ActionResult.success('hand ratios validated')

    def move_hand_pose(
        self,
        name: str,
        timeout_sec: float = 3.0,
    ) -> ActionResult:
        started = time.monotonic()
        values = self.poses.get(name)
        if values is None or not values:
            return ActionResult.failure(
                ResultCode.NOT_CALIBRATED, f'hand pose not calibrated: {name}'
            )
        valid = self._validate_values(values)
        if not valid.ok:
            return valid
        if timeout_sec <= 0.0:
            return ActionResult.failure(
                ResultCode.INVALID_ARGUMENT, 'timeout must be positive'
            )
        if not self.safety_check():
            return ActionResult.failure(
                ResultCode.SAFETY_LOCKED, 'safety latch is not clear'
            )
        if self.dry_run:
            return ActionResult.dry_run(
                f'would move hand to {name}', time.monotonic() - started
            )
        if self.command_sink is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING,
                'real Inspire Hand service adapter is not implemented',
            )
        if not self.command_sink(name, values):
            return ActionResult.failure(
                ResultCode.SDK_REJECTED,
                f'hand command rejected: {name}',
                time.monotonic() - started,
            )
        return ActionResult.success(name, time.monotonic() - started)

