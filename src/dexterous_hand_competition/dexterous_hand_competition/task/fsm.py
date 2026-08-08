"""Explicit finite-state machine for the tweezer bean-picking task.

This module deliberately has no ROS imports so the transition graph and
timeouts can be tested on a development computer before touching the robot.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
    RECOVER_PICK = 115
    MOVE_TARGET = 120
    RELEASE_BEAN = 130
    VERIFY_DROP = 140
    RECOVER_DROP = 145
    RETURN_TWEEZER = 150
    SAFE_FINISH = 160
    DONE = 170
    ERROR_LOCK = 900


DEFAULT_STATE_TIMEOUTS_SEC = {
    BeanTaskState.CHECK_SYSTEM: 5.0,
    BeanTaskState.GRASP_TWEEZER: 20.0,
    BeanTaskState.VERIFY_TWEEZER: 5.0,
    BeanTaskState.WAIT_SCENE: 10.0,
    BeanTaskState.SELECT_BEAN: 2.0,
    BeanTaskState.MOVE_HOVER: 12.0,
    BeanTaskState.VISUAL_REFINE: 5.0,
    BeanTaskState.DESCEND: 10.0,
    BeanTaskState.SQUEEZE: 5.0,
    BeanTaskState.LIFT: 10.0,
    BeanTaskState.VERIFY_PICK: 3.0,
    BeanTaskState.RECOVER_PICK: 12.0,
    BeanTaskState.MOVE_TARGET: 12.0,
    BeanTaskState.RELEASE_BEAN: 5.0,
    BeanTaskState.VERIFY_DROP: 3.0,
    BeanTaskState.RECOVER_DROP: 5.0,
    BeanTaskState.RETURN_TWEEZER: 15.0,
    BeanTaskState.SAFE_FINISH: 10.0,
}


_ALLOWED_TRANSITIONS = {
    BeanTaskState.WAIT_START: {BeanTaskState.CHECK_SYSTEM},
    BeanTaskState.CHECK_SYSTEM: {
        BeanTaskState.GRASP_TWEEZER,
        BeanTaskState.VERIFY_TWEEZER,
    },
    BeanTaskState.GRASP_TWEEZER: {BeanTaskState.VERIFY_TWEEZER},
    BeanTaskState.VERIFY_TWEEZER: {BeanTaskState.WAIT_SCENE},
    BeanTaskState.WAIT_SCENE: {
        BeanTaskState.SELECT_BEAN,
        BeanTaskState.RETURN_TWEEZER,
    },
    BeanTaskState.SELECT_BEAN: {
        BeanTaskState.MOVE_HOVER,
        BeanTaskState.WAIT_SCENE,
        BeanTaskState.RETURN_TWEEZER,
    },
    BeanTaskState.MOVE_HOVER: {BeanTaskState.VISUAL_REFINE},
    BeanTaskState.VISUAL_REFINE: {
        BeanTaskState.DESCEND,
        BeanTaskState.WAIT_SCENE,
    },
    BeanTaskState.DESCEND: {BeanTaskState.SQUEEZE},
    BeanTaskState.SQUEEZE: {BeanTaskState.LIFT},
    BeanTaskState.LIFT: {BeanTaskState.VERIFY_PICK},
    BeanTaskState.VERIFY_PICK: {
        BeanTaskState.MOVE_TARGET,
        BeanTaskState.RECOVER_PICK,
    },
    BeanTaskState.RECOVER_PICK: {BeanTaskState.WAIT_SCENE},
    BeanTaskState.MOVE_TARGET: {BeanTaskState.RELEASE_BEAN},
    BeanTaskState.RELEASE_BEAN: {BeanTaskState.VERIFY_DROP},
    BeanTaskState.VERIFY_DROP: {
        BeanTaskState.WAIT_SCENE,
        BeanTaskState.RECOVER_DROP,
        BeanTaskState.RETURN_TWEEZER,
    },
    BeanTaskState.RECOVER_DROP: {BeanTaskState.WAIT_SCENE},
    BeanTaskState.RETURN_TWEEZER: {BeanTaskState.SAFE_FINISH},
    BeanTaskState.SAFE_FINISH: {BeanTaskState.DONE},
    BeanTaskState.DONE: set(),
    BeanTaskState.ERROR_LOCK: set(),
}


@dataclass(frozen=True)
class TransitionRecord:
    previous: BeanTaskState
    current: BeanTaskState
    reason: str
    stamp_sec: float


class BeanTaskFsm:
    """Transition-validated FSM with per-state monotonic timeouts."""

    def __init__(
        self,
        state_timeouts_sec: Mapping[BeanTaskState, float] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self._clock = clock or time.monotonic
        self._timeouts = dict(DEFAULT_STATE_TIMEOUTS_SEC)
        if state_timeouts_sec:
            for state, timeout in state_timeouts_sec.items():
                parsed_state = BeanTaskState(state)
                parsed_timeout = float(timeout)
                if parsed_timeout <= 0.0:
                    raise ValueError(
                        f'timeout for {parsed_state.name} must be positive'
                    )
                self._timeouts[parsed_state] = parsed_timeout

        self.state = BeanTaskState.WAIT_START
        self.state_entered_sec = self._clock()
        self.last_error = ''
        self.history: list[TransitionRecord] = []

    def transition(
        self,
        new_state: BeanTaskState,
        reason: str = '',
        error: str = '',
    ):
        new_state = BeanTaskState(new_state)
        # Preserve the original two-argument API used by early scaffold code:
        # transition(ERROR_LOCK, 'reason').
        if new_state == BeanTaskState.ERROR_LOCK and reason and not error:
            error = reason
        previous = self.state
        if new_state == previous:
            raise ValueError(f'already in state {new_state.name}')

        globally_allowed = (
            new_state == BeanTaskState.ERROR_LOCK
            and previous not in (BeanTaskState.DONE, BeanTaskState.ERROR_LOCK)
        ) or (
            new_state == BeanTaskState.SAFE_FINISH
            and previous not in (
                BeanTaskState.WAIT_START,
                BeanTaskState.DONE,
                BeanTaskState.ERROR_LOCK,
            )
        )
        if (
            not globally_allowed
            and new_state not in _ALLOWED_TRANSITIONS[previous]
        ):
            raise ValueError(
                f'invalid transition: {previous.name} -> {new_state.name}'
            )

        now = self._clock()
        self.state = new_state
        self.state_entered_sec = now
        if error:
            self.last_error = error
        self.history.append(
            TransitionRecord(previous, new_state, reason or error, now)
        )

    def state_age_sec(self) -> float:
        return max(0.0, self._clock() - self.state_entered_sec)

    def timeout_sec(self) -> float | None:
        return self._timeouts.get(self.state)

    def timed_out(self) -> bool:
        timeout = self.timeout_sec()
        return timeout is not None and self.state_age_sec() > timeout

    def reset(self):
        self.state = BeanTaskState.WAIT_START
        self.state_entered_sec = self._clock()
        self.last_error = ''
        self.history.clear()
