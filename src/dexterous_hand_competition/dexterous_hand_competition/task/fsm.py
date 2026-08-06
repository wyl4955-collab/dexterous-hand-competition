"""Small explicit FSM with transition validation."""

from enum import IntEnum
import time


class BeanTaskState(IntEnum):
    WAIT_START = 0
    CHECK_SYSTEM = 10
    GRASP_TWEEZER = 20
    VERIFY_TWEEZER = 30
    WAIT_SCENE = 40
    SELECT_BEAN = 50
    MOVE_HOVER = 60
    VISUAL_REFINE = 70
    DESCEND = 80
    SQUEEZE = 90
    LIFT = 100
    VERIFY_PICK = 110
    MOVE_TARGET = 120
    RELEASE_BEAN = 130
    VERIFY_DROP = 140
    SAFE_FINISH = 150
    DONE = 160
    ERROR_LOCK = 900


class BeanTaskFsm:
    def __init__(self):
        self.state = BeanTaskState.WAIT_START
        self.state_entered_sec = time.monotonic()
        self.last_error = ''

    def transition(self, new_state: BeanTaskState, error: str = ''):
        self.state = new_state
        self.state_entered_sec = time.monotonic()
        if error:
            self.last_error = error

    def state_age_sec(self) -> float:
        return time.monotonic() - self.state_entered_sec

    def reset(self):
        self.state = BeanTaskState.WAIT_START
        self.state_entered_sec = time.monotonic()
        self.last_error = ''

