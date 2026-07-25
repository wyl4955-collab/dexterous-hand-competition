#!/usr/bin/env python3
"""
Perception Node — the "eyes" of the competition system.

Publishes:
  /vision/beans       (BeanDetections) — detected bean positions in world frame
  /vision/tool        (ToolState)      — tweezers/spoon tip position
  /vision/scale       (Float32)        — scale weight reading (grams)
  /vision/debug       (Image)          — annotated debug image

Subscribes:
  /camera/color/image_raw  (Image)     — from RealSense or USB camera
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
from cv_bridge import CvBridge

from .bean_detector import BeanDetector
from .tool_detector import ToolDetector
from .scale_reader import ScaleReader
from .world_state import WorldState, BeanInfo, ToolInfo


class PerceptionNode(Node):
    """Main perception node — fuses all sensor data into WorldState."""

    def __init__(self):
        super().__init__('perception_node')

        # Load config
        self.declare_parameter('camera_topic', '/camera/color/image_raw')
        self.declare_parameter('publish_debug', True)

        # Components
        self.bridge = CvBridge()
        self.bean_detector = BeanDetector()
        self.tool_detector = ToolDetector()
        self.scale_reader = ScaleReader()

        # Shared world state (thread-safe)
        self.world = WorldState()

        # Publishers
        self.beans_pub = self.create_publisher(
            BeanDetections, '/vision/beans', 10)
        self.tool_pub = self.create_publisher(
            ToolState, '/vision/tool', 10)
        self.scale_pub = self.create_publisher(
            Float32, '/vision/scale', 10)
        self.debug_pub = self.create_publisher(
            Image, '/vision/debug', 10)  # only if publish_debug is True

        # Subscriber
        self.camera_sub = self.create_subscription(
            Image,
            self.get_parameter('camera_topic').value,
            self.image_callback,
            10)

        # Scale polling timer (independent of camera, 10 Hz)
        self.scale_timer = self.create_timer(0.1, self.scale_timer_callback)

        # State publishing timer (20 Hz)
        self.pub_timer = self.create_timer(0.05, self.publish_state)

        self.get_logger().info('Perception node started')

    # ========== Image callback ==========
    def image_callback(self, msg: Image):
        """Process each camera frame: detect beans + tool."""
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'Image conversion failed: {e}')
            return

        # Detect beans
        beans = self.bean_detector.detect(frame)

        # Detect tool tip
        tool = self.tool_detector.detect(frame)

        # Update world state
        self.world.update(
            beans=beans,
            tool=tool,
            raw_image=frame if self.get_parameter('publish_debug').value else None
        )

    # ========== Scale polling ==========
    def scale_timer_callback(self):
        """Poll scale at 10Hz."""
        weight = self.scale_reader.read()
        self.world.update(scale_weight=weight)

    # ========== State publishing ==========
    def publish_state(self):
        """Publish world state at 20Hz."""
        snap = self.world.snapshot()

        # Publish bean detections
        bean_msg = BeanDetections()
        bean_msg.header.stamp = self.get_clock().now().to_msg()
        bean_msg.header.frame_id = 'table'
        for b in snap['beans']:
            bd = BeanDetection()
            bd.x = b.world_x
            bd.y = b.world_y
            bd.radius = b.radius_px
            bd.confidence = b.confidence
            bean_msg.beans.append(bd)
        self.beans_pub.publish(bean_msg)

        # Publish tool state
        tool = snap['tool']
        if tool is not None:
            tool_msg = ToolState()
            tool_msg.tip_x = tool.world_x
            tool_msg.tip_y = tool.world_y
            tool_msg.tip_z = tool.world_z
            tool_msg.detected = True
            self.tool_pub.publish(tool_msg)

        # Publish scale weight
        if snap['scale_weight'] is not None:
            self.scale_pub.publish(Float32(data=snap['scale_weight']))

        # Publish debug image
        if self.get_parameter('publish_debug').value and snap.get('raw_image') is not None:
            annotated = self.bean_detector.draw(snap['raw_image'], snap['beans'])
            debug_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            debug_msg.header.stamp = self.get_clock().now().to_msg()
            self.debug_pub.publish(debug_msg)


def main():
    rclpy.init()
    node = PerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
