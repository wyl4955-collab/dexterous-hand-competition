"""High-level tweezer skills composed from public arm/hand interfaces."""

from ..common.contracts import ActionResult, ResultCode


class TweezerSkills:
    def __init__(self, arm, hand):
        self.arm = arm
        self.hand = hand

    def grasp_tweezer(self) -> ActionResult:
        for pose_name in ('tweezers_pregrasp',):
            result = self.hand.move_hand_pose(pose_name)
            if not result.ok:
                return result

        result = self.arm.move_named_pose('tweezer_pregrasp')
        if not result.ok:
            return result
        result = self.arm.move_named_pose('tweezer_grasp')
        if not result.ok:
            return result
        return self.hand.move_hand_pose('tweezers_hold')

    def verify_tweezer_held(self) -> bool:
        # TODO_REAL_ROBOT: combine verified hand feedback and/or visual check.
        return self.hand.dry_run

    def squeeze_bean(self) -> ActionResult:
        return self.hand.move_hand_pose('tweezers_squeeze')

    def release_bean(self) -> ActionResult:
        return self.hand.move_hand_pose('tweezers_release')

    def release_tweezer(self) -> ActionResult:
        result = self.arm.move_named_pose('tweezer_grasp')
        if not result.ok:
            return result
        return self.hand.move_hand_pose('release_tool')

    def ensure_tweezer_held(self) -> ActionResult:
        if self.verify_tweezer_held():
            return ActionResult.success('tweezers verified')
        return ActionResult.failure(
            ResultCode.SDK_REJECTED, 'tweezers could not be verified'
        )

