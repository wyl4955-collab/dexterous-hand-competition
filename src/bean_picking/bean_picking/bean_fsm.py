#!/usr/bin/env python3
"""Bean Picking FSM — plain class, uses supervisor's node for ROS2."""
import time
from competition_interfaces.msg import BeanDetections, HandState


class BeanPickingFSM:
    def __init__(self, node, primitives, arm=None, waypoints=None):
        self.node = node
        self.p = primitives
        self.arm = arm
        self.wp = waypoints or {}
        self._beans = []
        self._forces = [0.0]*6
        self._status = [0]*6
        node.create_subscription(BeanDetections, '/vision/beans', self._beans_cb, 10)
        node.create_subscription(HandState, '/hand/state', self._state_cb, 10)

    def _beans_cb(self, m): self._beans = m.beans
    def _state_cb(self, m):
        self._forces, self._status = list(m.forces), list(m.status)

    def _log(self, s): self.node.get_logger().info(s)

    def execute(self, count=3, timeout=120.0) -> dict:
        t0 = time.time()
        done, failed = 0, 0
        self._log(f'Bean picking: target {count} beans')

        self.p.grip('tweezers')
        time.sleep(0.3)

        for i in range(count):
            if time.time()-t0 > timeout: break
            ok = self._pick_one(i+1)
            if ok: done += 1
            else: failed += 1
            self._log(f'Bean {i+1}/"{count}": {"OK" if ok else "MISS"} ({done}/{count} done)')

        self.p.release()
        return {'success':done>=count, 'beans_done':done,
                'beans_failed':failed, 'elapsed':time.time()-t0}

    def _pick_one(self, idx) -> bool:
        # Wait for beans
        for _ in range(40):
            if self._beans: break
            time.sleep(0.15)
        if not self._beans: return False

        bean = self._beans[-1]
        self._log(f'  Bean #{idx} at ({bean.x:.0f},{bean.y:.0f})mm')

        # Approach (arm moves)
        if self.arm:
            self.arm.move_to((bean.x, bean.y, 30), speed=30)
            self.arm.move_relative(dz=-18, speed=3)

        # Open tweezers
        self.p._send([1740,1740,1740,1500,1350,1200], [30]*6, [200]*6, sleep=0.3)

        # Grasp
        self.p.pinch_grasp(force=40, speed=150)
        time.sleep(0.3)

        # Check contact
        if self._forces[3] < 10:
            self.p.release(); return False

        # Anti-slip
        safe = min(int(max(self._forces[3], self._forces[4])) + 15, 80)
        self.p._send([-1]*6, [safe]*6, [200]*6, sleep=0.2)

        # Lift
        if self.arm: self.arm.move_relative(dz=50, speed=15)

        # Move to container
        if self.arm:
            drop = self.wp.get('bean_drop', (180,30,20))
            self.arm.move_to(drop[:3], speed=40)

        # Release
        self.p.release()
        time.sleep(0.2)
        return True
