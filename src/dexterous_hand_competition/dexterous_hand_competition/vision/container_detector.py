"""Detect source and target containers on the table via colour segmentation.

When detection fails the caller should fall back to the calibrated positions
stored in vision.yaml.
"""

import cv2
import numpy as np

from .table_calibration import TableCalibration


class ContainerDetector:
    def __init__(
        self,
        config: dict,
        calibration: TableCalibration,
    ):
        source = config.get('source', {})
        target = config.get('target', {})

        self.source_lower = np.array(
            source.get('hsv_lower', [0, 0, 0]), dtype=np.uint8
        )
        self.source_upper = np.array(
            source.get('hsv_upper', [180, 255, 255]), dtype=np.uint8
        )
        self.source_min_area = float(source.get('min_area_px', 3000))

        self.target_lower = np.array(
            target.get('hsv_lower', [0, 0, 0]), dtype=np.uint8
        )
        self.target_upper = np.array(
            target.get('hsv_upper', [180, 255, 255]), dtype=np.uint8
        )
        self.target_min_area = float(target.get('min_area_px', 3000))

        self.morph_kernel = int(config.get('morph_kernel', 5))
        self.calibration = calibration

    # ------------------------------------------------------------------
    def detect_source(self, image_bgr: np.ndarray) -> tuple[float, float] | None:
        """Return (x_m, y_m) of the source-container centre on the table."""
        return self._detect_one(
            image_bgr, self.source_lower, self.source_upper, self.source_min_area
        )

    def detect_target(self, image_bgr: np.ndarray) -> tuple[float, float] | None:
        """Return (x_m, y_m) of the target-container centre on the table."""
        return self._detect_one(
            image_bgr, self.target_lower, self.target_upper, self.target_min_area
        )

    # ------------------------------------------------------------------
    def _detect_one(
        self,
        image_bgr: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        min_area: float,
    ) -> tuple[float, float] | None:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)

        k = max(1, int(self.morph_kernel) | 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        best = None
        best_area = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            if area > best_area:
                best_area = area
                moments = cv2.moments(cnt)
                if moments['m00'] == 0.0:
                    continue
                best = (
                    moments['m10'] / moments['m00'],
                    moments['m01'] / moments['m00'],
                )

        if best is None:
            return None

        u, v = best
        table = self.calibration.pixel_to_table(u, v)
        if table is None:
            return None
        return float(table[0]), float(table[1])

    # ------------------------------------------------------------------
    def debug_masks(self, image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (source_mask, target_mask) for visual inspection."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        src = cv2.inRange(hsv, self.source_lower, self.source_upper)
        tgt = cv2.inRange(hsv, self.target_lower, self.target_upper)
        return src, tgt
