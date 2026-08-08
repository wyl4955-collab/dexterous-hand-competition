"""Locate 160 mm curved medical tweezers on the table.

Strategy: tweezers are metallic → high brightness in gray-scale.  We search a
configurable ROI, threshold, and pick the most elongated contour.  The
returned angle is the orientation of the fitted ellipse with respect to the
horizontal axis (radians).
"""

import cv2
import math
import numpy as np

from .table_calibration import TableCalibration


class TweezerDetector:
    def __init__(self, config: dict, calibration: TableCalibration):
        roi = config.get('roi', {})
        self.roi = {
            'x': int(roi.get('x', 0)),
            'y': int(roi.get('y', 0)),
            'width': int(roi.get('width', 280)),
            'height': int(roi.get('height', 320)),
        }
        self.gray_threshold = int(config.get('gray_threshold', 180))
        self.min_area = float(config.get('min_area_px', 500))
        self.max_area = float(config.get('max_area_px', 8000))
        self.min_elongation = float(config.get('min_elongation', 3.0))
        self.morph_kernel = int(config.get('morph_kernel', 3))
        self.calibration = calibration

    def detect(self, image_bgr: np.ndarray) -> tuple[float, float, float] | None:
        """Return (x_m, y_m, angle_rad) or None."""
        h, w = image_bgr.shape[:2]
        rx, ry = self.roi['x'], self.roi['y']
        rw, rh = self.roi['width'], self.roi['height']

        if rx < 0 or ry < 0 or rw <= 0 or rh <= 0:
            return None
        if rx + rw > w or ry + rh > h:
            return None

        roi_img = image_bgr[ry:ry + rh, rx:rx + rw]
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)

        _, binary = cv2.threshold(
            gray, self.gray_threshold, 255, cv2.THRESH_BINARY
        )

        k = max(1, int(self.morph_kernel) | 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        best = None
        best_elongation = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue
            rect = cv2.minAreaRect(cnt)
            w_rect, h_rect = rect[1]
            if w_rect < 1e-6 and h_rect < 1e-6:
                continue
            long_side = max(w_rect, h_rect)
            short_side = min(w_rect, h_rect)
            if short_side < 1.0:
                continue
            elongation = long_side / short_side
            if elongation < self.min_elongation:
                continue
            if elongation > best_elongation:
                best_elongation = elongation
                moments = cv2.moments(cnt)
                if moments['m00'] == 0.0:
                    continue
                local_u = moments['m10'] / moments['m00'] + rx
                local_v = moments['m01'] / moments['m00'] + ry
                angle_rad = math.radians(rect[2])
                best = (local_u, local_v, angle_rad)

        if best is None:
            return None

        u, v, angle = best
        table = self.calibration.pixel_to_table(u, v)
        if table is None:
            return None
        return float(table[0]), float(table[1]), angle
