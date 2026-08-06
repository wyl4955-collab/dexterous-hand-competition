from dexterous_hand_competition.task.fsm import BeanTaskFsm, BeanTaskState


def test_fsm_starts_waiting():
    fsm = BeanTaskFsm()
    assert fsm.state == BeanTaskState.WAIT_START


def test_fsm_records_error_and_resets():
    fsm = BeanTaskFsm()
    fsm.transition(BeanTaskState.ERROR_LOCK, 'estop')
    assert fsm.last_error == 'estop'
    fsm.reset()
    assert fsm.state == BeanTaskState.WAIT_START
    assert fsm.last_error == ''

