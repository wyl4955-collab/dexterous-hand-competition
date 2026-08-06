from dexterous_hand_competition.common.contracts import ResultCode
from dexterous_hand_competition.common.hand_controller import HandController


def test_hand_requires_six_ratios():
    controller = HandController({'open': [0.0, 0.0]}, dry_run=True)
    result = controller.move_hand_pose('open')
    assert not result.ok
    assert result.code == ResultCode.INVALID_ARGUMENT


def test_valid_hand_pose_runs_only_in_dry_run():
    controller = HandController({'open': [0.0] * 6}, dry_run=True)
    result = controller.move_hand_pose('open')
    assert result.ok
    assert result.code == ResultCode.DRY_RUN

