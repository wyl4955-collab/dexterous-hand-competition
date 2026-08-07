import time

from dexterous_hand_competition.common.robot_state import (
    JointSample,
    RobotState,
)


def make_sample(
    position_rad=0.1,
    error_code=0,
    stamp_sec=None,
):
    return JointSample(
        position_rad=position_rad,
        speed_rad_s=0.2,
        current=0.3,
        temperature_c=30.0,
        error_code=error_code,
        stamp_sec=time.monotonic() if stamp_sec is None else stamp_sec,
    )


def test_get_joint_sample_returns_complete_copy():
    state = RobotState()
    original = make_sample(position_rad=0.4)
    state.update_joint(21, original)

    returned = state.get_joint_sample(21)
    assert returned == original
    assert returned is not original

    returned.position_rad = 1.0
    assert state.get_joint_position(21) == 0.4


def test_update_joint_does_not_retain_callers_mutable_sample():
    state = RobotState()
    original = make_sample(position_rad=0.4)
    state.update_joint(21, original)

    original.position_rad = 1.0
    assert state.get_joint_position(21) == 0.4


def test_get_joint_sample_returns_none_for_unknown_joint():
    assert RobotState().get_joint_sample(999) is None


def test_update_joint_assigns_monotonic_stamp_when_missing():
    state = RobotState()
    state.update_joint(21, make_sample(stamp_sec=0.0))

    returned = state.get_joint_sample(21)
    assert returned.stamp_sec > 0.0
    assert state.feedback_is_fresh_for([21])


def test_feedback_is_fresh_for_requested_joints():
    state = RobotState()
    state.update_joint(21, make_sample())
    state.update_joint(22, make_sample())

    assert state.feedback_is_fresh_for([21, 22])
    assert not state.feedback_is_fresh_for([])
    assert not state.feedback_is_fresh_for([21, 23])


def test_unrelated_stale_feedback_does_not_affect_requested_joints():
    state = RobotState()
    state.update_joint(21, make_sample())
    state.update_joint(11, make_sample(stamp_sec=time.monotonic() - 2.0))

    assert state.feedback_is_fresh_for([21], max_age_sec=0.5)
    assert not state.feedback_is_fresh(max_age_sec=0.5)


def test_stale_requested_joint_is_not_fresh():
    state = RobotState()
    state.update_joint(21, make_sample(stamp_sec=time.monotonic() - 2.0))

    assert not state.feedback_is_fresh_for([21], max_age_sec=0.5)


def test_any_joint_error_for_only_checks_requested_joints():
    state = RobotState()
    state.update_joint(21, make_sample(error_code=0))
    state.update_joint(22, make_sample(error_code=8))

    assert not state.any_joint_error_for([21])
    assert state.any_joint_error_for([22])
    assert state.any_joint_error_for([21, 22])
    assert not state.any_joint_error_for([23])
    assert state.any_joint_error()


def test_existing_position_and_clear_interfaces_remain_compatible():
    state = RobotState()
    state.update_joint(21, make_sample(position_rad=0.4))
    state.update_joint(22, make_sample(position_rad=0.5))

    assert state.get_positions([21, 22, 23]) == {21: 0.4, 22: 0.5}
    state.clear()
    assert state.get_joint_position(21) is None
    assert not state.feedback_is_fresh()
    assert not state.any_joint_error()
