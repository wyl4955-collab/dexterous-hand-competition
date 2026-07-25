"""
Abstract robot arm interface.

All manipulation skills use this interface. Replace MockArm with your
actual arm driver (UR, Franka, xArm, etc.) by implementing this ABC.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class ArmPose:
    """Arm end-effector pose in table frame (mm, degrees)"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def to_tuple(self) -> Tuple[float, ...]:
        return (self.x, self.y, self.z, self.roll, self.pitch, self.yaw)


class ArmInterface(ABC):
    """
    Abstract interface for robot arm control.

    All manipulation skills interact with the arm through this interface,
    making it possible to swap arm hardware without changing skill code.
    """

    @abstractmethod
    def connect(self, config: dict) -> bool:
        """Connect to arm hardware. Return True on success."""
        ...

    @abstractmethod
    def disconnect(self):
        """Disconnect from arm hardware."""
        ...

    @abstractmethod
    def move_to(self, position: Tuple[float, float, float],
                orientation: Tuple[float, float, float] = (0, 0, 0),
                speed: float = 50.0,
                blocking: bool = True) -> bool:
        """
        Move end-effector to absolute position in table frame.

        Args:
            position: (x, y, z) in mm
            orientation: (roll, pitch, yaw) in degrees
            speed: movement speed in mm/s
            blocking: wait for completion

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    def move_relative(self, dx: float = 0, dy: float = 0, dz: float = 0,
                      speed: float = 20.0, blocking: bool = True) -> bool:
        """Move relative to current position by (dx, dy, dz) in mm."""
        ...

    @abstractmethod
    def move_linear(self, target: Tuple[float, float, float],
                    speed: float = 20.0) -> bool:
        """Linear motion to target position."""
        ...

    @abstractmethod
    def get_pose(self) -> Optional[ArmPose]:
        """Get current end-effector pose."""
        ...

    @abstractmethod
    def stop(self):
        """Immediate stop."""
        ...

    @abstractmethod
    def is_moving(self) -> bool:
        """Check if arm is currently in motion."""
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if arm is connected and ready."""
        ...

    @abstractmethod
    def set_tcp_offset(self, offset: Tuple[float, float, float]):
        """Set tool center point offset from flange (mm)."""
        ...
