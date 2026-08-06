"""ROS2 scene publisher intended to run on Orin."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool

from competition_interfaces.msg import BeanTarget, Scene

from ..common.config_loader import load_yaml, require_keys
from .bean_detector import BeanDetector
from .table_calibration import TableCalibration


class SceneNode(Node):
    def __init__(self):
        super().__init__('bean_scene_node')
        share = Path(get_package_share_directory('dexterous_hand_competition'))
        default_config = str(share / 'config' / 'vision.yaml')
        self.declare_parameter('config_path', default_config)
        config_path = self.get_parameter('config_path').value
        config = load_yaml(config_path)
        require_keys(config, ['vision', 'calibration'], 'vision config')

        calibration_cfg = config['calibration']
        calibration = TableCalibration(
            calibration_cfg['homography'],
            calibrated=calibration_cfg.get('calibrated', False),
        )
        self.detector = BeanDetector(config['vision'], calibration)
        self.calibrated = calibration.calibrated
        self.target_center = config['vision']['target_center_m']

        self.bridge = CvBridge()
        self.scene_pub = self.create_publisher(Scene, '/bean_task/scene', 10)
        self.debug_pub = self.create_publisher(
            Image, '/bean_task/debug_image', 10
        )
        self.health_pub = self.create_publisher(
            Bool, '/bean_task/vision_health', 10
        )
        image_topic = config['vision']['color_topic']
        self.image_sub = self.create_subscription(
            Image, image_topic, self._image_callback, 10
        )
        self.get_logger().info(f'Listening for color images on {image_topic}')

    def _image_callback(self, image_msg: Image):
        health = Bool()
        try:
            image = self.bridge.imgmsg_to_cv2(image_msg, 'bgr8')
            detections, debug = self.detector.detect(image)

            scene = Scene()
            scene.header = image_msg.header
            scene.valid = self.calibrated
            scene.calibrated = self.calibrated
            scene.target_center.x = float(self.target_center[0])
            scene.target_center.y = float(self.target_center[1])
            scene.target_center.z = 0.0
            scene.message = (
                f'{len(detections)} bean candidates'
                if self.calibrated
                else 'camera-table calibration is not complete'
            )

            for detection in detections:
                target = BeanTarget()
                target.id = detection.target_id
                target.u = float(detection.u)
                target.v = float(detection.v)
                target.table_position.x = float(detection.x_m)
                target.table_position.y = float(detection.y_m)
                target.table_position.z = 0.0
                target.confidence = float(detection.confidence)
                target.edge_distance_px = float(detection.edge_distance_px)
                target.nearest_neighbor_px = float(
                    detection.nearest_neighbor_px
                )
                target.failure_count = 0
                scene.beans.append(target)

            self.scene_pub.publish(scene)
            self.debug_pub.publish(
                self.bridge.cv2_to_imgmsg(debug, encoding='bgr8')
            )
            health.data = True
        except Exception as error:  # keep the node alive for later frames
            self.get_logger().error(f'Vision frame failed: {error}')
            health.data = False
        self.health_pub.publish(health)


def main(args=None):
    rclpy.init(args=args)
    node = SceneNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

