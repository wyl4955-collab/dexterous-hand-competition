"""ROS2 scene publisher for the powder-weighing task — Orin-side node.

Publishes ``/powder_task/scene``, ``/powder_task/scale_reading`` and
``/powder_task/vision_health``.
"""

from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Bool

from competition_interfaces.msg import PowderScene, ScaleReading

from ..common.config_loader import load_yaml, require_keys
from .container_detector import ContainerDetector
from .depth_utils import get_depth_at_pixel
from .scale_reader import ScaleReader
from .spoon_detector import SpoonDetector
from .table_calibration import TableCalibration


class PowderSceneNode(Node):
    def __init__(self):
        super().__init__('powder_scene_node')

        # -- config ---------------------------------------------------------
        share = Path(get_package_share_directory('dexterous_hand_competition'))
        default_config = str(share / 'config' / 'powder_vision.yaml')
        self.declare_parameter('config_path', default_config)
        config_path = self.get_parameter('config_path').value
        self.config = config = load_yaml(config_path)
        require_keys(
            config,
            ['powder_container', 'scale', 'spoon', 'calibration'],
            'powder vision config',
        )

        # -- calibration ----------------------------------------------------
        calibration_cfg = config['calibration']
        self.calibration = TableCalibration(
            homography=calibration_cfg['homography'],
            calibrated=calibration_cfg.get('calibrated', False),
        )

        # -- detectors ------------------------------------------------------
        self.container_detector = ContainerDetector(
            {'source': config['powder_container'], 'morph_kernel': config['powder_container'].get('morph_kernel', 5)},
            self.calibration,
        )
        self.spoon_detector = SpoonDetector(config['spoon'], self.calibration)
        self.scale_reader = ScaleReader(config['scale'])

        # -- fallbacks ------------------------------------------------------
        self.container_fallback = config['powder_container'].get('fallback_m', [0.35, -0.20])
        self.scale_fallback = config['scale'].get('fallback_m', [0.45, 0.0])
        self.spoon_fallbacks = config['spoon'].get('fallback_spoons', [])

        # -- state ----------------------------------------------------------
        self.bridge = CvBridge()
        self._color: np.ndarray | None = None
        self._depth: np.ndarray | None = None
        self._color_last_sec = 0.0
        self._color_timeout_sec = 2.0

        # -- publishers -----------------------------------------------------
        self.scene_pub = self.create_publisher(PowderScene, '/powder_task/scene', 10)
        self.reading_pub = self.create_publisher(ScaleReading, '/powder_task/scale_reading', 10)
        self.health_pub = self.create_publisher(Bool, '/powder_task/vision_health', 10)

        # -- subscriptions --------------------------------------------------
        color_topic = config.get('color_topic', '/ob_camera_head/color/image_raw')
        depth_topic = config.get('depth_topic', '/ob_camera_head/depth/image_raw')

        self.color_sub = self.create_subscription(
            Image, color_topic, self._color_cb, 10,
        )
        self.depth_sub = self.create_subscription(
            Image, depth_topic, self._depth_cb, 10,
        )
        self.info_sub = self.create_subscription(
            CameraInfo, '/ob_camera_head/color/camera_info', self._info_cb, 10,
        )

        self.get_logger().info(f'PowderSceneNode listening on {color_topic}')

    # -- callbacks ----------------------------------------------------------
    def _color_cb(self, msg: Image):
        try:
            self._color = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            self._color_last_sec = time.monotonic()
        except Exception as exc:
            self.get_logger().error(f'color decode: {exc}')

    def _depth_cb(self, msg: Image):
        try:
            self._depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono16')
        except Exception as exc:
            self.get_logger().error(f'depth decode: {exc}')

    def _info_cb(self, msg: CameraInfo):
        pass

    # -- processing ---------------------------------------------------------
    def _process_frame(self):
        if self._color is None:
            return

        image = self._color

        # -- container detection --------------------------------------------
        container = self.container_detector.detect_source(image)
        if container is None:
            container = (float(self.container_fallback[0]), float(self.container_fallback[1]))

        # -- scale centre detection (use container detector with scale HSV) --
        scale_center = container  # fallback; scale detector uses fixed ROI for now
        scale_roi_config = self.config['scale']
        sh_lower = scale_roi_config.get('hsv_lower', [0, 0, 180])
        sh_upper = scale_roi_config.get('hsv_upper', [180, 30, 255])
        # Simple: find brightest/largest white region near the expected scale position.
        scale_center = self._find_scale_center(image, sh_lower, sh_upper)
        if scale_center is None:
            scale_center = (float(self.scale_fallback[0]), float(self.scale_fallback[1]))

        # -- spoon detection ------------------------------------------------
        spoons = self.spoon_detector.detect(image)
        if not spoons:
            spoons = [
                type('SpoonFallback', (), {
                    'x_m': sf['x_m'], 'y_m': sf['y_m'],
                    'angle_rad': sf.get('angle_rad', 0.0),
                    'size_category': sf.get('size', 'medium'),
                    'area_px': 0.0,
                })()
                for sf in self.spoon_fallbacks
            ]

        # -- scale reading --------------------------------------------------
        scale_result = self.scale_reader.read(image)

        # -- assemble PowderScene -------------------------------------------
        scene = PowderScene()
        scene.header.stamp = self.get_clock().now().to_msg()
        scene.header.frame_id = 'table'
        scene.valid = self.calibration.calibrated
        scene.calibrated = self.calibration.calibrated

        scene.powder_container_center.x = float(container[0])
        scene.powder_container_center.y = float(container[1])
        scene.powder_container_center.z = 0.0

        scene.scale_center.x = float(scale_center[0])
        scene.scale_center.y = float(scale_center[1])
        scene.scale_center.z = 0.0

        for spoon in spoons:
            scene.spoon_categories.append(spoon.size_category)
            scene.spoon_x_m.append(float(spoon.x_m))
            scene.spoon_y_m.append(float(spoon.y_m))
            scene.spoon_angle_rad.append(float(spoon.angle_rad))

        scene.message = (
            f'{len(spoons)} spoons, scale={scale_result.value_grams:.1f}g'
            if scale_result
            else f'{len(spoons)} spoons'
        )

        self.scene_pub.publish(scene)

        # -- scale reading --------------------------------------------------
        if scale_result is not None:
            reading = ScaleReading()
            reading.header.stamp = self.get_clock().now().to_msg()
            reading.value_grams = scale_result.value_grams
            reading.confidence = scale_result.confidence
            reading.stable = True
            reading.message = f'{scale_result.value_grams:.1f}g'
        else:
            reading = ScaleReading()
            reading.header.stamp = self.get_clock().now().to_msg()
            reading.value_grams = 0.0
            reading.confidence = 0.0
            reading.stable = False
            reading.message = 'no reading'
        self.reading_pub.publish(reading)

        # -- health ---------------------------------------------------------
        healthy = (
            self._color_last_sec > 0.0
            and time.monotonic() - self._color_last_sec <= self._color_timeout_sec
        )
        health = Bool()
        health.data = healthy
        self.health_pub.publish(health)

    # -- scale centre helper ------------------------------------------------
    def _find_scale_center(self, image, hsv_lower, hsv_upper):
        try:
            import cv2
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            lower = np.array(hsv_lower, dtype=np.uint8)
            upper = np.array(hsv_upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            best = max(contours, key=cv2.contourArea)
            moments = cv2.moments(best)
            if moments['m00'] == 0.0:
                return None
            u = moments['m10'] / moments['m00']
            v = moments['m01'] / moments['m00']
            table = self.calibration.pixel_to_table(u, v)
            if table is None:
                return None
            return float(table[0]), float(table[1])
        except Exception:
            return None

    # -- timer --------------------------------------------------------------
    def start_processing(self, hz: float = 5.0):
        period = 1.0 / max(1.0, float(hz))
        self._timer = self.create_timer(period, self._process_frame)
        self.get_logger().info(f'Powder scene processing @ {hz} Hz')


def main(args=None):
    rclpy.init(args=args)
    node = PowderSceneNode()
    node.start_processing(hz=5.0)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
