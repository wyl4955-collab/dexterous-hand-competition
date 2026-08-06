"""Latched safety monitor.

The scaffold intentionally does not guess Tianyi SDK safety message types.
Implement the marked subscriptions after verifying them on the real robot.
"""

import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class SafetyLatch:
    def __init__(self, dry_run: bool = True):
        self._lock = threading.RLock()
        self._safe = bool(dry_run)
        self._reason = 'dry-run safety simulation' if dry_run else 'not initialized'
        self._stamp_sec = time.monotonic()

    def is_safe(self) -> bool:
        with self._lock:
            return self._safe

    def last_error(self) -> str:
        with self._lock:
            return '' if self._safe else self._reason

    def set_safe(self, reason: str = 'checks passed'):
        with self._lock:
            self._safe = True
            self._reason = reason
            self._stamp_sec = time.monotonic()

    def trip(self, reason: str):
        with self._lock:
            self._safe = False
            self._reason = reason
            self._stamp_sec = time.monotonic()


class SafetyMonitorNode(Node):
    def __init__(self):
        super().__init__('safety_monitor')
        self.declare_parameter('dry_run', True)
        dry_run = bool(self.get_parameter('dry_run').value)
        self.latch = SafetyLatch(dry_run=dry_run)

        self._safe_pub = self.create_publisher(Bool, '/bean_task/safety_ok', 10)
        self._reason_pub = self.create_publisher(
            String, '/bean_task/safety_reason', 10
        )
        self.create_timer(0.1, self._publish_status)

        if dry_run:
            self.get_logger().warning(
                'Safety monitor is in dry-run simulation; no real SDK safety '
                'topics are connected'
            )
        else:
            self.latch.trip('TODO_REAL_ROBOT safety adapters are missing')
            self.get_logger().error(
                'Real mode is locked until verified hard-estop, remote-estop, '
                'power, joint-error and feedback-timeout adapters are added'
            )

        # TODO_REAL_ROBOT: create subscriptions only after verifying:
        # /power/board/key_status
        # /power/board/status
        # /power/battery/status
        # arm/head/waist/leg status message types and error fields

    def _publish_status(self):
        safe_msg = Bool()
        safe_msg.data = self.latch.is_safe()
        self._safe_pub.publish(safe_msg)

        reason_msg = String()
        reason_msg.data = self.latch.last_error()
        self._reason_pub.publish(reason_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

