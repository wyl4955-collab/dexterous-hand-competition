"""Stable cross-module contracts.

Keep this module free of ROS imports so it can be unit-tested on any computer.
"""

from dataclasses import dataclass
from enum import IntEnum


class ResultCode(IntEnum):
    OK = 0
    DRY_RUN = 1
    INVALID_ARGUMENT = 10
    NOT_CALIBRATED = 11
    NO_FEEDBACK = 12
    OUT_OF_LIMITS = 13
    TIMEOUT = 14
    SAFETY_LOCKED = 15
    ADAPTER_MISSING = 16
    SDK_REJECTED = 17
    VISION_INVALID = 20
    INTERNAL_ERROR = 99


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    code: ResultCode
    message: str
    elapsed_sec: float = 0.0

    @classmethod
    def success(cls, message: str = 'ok', elapsed_sec: float = 0.0):
        return cls(True, ResultCode.OK, message, elapsed_sec)

    @classmethod
    def dry_run(cls, message: str, elapsed_sec: float = 0.0):
        return cls(True, ResultCode.DRY_RUN, message, elapsed_sec)

    @classmethod
    def failure(
        cls,
        code: ResultCode,
        message: str,
        elapsed_sec: float = 0.0,
    ):
        return cls(False, code, message, elapsed_sec)


@dataclass(frozen=True)
class BeanCandidate:
    target_id: int
    u: float
    v: float
    table_x_m: float
    table_y_m: float
    confidence: float
    edge_distance_px: float
    nearest_neighbor_px: float
    failure_count: int = 0


@dataclass(frozen=True)
class SafetySnapshot:
    safe: bool
    reason: str
    stamp_sec: float

