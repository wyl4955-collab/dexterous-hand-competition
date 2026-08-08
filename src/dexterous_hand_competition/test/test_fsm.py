import pytest

from dexterous_hand_competition.task.fsm import BeanTaskFsm, BeanTaskState


def test_fsm_starts_waiting():
    fsm = BeanTaskFsm()
    assert fsm.state == BeanTaskState.WAIT_START


def test_fsm_accepts_only_declared_transitions():
    fsm = BeanTaskFsm()
    fsm.transition(BeanTaskState.CHECK_SYSTEM)
    fsm.transition(BeanTaskState.VERIFY_TWEEZER)
    assert fsm.state == BeanTaskState.VERIFY_TWEEZER

    with pytest.raises(ValueError, match='invalid transition'):
        fsm.transition(BeanTaskState.MOVE_TARGET)


def test_fsm_records_error_and_resets():
    fsm = BeanTaskFsm()
    fsm.transition(BeanTaskState.ERROR_LOCK, 'estop')
    assert fsm.last_error == 'estop'
    assert fsm.history[-1].current == BeanTaskState.ERROR_LOCK
    fsm.reset()
    assert fsm.state == BeanTaskState.WAIT_START
    assert fsm.last_error == ''
    assert fsm.history == []


def test_fsm_timeout_uses_monotonic_clock():
    now = [100.0]
    fsm = BeanTaskFsm(
        {BeanTaskState.CHECK_SYSTEM: 2.0}, clock=lambda: now[0]
    )
    fsm.transition(BeanTaskState.CHECK_SYSTEM)
    now[0] += 1.9
    assert not fsm.timed_out()
    now[0] += 0.2
    assert fsm.timed_out()


def test_manual_finish_is_allowed_from_active_state():
    fsm = BeanTaskFsm()
    fsm.transition(BeanTaskState.CHECK_SYSTEM)
    fsm.transition(BeanTaskState.SAFE_FINISH, 'operator stop')
    fsm.transition(BeanTaskState.DONE)
    assert fsm.state == BeanTaskState.DONE
