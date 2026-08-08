"""Target selection, retry accounting and short-term blacklisting."""

from collections.abc import Callable, Iterable
import math
import time

from ..common.contracts import BeanCandidate


class TargetManager:
    def __init__(
        self,
        max_retries: int = 3,
        blacklist_ttl_sec: float = 20.0,
        min_confidence: float = 0.25,
        clock: Callable[[], float] | None = None,
    ):
        if max_retries < 1:
            raise ValueError('max_retries must be at least one')
        if blacklist_ttl_sec <= 0.0:
            raise ValueError('blacklist_ttl_sec must be positive')
        self.max_retries = int(max_retries)
        self.blacklist_ttl_sec = float(blacklist_ttl_sec)
        self.min_confidence = float(min_confidence)
        self._clock = clock or time.monotonic
        self._failures: dict[int, int] = {}
        self._blocked_until: dict[int, float] = {}

    @staticmethod
    def _valid(candidate: BeanCandidate) -> bool:
        values = (
            candidate.u,
            candidate.v,
            candidate.table_x_m,
            candidate.table_y_m,
            candidate.confidence,
            candidate.edge_distance_px,
            candidate.nearest_neighbor_px,
        )
        return all(math.isfinite(float(value)) for value in values)

    def _expire(self, target_id: int, now: float):
        blocked_until = self._blocked_until.get(target_id)
        if blocked_until is not None and now >= blocked_until:
            self._blocked_until.pop(target_id, None)
            self._failures[target_id] = 0

    def is_blacklisted(self, target_id: int) -> bool:
        now = self._clock()
        self._expire(int(target_id), now)
        return now < self._blocked_until.get(int(target_id), 0.0)

    def failure_count(self, target_id: int) -> int:
        self._expire(int(target_id), self._clock())
        return self._failures.get(int(target_id), 0)

    def select(
        self,
        candidates: Iterable[BeanCandidate],
    ) -> BeanCandidate | None:
        eligible = []
        for candidate in candidates:
            if not self._valid(candidate):
                continue
            if candidate.confidence < self.min_confidence:
                continue
            if self.is_blacklisted(candidate.target_id):
                continue

            local_failures = self.failure_count(candidate.target_id)
            score = (
                100.0 * candidate.confidence
                + 0.10 * min(max(candidate.edge_distance_px, 0.0), 200.0)
                + 0.05
                * min(max(candidate.nearest_neighbor_px, 0.0), 200.0)
                - 20.0 * (local_failures + candidate.failure_count)
            )
            eligible.append((score, -candidate.target_id, candidate))

        if not eligible:
            return None
        return max(eligible, key=lambda item: (item[0], item[1]))[2]

    def mark_failure(self, target_id: int) -> bool:
        """Record a failure and return True when the target was blacklisted."""
        target_id = int(target_id)
        count = self.failure_count(target_id) + 1
        self._failures[target_id] = count
        if count < self.max_retries:
            return False
        self._blocked_until[target_id] = self._clock() + self.blacklist_ttl_sec
        return True

    def mark_success(self, target_id: int):
        target_id = int(target_id)
        self._failures.pop(target_id, None)
        self._blocked_until.pop(target_id, None)

    def reset(self):
        self._failures.clear()
        self._blocked_until.clear()
