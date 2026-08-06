"""Validated YAML configuration loading."""

from pathlib import Path
from typing import Any, Iterable

import yaml


class ConfigurationError(RuntimeError):
    """Raised when a required configuration is missing or invalid."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigurationError(f'Configuration file not found: {config_path}')

    with config_path.open('r', encoding='utf-8') as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise ConfigurationError(
            f'Configuration root must be a mapping: {config_path}'
        )
    return data


def require_keys(data: dict[str, Any], keys: Iterable[str], context: str):
    missing = [key for key in keys if key not in data]
    if missing:
        raise ConfigurationError(
            f'{context} is missing required keys: {", ".join(missing)}'
        )


def require_calibrated(data: dict[str, Any], context: str):
    if data.get('calibrated') is not True:
        raise ConfigurationError(
            f'{context} is not calibrated; keep dry_run enabled'
        )

