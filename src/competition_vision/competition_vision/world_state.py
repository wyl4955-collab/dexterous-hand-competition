"""
Thread-safe world state — single source of truth for all perception data.

Perception node WRITES → WorldState
All decision nodes READ → WorldState.snapshot()
"""
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np


@dataclass
class BeanInfo:
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    world_x: float = 0.0   # mm in table frame
    world_y: float = 0.0   # mm in table frame
    radius_px: float = 0.0
    confidence: float = 0.0


@dataclass
class ToolInfo:
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    world_x: float = 0.0
    world_y: float = 0.0
    world_z: float = 0.0   # height above table
    angle_deg: float = 0.0


class WorldState:
    """Thread-safe world state buffer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._beans: List[BeanInfo] = []
        self._tool: Optional[ToolInfo] = None
        self._scale_weight: Optional[float] = None
        self._raw_image: Optional[np.ndarray] = None
        self._timestamp = 0.0
        self._frame_count = 0

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f'_{k}'):
                    setattr(self, f'_{k}', v)
            self._timestamp = time.time()
            self._frame_count += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'timestamp': self._timestamp,
                'frame_count': self._frame_count,
                'beans': list(self._beans),
                'tool': self._tool,
                'scale_weight': self._scale_weight,
                'raw_image': self._raw_image,
            }

    def best_bean(self) -> Optional[BeanInfo]:
        """Select the best bean to pick (closest to center, isolated)."""
        with self._lock:
            if not self._beans:
                return None
            # Sort by distance to tool (if known), else to center
            if self._tool:
                tx, ty = self._tool.world_x, self._tool.world_y
                sorted_beans = sorted(
                    self._beans,
                    key=lambda b: (b.world_x - tx)**2 + (b.world_y - ty)**2
                )
            else:
                sorted_beans = sorted(
                    self._beans,
                    key=lambda b: b.world_x**2 + b.world_y**2
                )
            # Pick first bean that's not too close to others
            for b in sorted_beans:
                too_close = False
                for other in self._beans:
                    if other is b:
                        continue
                    d = ((b.world_x - other.world_x)**2 +
                         (b.world_y - other.world_y)**2) ** 0.5
                    if d < 10.0:  # < 10mm apart
                        too_close = True
                        break
                if not too_close:
                    return b
            return sorted_beans[0] if sorted_beans else None
