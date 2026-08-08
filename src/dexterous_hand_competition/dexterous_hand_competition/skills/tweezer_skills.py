"""High-level tweezer skills composed only from public A/C1 interfaces."""

from collections.abc import Callable
from dataclasses import dataclass
import math

from ..common.contracts import ActionResult, BeanCandidate, ResultCode


@dataclass(frozen=True)
class TweezerSkillConfig:
    motion_duration_sec: float = 3.0
    motion_timeout_sec: float = 10.0
    hand_timeout_sec: float = 3.0
    refine_duration_sec: float = 1.0


class TweezerSkills:
    """C2 skill layer.

    ``arm``, ``hand`` and ``workspace_mapper`` are injected adapters.  This
    class never reads their private attributes and never guesses SDK message
    types or joint IDs.
    """

    def __init__(
        self,
        arm,
        hand,
        workspace_mapper=None,
        safety_check: Callable[[], bool] | None = None,
        hand_feedback_check: Callable[[], bool] | None = None,
        tweezer_verifier: Callable[[], bool | None] | None = None,
        config: TweezerSkillConfig | None = None,
    ):
        self.arm = arm
        self.hand = hand
        self.workspace_mapper = workspace_mapper
        self.safety_check = safety_check or (lambda: True)
        self.hand_feedback_check = hand_feedback_check
        self.tweezer_verifier = tweezer_verifier
        self.config = config or TweezerSkillConfig()

    def _call(
        self,
        label: str,
        action: Callable[[], ActionResult],
    ) -> ActionResult:
        if not self.safety_check():
            return ActionResult.failure(
                ResultCode.SAFETY_LOCKED,
                f'{label} blocked because command permission is false',
            )
        if self.hand_feedback_check is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING,
                f'{label} blocked because hand feedback is not connected',
            )
        if not self.hand_feedback_check():
            return ActionResult.failure(
                ResultCode.NO_FEEDBACK,
                f'{label} blocked because hand feedback is stale',
            )
        try:
            result = action()
        # Convert all adapter exceptions to the stable cross-module contract.
        except Exception as exc:
            return ActionResult.failure(
                ResultCode.INTERNAL_ERROR, f'{label} raised: {exc}'
            )
        if not isinstance(result, ActionResult):
            return ActionResult.failure(
                ResultCode.INTERNAL_ERROR,
                f'{label} returned {type(result).__name__}, '
                'expected ActionResult',
            )
        if not result.ok:
            return ActionResult.failure(
                result.code,
                f'{label} failed: {result.message}',
                result.elapsed_sec,
            )
        return result

    def _sequence(
        self,
        name: str,
        steps: list[tuple[str, Callable[[], ActionResult]]],
    ) -> ActionResult:
        simulated = False
        elapsed = 0.0
        for label, action in steps:
            result = self._call(label, action)
            elapsed += result.elapsed_sec
            if not result.ok:
                return result
            simulated = simulated or result.code == ResultCode.DRY_RUN
        if simulated:
            return ActionResult.dry_run(f'{name} simulated', elapsed)
        return ActionResult.success(f'{name} complete', elapsed)

    def grasp_tweezer(self) -> ActionResult:
        return self._sequence(
            'grasp_tweezer',
            [
                (
                    'hand tweezers_pregrasp',
                    lambda: self.hand.move_hand_pose(
                        'tweezers_pregrasp', self.config.hand_timeout_sec
                    ),
                ),
                (
                    'arm tweezer_pregrasp',
                    lambda: self.arm.move_named_pose(
                        'tweezer_pregrasp', self.config.motion_timeout_sec
                    ),
                ),
                (
                    'arm tweezer_grasp',
                    lambda: self.arm.move_named_pose(
                        'tweezer_grasp', self.config.motion_timeout_sec
                    ),
                ),
                (
                    'hand tweezers_hold',
                    lambda: self.hand.move_hand_pose(
                        'tweezers_hold', self.config.hand_timeout_sec
                    ),
                ),
            ],
        )

    def ensure_tweezer_held(self) -> ActionResult:
        if not self.safety_check():
            return ActionResult.failure(
                ResultCode.SAFETY_LOCKED, 'tweezer verification blocked'
            )
        if self.hand_feedback_check is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING,
                'hand feedback freshness check is not connected',
            )
        if not self.hand_feedback_check():
            return ActionResult.failure(
                ResultCode.NO_FEEDBACK, 'hand feedback is missing or stale'
            )
        if self.tweezer_verifier is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING,
                'tweezer-held verifier is not connected',
            )
        try:
            held = self.tweezer_verifier()
        except Exception as exc:
            return ActionResult.failure(
                ResultCode.INTERNAL_ERROR, f'tweezer verifier raised: {exc}'
            )
        if held is True:
            return ActionResult.success('tweezers verified as held')
        if held is None:
            return ActionResult.failure(
                ResultCode.NO_FEEDBACK, 'tweezer-held result is unavailable'
            )
        return ActionResult.failure(
            ResultCode.SDK_REJECTED, 'tweezers are not securely held'
        )

    @staticmethod
    def _valid_candidate(candidate: BeanCandidate | None) -> bool:
        if (
            not isinstance(candidate, BeanCandidate)
            or candidate.target_id <= 0
        ):
            return False
        try:
            return all(
                math.isfinite(float(value))
                for value in (
                    candidate.table_x_m,
                    candidate.table_y_m,
                    candidate.confidence,
                )
            )
        except (TypeError, ValueError):
            return False

    def move_to_bean(
        self,
        candidate: BeanCandidate | None,
        layer: str,
        duration_sec: float | None = None,
    ) -> ActionResult:
        if not self._valid_candidate(candidate):
            return ActionResult.failure(
                ResultCode.VISION_INVALID, 'bean table position is invalid'
            )
        assert candidate is not None
        if self.workspace_mapper is None:
            return ActionResult.failure(
                ResultCode.ADAPTER_MISSING, 'workspace mapper is not connected'
            )
        target = self.workspace_mapper.map_table_to_joints(
            candidate.table_x_m, candidate.table_y_m, layer
        )
        if not target:
            return ActionResult.failure(
                ResultCode.NOT_CALIBRATED,
                f'bean {candidate.target_id} is outside calibrated '
                f'{layer} grid',
            )
        duration = (
            self.config.motion_duration_sec
            if duration_sec is None
            else float(duration_sec)
        )
        return self._call(
            f'move bean {candidate.target_id} to {layer}',
            lambda: self.arm.move_to_joints(
                target, duration, self.config.motion_timeout_sec
            ),
        )

    def move_hover(self, candidate: BeanCandidate) -> ActionResult:
        return self.move_to_bean(candidate, 'hover')

    def visual_refine(self, candidate: BeanCandidate) -> ActionResult:
        return self.move_to_bean(
            candidate, 'hover', self.config.refine_duration_sec
        )

    def descend(self, candidate: BeanCandidate) -> ActionResult:
        return self.move_to_bean(candidate, 'pick')

    def squeeze_bean(self) -> ActionResult:
        return self._call(
            'squeeze bean',
            lambda: self.hand.move_hand_pose(
                'tweezers_squeeze', self.config.hand_timeout_sec
            ),
        )

    def lift(self, candidate: BeanCandidate) -> ActionResult:
        return self.move_to_bean(candidate, 'lift')

    def move_to_target(self) -> ActionResult:
        return self._call(
            'move to destination hover',
            lambda: self.arm.move_named_pose(
                'destination_hover', self.config.motion_timeout_sec
            ),
        )

    def release_bean(self) -> ActionResult:
        """Open only the tweezer tips; this must not release the tool."""
        return self._call(
            'release bean',
            lambda: self.hand.move_hand_pose(
                'tweezers_release', self.config.hand_timeout_sec
            ),
        )

    def recover_failed_pick(self, candidate: BeanCandidate) -> ActionResult:
        return self._sequence(
            'recover_failed_pick',
            [
                ('return above source', lambda: self.move_hover(candidate)),
                ('release uncertain bean', self.release_bean),
                ('lift clear of source', lambda: self.lift(candidate)),
            ],
        )

    def release_tweezer(self) -> ActionResult:
        return self._sequence(
            'release_tweezer',
            [
                (
                    'arm tweezer_grasp',
                    lambda: self.arm.move_named_pose(
                        'tweezer_grasp', self.config.motion_timeout_sec
                    ),
                ),
                (
                    'hand release_tool',
                    lambda: self.hand.move_hand_pose(
                        'release_tool', self.config.hand_timeout_sec
                    ),
                ),
            ],
        )

    def safe_finish(self) -> ActionResult:
        """Move to the calibrated finish pose without releasing the tool."""
        return self._call(
            'move to safe finish',
            lambda: self.arm.move_named_pose(
                'safe_finish', self.config.motion_timeout_sec
            ),
        )

    def halt(self, reason: str):
        """Ask A's adapter to hold/stop; never command neutral or open here."""
        try:
            self.arm.stop_motion(reason)
        except Exception:
            # The safety latch remains authoritative even if the stop adapter
            # is unavailable.  The node records the original safety reason.
            pass
