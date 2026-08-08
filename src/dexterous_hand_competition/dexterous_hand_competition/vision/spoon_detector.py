"""Detect metallic spoons of various sizes on the table.

Spoons have a two-part structure: a rounded bowl and an elongated handle.
We detect them via gray-level thresholding in a configurable ROI, shape
filtering, and classify them into three size categories based on contour area.
"""

from dataclasses import dataclass

import cv2
import math
import numpy as np

from .table_calibration import TableCalibration


@dataclass(frozen=True)
class SpoonTarget:
    x_m: float
    y_m: float
    angle_rad: float
    size_category: str       # "large" | "medium" | "small"
    area_px: float


class SpoonDetector:
    """Detect all spoons in the configured spoon-placement ROI."""

    def __init__(self, config: dict, calibration: TableCalibration):
        roi = config.get('roi', {})
        self.roi = {
            'x': int(roi.get('x', 800)),
            'y': int(roi.get('y', 300)),
            'width': int(roi.get('width', 400)),
            'height': int(roi.get('height', 400)),
        }
        self.gray_threshold = int(config.get('gray_threshold', 160))
        self.min_area = float(config.get('min_area_px', 500))
        self.max_area = float(config.get('max_area_px', 15000))
        self.morph_kernel = int(config.get('morph_kernel', 3))

        thresholds = config.get('size_thresholds', {})
        self.large_threshold = float(thresholds.get('large_px', 3000))
        self.medium_threshold = float(thresholds.get('medium_px', 1000))

        self.calibration = calibration

    # ------------------------------------------------------------------
    def detect(self, image_bgr: np.ndarray) -> list[SpoonTarget]:
        """Return all detected spoons, sorted large→small."""
        h, w = image_bgr.shape[:2]
        rx, ry = self.roi['x'], self.roi['y']
        rw, rh = self.roi['width'], self.roi['height']

        if rx < 0 or ry < 0 or rw <= 0 or rh <= 0:
            return []
        if rx + rw > w or ry + rh > h:
            return []

        roi_img = image_bgr[ry:ry + rh, rx:rx + rw]
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)

        _, binary = cv2.threshold(
            gray, self.gray_threshold, 255, cv2.THRESH_BINARY,
        )

        k = max(1, int(self.morph_kernel) | 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        spoons = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue

            rect = cv2.minAreaRect(cnt)
            w_rect, h_rect = rect[1]
            if w_rect < 1.0 or h_rect < 1.0:
                continue

            # A spoon should have a bowl (wider region) + handle (narrower).
            # minAreaRect's long/short ratio helps filter out noise.
            long_side = max(w_rect, h_rect)
            short_side = min(w_rect, h_rect)
            elongation = long_side / short_side
            if elongation < 1.2:
                continue

            moments = cv2.moments(cnt)
            if moments['m00'] == 0.0:
                continue
            local_u = moments['m10'] / moments['m00'] + rx
            local_v = moments['m01'] / moments['m00'] + ry
            angle_rad = math.radians(rect[2])

            # Classify size.
            if area >= self.large_threshold:
                size_cat = 'large'
            elif area >= self.medium_threshold:
                size_cat = 'medium'
            else:
                size_cat = 'small'

            table = self.calibration.pixel_to_table(local_u, local_v)
            if table is None:
                continue

            spoons.append(
                SpoonTarget(
                    x_m=float(table[0]),
                    y_m=float(table[1]),
                    angle_rad=angle_rad,
                    size_category=size_cat,
                    area_px=area,
                )
            )

        spoons.sort(key=lambda s: s.area_px, reverse=True)
        return spoons
