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


def test_settings_parse_string_booleans_safely():
    settings = BeanTaskSettings.from_mapping({
        'dry_run': 'false',
        'auto_grasp_tweezer': 'true',
        'auto_release_tweezer': 'off',
    })
    assert settings.dry_run is False
    assert settings.auto_grasp_tweezer is True
    assert settings.auto_release_tweezer is False


def test_settings_reject_zero_empty_scene_confirmations():
    with pytest.raises(ValueError, match='empty_scene_confirmations'):
        BeanTaskSettings.from_mapping({'empty_scene_confirmations': 0})
