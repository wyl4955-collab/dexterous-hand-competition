#!/usr/bin/env python3
"""Perception node — publishes bean positions, tool state, scale weight."""
import cv2, numpy as np, serial, re, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
from cv_bridge import CvBridge
from competition_interfaces.msg import BeanDetections, BeanDetection, ToolState


class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node')
        self.declare_parameter('camera_topic', '/camera/color/image_raw')
        self.declare_parameter('scale_port', '/dev/ttyUSB1')
        self.declare_parameter('fps', 20)

        self.bridge = CvBridge()
        self._beans = []
        self._tool = None
        self._scale_weight = None
        self._image = None

        # Scale serial
        try:
            self.scale_ser = serial.Serial(
                self.get_parameter('scale_port').value, 9600, timeout=0.3)
        except Exception:
            self.scale_ser = None

        # Publishers
        self.beans_pub = self.create_publisher(BeanDetections, '/vision/beans', 10)
        self.tool_pub = self.create_publisher(ToolState, '/vision/tool', 10)
        self.scale_pub = self.create_publisher(Float32, '/vision/scale', 10)
        self.debug_pub = self.create_publisher(Image, '/vision/debug', 10)

        # Subscriber
        self.create_subscription(Image, self.get_parameter('camera_topic').value,
                                 self._image_cb, 10)
        # Timer for scale + publish
        self.create_timer(0.05, self._timer_cb)

        self.get_logger().info('Perception node started')

    # ── Image processing ──
    def _image_cb(self, msg):
        try:
            self._image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception:
            return
        hsv = cv2.cvtColor(self._image, cv2.COLOR_BGR2HSV)
        # Bean detection: yellow/green color range
        mask = cv2.inRange(hsv, np.array([15,50,50]), np.array([85,255,255]))
        mask = cv2.erode(mask, np.ones((3,3),np.uint8), iterations=1)
        mask = cv2.dilate(mask, np.ones((3,3),np.uint8), iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        beans = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 30 or area > 800: continue
            perim = cv2.arcLength(cnt, True)
            if perim < 1: continue
            circ = 4*np.pi*area/(perim*perim)
            if circ < 0.5: continue
            M = cv2.moments(cnt)
            if M['m00'] < 1: continue
            cx, cy = M['m10']/M['m00'], M['m01']/M['m00']
            beans.append(BeanDetection(x=cx*0.3, y=cy*0.3,
                         radius=np.sqrt(area/np.pi), confidence=min(circ,1.0)))
        # Sort by y (far to near)
        beans.sort(key=lambda b: b.y)
        self._beans = beans
        # Tool detection: bright elongated thin object
        gray = cv2.cvtColor(self._image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        tcnt, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None; best_score = 0
        for c in tcnt:
            a = cv2.contourArea(c)
            if a < 100 or a > 3000: continue
            rect = cv2.minAreaRect(c)
            w, h = rect[1]
            if min(w,h) == 0: continue
            ar = max(w,h)/min(w,h)
            if ar > 3 and a*ar > best_score:
                best_score = a*ar
                M = cv2.moments(c)
                if M['m00'] > 0:
                    cx, cy = M['m10']/M['m00'], M['m01']/M['m00']
                    tip = max(c, key=lambda p: (p[0][0]-cx)**2+(p[0][1]-cy)**2
                              if p[0][1] > cy else 0)
                    best = ToolState(tip_x=tip[0][0]*0.3, tip_y=tip[0][1]*0.3,
                                     tip_z=0, detected=True)
        self._tool = best

    # ── Scale reading ──
    def _read_scale(self):
        if self.scale_ser is None: return None
        try:
            self.scale_ser.reset_input_buffer()
            line = self.scale_ser.readline()
            m = re.search(r'[+-]?\d+\.?\d*', line.decode('ascii', errors='ignore'))
            if m:
                v = float(m.group())
                if 0 <= v <= 500: return v
        except Exception:
            pass
        return None

    # ── Timer: publish all ──
    def _timer_cb(self):
        now = self.get_clock().now().to_msg()
        # Beans
        bm = BeanDetections()
        bm.header.stamp = now; bm.header.frame_id = 'table'
        bm.beans = self._beans
        self.beans_pub.publish(bm)
        # Tool
        if self._tool:
            self._tool.header = bm.header
            self.tool_pub.publish(self._tool)
        # Scale
        w = self._read_scale()
        if w is not None:
            self.scale_pub.publish(Float32(data=w))
        # Debug
        if self._image is not None:
            vis = self._image.copy()
            for b in self._beans:
                cv2.circle(vis, (int(b.x/0.3), int(b.y/0.3)), int(b.radius), (0,255,0), 2)
            self.debug_pub.publish(self.bridge.cv2_to_imgmsg(vis, 'bgr8'))


def main():
    rclpy.init()
    rclpy.spin(PerceptionNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
