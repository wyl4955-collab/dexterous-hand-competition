from dexterous_hand_competition.common.arm_controller import ArmController
from dexterous_hand_competition.common.contracts import ResultCode
from dexterous_hand_competition.common.robot_state import RobotState


def make_controller():
    return ArmController(
        state=RobotState(),
        joint_limits={21: (-1.0, 1.0)},
        named_poses={'ready': {21: 0.2}},
        dry_run=True,
    )


def test_dry_run_motion_is_explicit():
    result = make_controller().move_named_pose('ready')
    assert result.ok
    assert result.code == ResultCode.DRY_RUN


def test_out_of_limit_target_is_rejected():
    result = make_controller().move_to_joints(
        {21: 2.0}, duration_sec=1.0, timeout_sec=2.0
    )
    assert not result.ok
    assert result.code == ResultCode.OUT_OF_LIMITS


def test_unknown_pose_is_rejected():
    result = make_controller().move_named_pose('missing')
    assert not result.ok
    assert result.code == ResultCode.NOT_CALIBRATED

