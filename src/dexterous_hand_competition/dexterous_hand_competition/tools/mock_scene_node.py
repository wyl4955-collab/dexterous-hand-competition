"""Synthetic scene and visual confirmations for C2 dry-run integration."""

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, UInt32

from competition_interfaces.msg import BeanTarget, Scene, TaskState


class MockSceneNode(Node):
    def __init__(self):
        super().__init__('mock_scene_node')
        self.declare_parameter('bean_count', 3)
        self.declare_parameter('confirmation_delay_sec', 0.25)
        self.bean_count = max(1, int(self.get_parameter('bean_count').value))
        self.confirmation_delay_sec = max(
            0.0,
            float(self.get_parameter('confirmation_delay_sec').value),
        )

        self.scene_pub = self.create_publisher(
            Scene, '/bean_task/scene', 10
        )
        self.health_pub = self.create_publisher(
            Bool, '/bean_task/vision_health', 10
        )
        self.pick_pub = self.create_publisher(
            UInt32, '/bean_task/pick_confirmed_id', 10
        )
        self.drop_pub = self.create_publisher(
            UInt32, '/bean_task/drop_confirmed_id', 10
        )
        self.create_subscription(
            TaskState, '/bean_task/state', self._state_callback, 10
        )
        self.create_subscription(
            UInt32,
            '/bean_task/active_target_id',
            self._target_callback,
            10,
        )

        self._state_name = 'WAIT_START'
        self._state_seen_sec = time.monotonic()
        self._active_target_id = 0
        self._picked: set[int] = set()
        self._dropped: set[int] = set()
        self._confirmation_keys: set[tuple[str, int]] = set()
        self.create_timer(0.1, self._publish)
        self.get_logger().warning(
            'Synthetic C2 scene/confirmations active; never use on hardware'
        )

    def _state_callback(self, message: TaskState):
        if message.state_name != self._state_name:
            self._state_name = message.state_name
            self._state_seen_sec = time.monotonic()

    def _target_callback(self, message: UInt32):
        self._active_target_id = int(message.data)

    def _publish_confirmation(self, publisher, target_id: int):
        message = UInt32()
        message.data = target_id
        publisher.publish(message)

    def _maybe_confirm(self):
        target_id = self._active_target_id
        if target_id <= 0:
            return
        if (
            time.monotonic() - self._state_seen_sec
            < self.confirmation_delay_sec
        ):
            return
        key = (self._state_name, target_id)
        if key in self._confirmation_keys:
            return

        if self._state_name == 'VERIFY_PICK':
            self._picked.add(target_id)
            self._publish_confirmation(self.pick_pub, target_id)
            self._confirmation_keys.add(key)
        elif self._state_name == 'VERIFY_DROP' and target_id in self._picked:
            self._dropped.add(target_id)
            self._publish_confirmation(self.drop_pub, target_id)
            self._confirmation_keys.add(key)

    def _publish(self):
        self._maybe_confirm()

        health = Bool()
        health.data = True
        self.health_pub.publish(health)

        scene = Scene()
        scene.header.stamp = self.get_clock().now().to_msg()
        scene.header.frame_id = 'table'
        scene.valid = True
        scene.calibrated = True
        scene.source_center.x = 0.45
        scene.source_center.y = -0.20
        scene.target_center.x = 0.45
        scene.target_center.y = 0.20
        scene.message = 'synthetic C2 dry-run scene'

        for target_id in range(1, self.bean_count + 1):
            if target_id in self._picked:
                continue
            target = BeanTarget()
            target.id = target_id
            target.u = 600.0 + 24.0 * target_id
            target.v = 340.0 + 8.0 * target_id
            target.table_position.x = 0.43 + 0.01 * target_id
            target.table_position.y = -0.21 + 0.008 * target_id
            target.confidence = 0.98 - 0.01 * target_id
            target.edge_distance_px = 90.0 + target_id
            target.nearest_neighbor_px = 70.0 + target_id
            target.failure_count = 0
            scene.beans.append(target)
        self.scene_pub.publish(scene)


def main(args=None):
    rclpy.init(args=args)
    node = MockSceneNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
