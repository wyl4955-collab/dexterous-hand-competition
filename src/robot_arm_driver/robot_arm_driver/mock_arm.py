"""
Mock arm for development and testing without real hardware.

Simulates arm movements with configurable delays.
"""

import time
import threading
from typing import Tuple, Optional
from .arm_interface import ArmInterface, ArmPose


class MockArm(ArmInterface):
    """
    Simulated robot arm for development.

    All move methods introduce a small delay to simulate real movement time.
    """

    def __init__(self):
        self._pose = ArmPose(x=100, y=75, z=200)  # home position
        self._moving = False
        self._ready = False
        self._tcp_offset = (0.0, 0.0, 0.0)
        self._sim_speed_factor = 1.0  # set < 1 for faster simulation

    def connect(self, config: dict) -> bool:
        print(f"[MockArm] Connected (simulated)")
        self._ready = True
        return True

    def disconnect(self):
        self._ready = False
        print("[MockArm] Disconnected")

    def move_to(self, position: Tuple[float, float, float],
                orientation: Tuple[float, float, float] = (0, 0, 0),
                speed: float = 50.0,
                blocking: bool = True) -> bool:
        if not self._ready:
            return False

        # Simulate movement time
        dx = position[0] - self._pose.x
        dy = position[1] - self._pose.y
        dz = position[2] - self._pose.z
        dist = (dx*dx + dy*dy + dz*dz) ** 0.5
        sim_time = (dist / speed) * self._sim_speed_factor

        if blocking:
            self._moving = True
            time.sleep(max(0.05, sim_time))
            self._moving = False

        self._pose = ArmPose(
            x=position[0], y=position[1], z=position[2],
            roll=orientation[0], pitch=orientation[1], yaw=orientation[2]
        )
        return True

    def move_relative(self, dx: float = 0, dy: float = 0, dz: float = 0,
                      speed: float = 20.0, blocking: bool = True) -> bool:
        return self.move_to(
            (self._pose.x + dx, self._pose.y + dy, self._pose.z + dz),
            (self._pose.roll, self._pose.pitch, self._pose.yaw),
            speed, blocking
        )

    def move_linear(self, target: Tuple[float, float, float],
                    speed: float = 20.0) -> bool:
        return self.move_to(target, speed=speed)

    def get_pose(self) -> Optional[ArmPose]:
        return self._pose

    def stop(self):
        self._moving = False

    def is_moving(self) -> bool:
        return self._moving

    def is_ready(self) -> bool:
        return self._ready

    def set_tcp_offset(self, offset: Tuple[float, float, float]):
        self._tcp_offset = offset
