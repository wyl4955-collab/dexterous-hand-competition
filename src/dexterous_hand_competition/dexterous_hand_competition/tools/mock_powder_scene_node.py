"""Publish synthetic powder-task scene data for FSM dry-run development."""

import rclpy
from rclpy.node import Node

from competition_interfaces.msg import PowderScene, ScaleReading


class MockPowderSceneNode(Node):
    def __init__(self):
        super().__init__('mock_powder_scene_node')
        self.scene_pub = self.create_publisher(PowderScene, '/powder_task/scene', 10)
        self.reading_pub = self.create_publisher(ScaleReading, '/powder_task/scale_reading', 10)
        self.create_timer(0.2, self._publish_scene)
        self.create_timer(0.5, self._publish_reading)
        self._mock_reading = 0.0
        self.get_logger().warning(
            'Publishing synthetic powder scene data; never use for a real task'
        )

    def _publish_scene(self):
        scene = PowderScene()
        scene.header.stamp = self.get_clock().now().to_msg()
        scene.header.frame_id = 'table'
        scene.valid = True
        scene.calibrated = True
        scene.powder_container_center.x = 0.35
        scene.powder_container_center.y = -0.20
        scene.scale_center.x = 0.45
        scene.scale_center.y = 0.0
        scene.spoon_categories = ['large', 'medium']
        scene.spoon_x_m = [0.55, 0.57]
        scene.spoon_y_m = [0.25, 0.20]
        scene.spoon_angle_rad = [0.0, 0.3]
        scene.message = 'synthetic dry-run powder scene'
        self.scene_pub.publish(scene)

    def _publish_reading(self):
        self._mock_reading += 5.3
        if self._mock_reading > 60.0:
            self._mock_reading = 0.0
        reading = ScaleReading()
        reading.header.stamp = self.get_clock().now().to_msg()
        reading.value_grams = self._mock_reading
        reading.confidence = 0.95
        reading.stable = True
        reading.message = f'{self._mock_reading:.1f}g (mock)'
        self.reading_pub.publish(reading)


def main(args=None):
    rclpy.init(args=args)
    node = MockPowderSceneNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
