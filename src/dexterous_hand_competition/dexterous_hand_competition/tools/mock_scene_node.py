"""Publish a valid synthetic bean scene for FSM dry-run development."""

import rclpy
from rclpy.node import Node

from competition_interfaces.msg import BeanTarget, Scene


class MockSceneNode(Node):
    def __init__(self):
        super().__init__('mock_scene_node')
        self.publisher = self.create_publisher(Scene, '/bean_task/scene', 10)
        self.create_timer(0.2, self._publish)
        self.get_logger().warning(
            'Publishing synthetic scene data; never use this node for a real task'
        )

    def _publish(self):
        scene = Scene()
        scene.header.stamp = self.get_clock().now().to_msg()
        scene.header.frame_id = 'table'
        scene.valid = True
        scene.calibrated = True
        scene.source_center.x = 0.45
        scene.source_center.y = -0.20
        scene.target_center.x = 0.45
        scene.target_center.y = 0.20
        scene.tweezer_position.x = 0.50
        scene.tweezer_position.y = 0.00
        scene.tweezer_position.z = 0.0
        scene.tweezer_angle = 0.0
        scene.message = 'synthetic dry-run scene'

        target = BeanTarget()
        target.id = 1
        target.u = 640.0
        target.v = 360.0
        target.table_position.x = 0.45
        target.table_position.y = -0.20
        target.confidence = 1.0
        target.edge_distance_px = 100.0
        target.nearest_neighbor_px = 9999.0
        target.failure_count = 0
        scene.beans.append(target)
        self.publisher.publish(scene)


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

