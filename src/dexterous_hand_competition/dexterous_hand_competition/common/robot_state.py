"""Thread-safe robot feedback cache.

TODO_REAL_ROBOT: subscribe to verified Tianyi SDK status messages and call
``update_joint`` for every joint sample. Do not guess the SDK message type.
"""

from dataclasses import dataclass
import threading
import time


@dataclass
class JointSample:
    position_rad: float
    speed_rad_s: float = 0.0
    current: float = 0.0
    temperature_c: float = 0.0
    error_code: int = 0
    stamp_sec: float = 0.0


class RobotState:
    def __init__(self):
        self._lock = threading.RLock()
        self._joints: dict[int, JointSample] = {}

    def update_joint(self, joint_id: int, sample: JointSample):
        if sample.stamp_sec <= 0.0:
            sample.stamp_sec = time.monotonic()
        with self._lock:
            self._joints[int(joint_id)] = sample

    def get_joint_position(self, joint_id: int) -> float | None:
        with self._lock:
            sample = self._joints.get(int(joint_id))
            return None if sample is None else float(sample.position_rad)

    def get_positions(self, joint_ids: list[int]) -> dict[int, float]:
        with self._lock:
            return {
                joint_id: self._joints[joint_id].position_rad
                for joint_id in joint_ids
                if joint_id in self._joints
            }

    def feedback_is_fresh(self, max_age_sec: float = 0.5) -> bool:
        now = time.monotonic()
        with self._lock:
            return bool(self._joints) and all(
                now - sample.stamp_sec <= max_age_sec
                for sample in self._joints.values()
            )

    def any_joint_error(self) -> bool:
        with self._lock:
            return any(sample.error_code != 0 for sample in self._joints.values())

    def clear(self):
        with self._lock:
            self._joints.clear()

