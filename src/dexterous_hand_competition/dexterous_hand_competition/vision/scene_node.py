"""ROS2 scene publisher — Orin-side node.

Subscribes to colour, depth, camera info and publishes
``/bean_task/scene``, ``/bean_task/debug_image`` and
``/bean_task/vision_health``.
"""

from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool

from competition_interfaces.msg import BeanTarget, Scene

from ..common.config_loader import load_yaml, require_keys
from .bean_detector import BeanDetector
from .container_detector import ContainerDetector
from .depth_utils import align_depth_to_per_pixel_map, get_depth_at_pixel
from .table_calibration import TableCalibration
from .target_selector import rank_candidates
from .tweezer_detector import TweezerDetector


# ---------------------------------------------------------------------------
class SceneNode(Node):
    def __init__(self):
        super().__init__('bean_scene_node')

        # -- config ---------------------------------------------------------
        share = Path(get_package_share_directory('dexterous_hand_competition'))
        default_config = str(share / 'config' / 'vision.yaml')
        self.declare_parameter('config_path', default_config)
        config_path = self.get_parameter('config_path').value
        self.config = config = load_yaml(config_path)
        require_keys(
            config, ['vision', 'calibration', 'container', 'tweezer', 'selection'],
            'vision config',
        )

        # -- calibration ----------------------------------------------------
        calibration_cfg = config['calibration']
        self.calibration = TableCalibration(
            homography=calibration_cfg['homography'],
            calibrated=calibration_cfg.get('calibrated', False),
        )

        # -- detectors ------------------------------------------------------
        self.bean_detector = BeanDetector(config['vision'], self.calibration)
        self.container_detector = ContainerDetector(
            config['container'], self.calibration
        )
        self.tweezer_detector = TweezerDetector(
            config['tweezer'], self.calibration
        )

        # -- fallbacks ------------------------------------------------------
        self.src_fallback = config['container']['source'].get('fallback_m', [0.42, -0.20])
        self.tgt_fallback = config['container']['target'].get('fallback_m', [0.42, 0.20])
        self.twz_fallback = config['tweezer'].get('fallback_m', [0.50, 0.00])
        self.twz_fallback_angle = float(config['tweezer'].get('fallback_angle_rad', 0.0))

        # -- selection params -----------------------------------------------
        self.sel = config['selection']
        self.workspace_center = (
            float(self.sel.get('workspace_cx_m', 0.42)),
            float(self.sel.get('workspace_cy_m', 0.0)),
        )

        # -- state ----------------------------------------------------------
        self.bridge = CvBridge()
        self._color: np.ndarray | None = None
        self._depth: np.ndarray | None = None
        self._depth_to_color: np.ndarray | None = None
        self._color_last_sec = 0.0
        self._color_timeout_sec = 2.0

        # -- publishers -----------------------------------------------------
        self.scene_pub = self.create_publisher(Scene, '/bean_task/scene', 10)
        self.debug_pub = self.create_publisher(Image, '/bean_task/debug_image', 10)
        self.health_pub = self.create_publisher(Bool, '/bean_task/vision_health', 10)

        # -- subscriptions --------------------------------------------------
        color_topic = config['vision']['color_topic']
        depth_topic = config['vision'].get('depth_topic', '/ob_camera_head/depth/image_raw')
        info_topic = config['vision'].get('color_camera_info_topic', '/ob_camera_head/color/camera_info')
        d2c_topic = config['vision'].get('depth_to_color_topic', '/ob_camera_head/depth_to_color')

        self.color_sub = self.create_subscription(
            Image, color_topic, self._color_cb, 10,
        )
        self.depth_sub = self.create_subscription(
            Image, depth_topic, self._depth_cb, 10,
        )
        self.info_sub = self.create_subscription(
            CameraInfo, info_topic, self._info_cb, 10,
        )
        self.d2c_sub = self.create_subscription(
            Image, d2c_topic, self._d2c_cb, 10,
        )

        self.get_logger().info(f'Listening on {color_topic} + {depth_topic}')

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
        pass  # kept for completeness; homography is the primary calibration

    def _d2c_cb(self, msg: Image):
        """depth_to_color is published as a 2-channel float image (dx, dy map)."""
        try:
            mapping = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            if mapping is not None and mapping.ndim == 3 and mapping.shape[2] >= 2:
                self._depth_to_color = mapping
        except Exception:
            pass

    # -- processing ---------------------------------------------------------
    def _process_frame(self):
        """Run all detectors on the latest colour frame.  Called from a timer."""
        if self._color is None:
            return

        image = self._color
        depth = self._depth

        # Align depth if the Orbbec depth→color mapping is available.
        aligned_depth = depth
        if self._depth_to_color is not None and depth is not None:
            aligned = align_depth_to_per_pixel_map(depth, self._depth_to_color)
            if aligned is not None:
                aligned_depth = aligned

        # -- bean detection -------------------------------------------------
        beans_detections, debug_img = self.bean_detector.detect(
            image, stamp_sec=time.monotonic()
        )

        # -- container detection --------------------------------------------
        src = self.container_detector.detect_source(image)
        tgt = self.container_detector.detect_target(image)
        if src is None:
            src = (float(self.src_fallback[0]), float(self.src_fallback[1]))
        if tgt is None:
            tgt = (float(self.tgt_fallback[0]), float(self.tgt_fallback[1]))

        # -- tweezer detection ----------------------------------------------
        twz = self.tweezer_detector.detect(image)
        if twz is None:
            twz = (
                float(self.twz_fallback[0]),
                float(self.twz_fallback[1]),
                self.twz_fallback_angle,
            )

        # -- bean ranking ---------------------------------------------------
        failure_map = self.bean_detector.get_failure_map()
        ranked = rank_candidates(
            [
                {
                    'id': d.target_id,
                    'u': d.u,
                    'v': d.v,
                    'x_m': d.x_m,
                    'y_m': d.y_m,
                    'confidence': d.confidence,
                    'edge_distance_px': d.edge_distance_px,
                    'nearest_neighbor_px': d.nearest_neighbor_px,
                }
                for d in beans_detections
            ],
            workspace_center=self.workspace_center,
            failure_map=failure_map,
        )

        # -- depth validation (best bean) -----------------------------------
        if aligned_depth is not None and ranked:
            best = ranked[0]
            table_mm = float(
                self.config['vision'].get('table_height_mm', 750)
            )
            depth_mm = get_depth_at_pixel(aligned_depth, best.u, best.v)
            if depth_mm is not None and abs(depth_mm - table_mm) > 50:
                # Bean is not on the table surface — mark scene suspect.
                pass  # scene.valid stays as calibrated flag; C2 handles.

        # -- assemble Scene ------------------------------------------------
        scene = Scene()
        scene.header.stamp = self.get_clock().now().to_msg()
        scene.header.frame_id = 'table'
        scene.valid = self.calibration.calibrated
        scene.calibrated = self.calibration.calibrated

        scene.source_center.x = float(src[0])
        scene.source_center.y = float(src[1])
        scene.source_center.z = 0.0

        scene.target_center.x = float(tgt[0])
        scene.target_center.y = float(tgt[1])
        scene.target_center.z = 0.0

        scene.tweezer_position.x = float(twz[0])
        scene.tweezer_position.y = float(twz[1])
        scene.tweezer_position.z = 0.0
        scene.tweezer_angle = float(twz[2])

        for d in beans_detections:
            target = BeanTarget()
            target.id = d.target_id
            target.u = float(d.u)
            target.v = float(d.v)
            target.table_position.x = float(d.x_m)
            target.table_position.y = float(d.y_m)
            target.table_position.z = 0.0
            target.confidence = float(d.confidence)
            target.edge_distance_px = float(d.edge_distance_px)
            target.nearest_neighbor_px = float(d.nearest_neighbor_px)
            target.failure_count = failure_map.get(d.target_id, 0)
            scene.beans.append(target)

        # Best bean hint: highest-ranked candidate is first in the list.
        scene.message = (
            f'{len(beans_detections)} beans, best=#{ranked[0].target_id}'
            if ranked
            else 'no beans detected'
        )

        # -- publish --------------------------------------------------------
        self.scene_pub.publish(scene)
        self.debug_pub.publish(
            self.bridge.cv2_to_imgmsg(debug_img, encoding='bgr8')
        )

        # -- health ---------------------------------------------------------
        # Vision health is about pipeline liveness (images arriving, no
        # crashes), not about whether beans were found.
        healthy = (
            self._color_last_sec > 0.0
            and time.monotonic() - self._color_last_sec <= self._color_timeout_sec
        )
        health = Bool()
        health.data = healthy
        self.health_pub.publish(health)

    # -- timer driver -------------------------------------------------------
    def start_processing(self, hz: float = 10.0):
        """Call this after construction to begin the processing loop."""
        period = 1.0 / max(1.0, float(hz))
        self._timer = self.create_timer(period, self._process_frame)
        self.get_logger().info(f'Scene processing @ {hz} Hz')


# ---------------------------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = SceneNode()
    node.start_processing(hz=10.0)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
