#!/usr/bin/env python3
"""Capture synchronised colour + depth frames for offline calibration.

Usage (on Orin)::

    source install/setup.bash
    python3 scripts/collect_data.py --output data/raw

Press Enter to save a frame pair; press q then Enter to quit.
"""

import argparse
import os
import sys
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from cv_bridge import CvBridge


class FrameGrabber(Node):
    def __init__(self):
        super().__init__('frame_grabber')
        self.bridge = CvBridge()
        self._color = None
        self._depth = None
        self._info = None  # type: CameraInfo | None

        self.color_sub = self.create_subscription(
            Image, '/ob_camera_head/color/image_raw',
            self._cb_color, 10,
        )
        self.depth_sub = self.create_subscription(
            Image, '/ob_camera_head/depth/image_raw',
            self._cb_depth, 10,
        )
        self.info_sub = self.create_subscription(
            CameraInfo, '/ob_camera_head/color/camera_info',
            self._cb_info, 10,
        )

    def _cb_color(self, msg: Image):
        try:
            self._color = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception:
            pass

    def _cb_depth(self, msg: Image):
        try:
            self._depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono16')
        except Exception:
            pass

    def _cb_info(self, msg: CameraInfo):
        self._info = msg

    def grab(self) -> tuple[np.ndarray | None, np.ndarray | None, CameraInfo | None]:
        rclpy.spin_once(self, timeout_sec=1.0)
        return self._color, self._depth, self._info


def main():
    parser = argparse.ArgumentParser(description='Collect calibration frames')
    parser.add_argument('--output', default='data/raw', help='output directory')
    args = parser.parse_args()

    rclpy.init()
    grabber = FrameGrabber()

    os.makedirs(args.output, exist_ok=True)
    print(f'Saving frames to {args.output}/')
    print('Press ENTER to capture, q+ENTER to quit.\n')

    count = 0
    try:
        while rclpy.ok():
            color, depth, info = grabber.grab()
            if color is None:
                print('\r  waiting for colour image ...', end='', flush=True)
                continue

            status = []
            if color is not None:
                status.append(f'color {color.shape[1]}x{color.shape[0]}')
            if depth is not None:
                status.append(f'depth {depth.shape[1]}x{depth.shape[0]}')
            if info is not None:
                status.append('info ok')

            print(f'\r  [{" | ".join(status)}] — ENTER to snap, q to quit  ', end='', flush=True)

            # Non-blocking input is hard cross-platform; use a simple blocking
            # read from a separate line.  The user sees the prompt and hits
            # Enter whenever the scene looks right.
            line = sys.stdin.readline().strip().lower()
            if line == 'q':
                break

            ts = time.strftime('%Y%m%d_%H%M%S')
            prefix = os.path.join(args.output, f'frame_{count:04d}_{ts}')

            if color is not None:
                cv2.imwrite(f'{prefix}_color.png', color)
            if depth is not None:
                np.save(f'{prefix}_depth.npy', depth)
            if info is not None:
                k = np.array(info.k).reshape(3, 3)
                d = np.array(info.d)
                np.savez(f'{prefix}_camera_info.npz', K=k, D=d,
                         width=info.width, height=info.height)

            count += 1
            print(f'  saved #{count} → {prefix}_*')

    except KeyboardInterrupt:
        pass
    finally:
        grabber.destroy_node()
        rclpy.shutdown()
        print(f'\nDone. {count} frames saved to {args.output}/')


if __name__ == '__main__':
    main()
