"""Validated C2 task settings loaded from YAML."""

from dataclasses import dataclass
from typing import Any

from .fsm import BeanTaskState, DEFAULT_STATE_TIMEOUTS_SEC


def _as_bool(value: Any, name: str) -> bool:
    """Parse booleans without treating the string ``"false"`` as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('true', 'yes', 'on', '1'):
            return True
        if normalized in ('false', 'no', 'off', '0'):
            return False
    raise ValueError(f'{name} must be a boolean')


@dataclass(frozen=True)
class BeanTaskSettings:
    dry_run: bool = True
    time_limit_sec: float = 300.0
    target_count: int = 0
    scene_timeout_sec: float = 0.5
    empty_scene_confirmations: int = 3
    max_pick_retries: int = 3
    blacklist_ttl_sec: float = 20.0
    min_target_confidence: float = 0.25
    stop_new_pick_remaining_sec: float = 20.0
    tick_period_sec: float = 0.1
    state_publish_period_sec: float = 0.2
    retry_wait_sec: float = 0.5
    auto_grasp_tweezer: bool = False
    auto_release_tweezer: bool = False
    state_timeouts_sec: dict[BeanTaskState, float] | None = None

    @classmethod
    def from_mapping(cls, root: dict[str, Any]):
        data = root.get('bean_task', root)
        if not isinstance(data, dict):
            raise ValueError('bean_task configuration must be a mapping')

        timeouts = dict(DEFAULT_STATE_TIMEOUTS_SEC)
        configured_timeouts = data.get('state_timeouts_sec', {})
        if not isinstance(configured_timeouts, dict):
            raise ValueError('state_timeouts_sec must be a mapping')
        for name, value in configured_timeouts.items():
            try:
                state = BeanTaskState[str(name).upper()]
            except KeyError as exc:
                raise ValueError(f'unknown state timeout: {name}') from exc
            timeout = float(value)
            if timeout <= 0.0:
                raise ValueError(f'timeout for {state.name} must be positive')
            timeouts[state] = timeout

        settings = cls(
            dry_run=_as_bool(data.get('dry_run', True), 'dry_run'),
            time_limit_sec=float(data.get('time_limit_sec', 300.0)),
            target_count=int(data.get('target_count', 0)),
            scene_timeout_sec=float(data.get('scene_timeout_sec', 0.5)),
            empty_scene_confirmations=int(
                data.get('empty_scene_confirmations', 3)
            ),
            max_pick_retries=int(data.get('max_pick_retries', 3)),
            blacklist_ttl_sec=float(data.get('blacklist_ttl_sec', 20.0)),
            min_target_confidence=float(
                data.get('min_target_confidence', 0.25)
            ),
            stop_new_pick_remaining_sec=float(
                data.get('stop_new_pick_remaining_sec', 20.0)
            ),
            tick_period_sec=float(data.get('tick_period_sec', 0.1)),
            state_publish_period_sec=float(
                data.get('state_publish_period_sec', 0.2)
            ),
            retry_wait_sec=float(data.get('retry_wait_sec', 0.5)),
            auto_grasp_tweezer=_as_bool(
                data.get('auto_grasp_tweezer', False),
                'auto_grasp_tweezer',
            ),
            auto_release_tweezer=_as_bool(
                data.get('auto_release_tweezer', False),
                'auto_release_tweezer',
            ),
            state_timeouts_sec=timeouts,
        )
        settings.validate()
        return settings

    def validate(self):
        positive = {
            'time_limit_sec': self.time_limit_sec,
            'scene_timeout_sec': self.scene_timeout_sec,
            'blacklist_ttl_sec': self.blacklist_ttl_sec,
            'tick_period_sec': self.tick_period_sec,
            'state_publish_period_sec': self.state_publish_period_sec,
            'retry_wait_sec': self.retry_wait_sec,
        }
        invalid = [name for name, value in positive.items() if value <= 0.0]
        if invalid:
            names = ', '.join(invalid)
            raise ValueError(f'parameters must be positive: {names}')
        if self.target_count < 0:
            raise ValueError('target_count cannot be negative')
        if self.empty_scene_confirmations < 1:
            raise ValueError('empty_scene_confirmations must be at least one')
        if self.max_pick_retries < 1:
            raise ValueError('max_pick_retries must be at least one')
        if not 0.0 <= self.min_target_confidence <= 1.0:
            raise ValueError('min_target_confidence must be in [0, 1]')
        if self.stop_new_pick_remaining_sec < 0.0:
            raise ValueError('stop_new_pick_remaining_sec cannot be negative')
