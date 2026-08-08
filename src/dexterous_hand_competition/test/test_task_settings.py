import pytest

from dexterous_hand_competition.task.fsm import BeanTaskState
from dexterous_hand_competition.task.settings import BeanTaskSettings


def test_settings_load_state_timeouts():
    settings = BeanTaskSettings.from_mapping({
        'bean_task': {
            'time_limit_sec': 30,
            'target_count': 3,
            'state_timeouts_sec': {'VERIFY_PICK': 1.5},
        }
    })
    assert settings.target_count == 3
    assert settings.state_timeouts_sec[BeanTaskState.VERIFY_PICK] == 1.5


def test_settings_reject_unknown_state():
    with pytest.raises(ValueError, match='unknown state timeout'):
        BeanTaskSettings.from_mapping({
            'state_timeouts_sec': {'NOT_A_STATE': 1.0}
        })
