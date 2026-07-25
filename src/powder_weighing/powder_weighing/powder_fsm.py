#!/usr/bin/env python3
"""Powder Weighing FSM — plain class, uses supervisor's node for ROS2."""
import time
from std_msgs.msg import Float32

TAP_DROP = {30:0.01, 50:0.02, 80:0.04, 120:0.08, 180:0.15, 250:0.30}


class PowderWeighingFSM:
    def __init__(self, node, primitives, arm=None, waypoints=None):
        self.node = node
        self.p = primitives
        self.arm = arm
        self.wp = waypoints or {}
        self._weight = 0.0
        node.create_subscription(Float32, '/vision/scale', self._scale_cb, 10)

    def _scale_cb(self, msg): self._weight = msg.data

    def _log(self, s): self.node.get_logger().info(s)

    def execute(self, target=5.00, tolerance=0.05, timeout=120.0) -> dict:
        t0 = time.time()
        self._log(f'Powder: target={target}g ±{tolerance}g')

        self.p.grip('spoon')
        time.sleep(0.3)

        # Scoop (arm moves to container)
        if self.arm:
            self.arm.move_to(self.wp.get('powder_container', (50,20,80)), speed=30)
            self.arm.move_relative(dz=-15, speed=10)
            time.sleep(0.3)
            self.arm.move_relative(dx=30, speed=15)
            self.arm.move_relative(dz=20, speed=15)

        # Move to scale
        if self.arm:
            self.arm.move_to(self.wp.get('scale_above', (150,75,60)), speed=30)

        # Wait for powder to start showing
        for _ in range(15):
            if self._weight > 0.3: break
            time.sleep(0.3)
        self._log(f'Starting weight: {self._weight:.2f}g')

        # Coarse pour: tilt spoon, wait until ~1g of target
        coarse_deadline = time.time() + 25
        while time.time() < coarse_deadline:
            remaining = target - self._weight
            if remaining <= 1.0: break
            time.sleep(0.3)

        # Fine tap with scale feedback
        taps = 0
        for _ in range(250):
            if time.time()-t0 > timeout: break
            remaining = target - self._weight
            if abs(remaining) <= tolerance: break
            if remaining < 0: break

            if remaining > 1.5:   force = 250
            elif remaining > 0.8: force = 180
            elif remaining > 0.3: force = 120
            elif remaining > 0.1: force = 80
            elif remaining > 0.05: force = 50
            else:                  force = 30

            drop = TAP_DROP.get(force, 0.05)
            n = max(1, min(10, int(remaining/drop*0.7)))
            self.p.tap(force, n, 0.4)
            taps += n
            time.sleep(0.5)

        time.sleep(1.5)
        final = self._weight
        err = abs(final-target)
        ok = err <= tolerance
        self._log(f'Done: {final:.2f}g err={err:.3f}g {"OK" if ok else "FAIL"}')

        self.p.release()
        return {'success':ok, 'actual':final, 'error':err,
                'elapsed':time.time()-t0, 'taps':taps}
