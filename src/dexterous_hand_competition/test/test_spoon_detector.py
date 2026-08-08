"""Unit tests for SpoonDetector (offline, no ROS required)."""

import numpy as np

from dexterous_hand_competition.vision.spoon_detector import (
    SpoonDetector,
    SpoonTarget,
)


def make_detector(calibrated=False):
    from dexterous_hand_competition.vision.table_calibration import TableCalibration
    calib = TableCalibration(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        calibrated=calibrated,
    )
    config = {
        'roi': {'x': 0, 'y': 0, 'width': 640, 'height': 480},
        'gray_threshold': 128,
        'morph_kernel': 3,
        'min_area_px': 100,
        'max_area_px': 50000,
        'size_thresholds': {'large_px': 3000, 'medium_px': 1000},
    }
    return SpoonDetector(config, calib)


def draw_spoon(img, x, y, size=80):
    """Draw a spoon-like shape: an ellipse (bowl) + a rectangle (handle)."""
    cv2 = __import__('cv2')
    # Bowl
    cv2.ellipse(img, (x, y), (15, 10), 0, 0, 360, 255, -1)
    # Handle
    cv2.rectangle(img, (x - 3, y + 10), (x + 3, y + size), 255, -1)
    return img


class TestSpoonDetector:
    def test_empty_image_returns_none(self):
        d = make_detector(calibrated=False)
        img = np.zeros((480, 640), dtype=np.uint8)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        # Uncalibrated → pixel_to_table returns None, so no results
        result = d.detect(img_bgr)
        assert result == []

    def test_calibrated_detects_spoon(self):
        d = make_detector(calibrated=True)
        img = np.zeros((480, 640), dtype=np.uint8)
        draw_spoon(img, 200, 250, size=60)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        result = d.detect(img_bgr)
        assert len(result) > 0
        assert result[0].size_category in ('large', 'medium', 'small')

    def test_roi_out_of_bounds_returns_empty(self):
        from dexterous_hand_competition.vision.table_calibration import TableCalibration
        calib = TableCalibration(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            calibrated=True,
        )
        config = {
            'roi': {'x': -10, 'y': 0, 'width': 100, 'height': 100},
            'gray_threshold': 128, 'morph_kernel': 3,
            'min_area_px': 100, 'max_area_px': 50000,
            'size_thresholds': {'large_px': 3000, 'medium_px': 1000},
        }
        d = SpoonDetector(config, calib)
        img = np.zeros((480, 640), dtype=np.uint8)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        assert d.detect(img_bgr) == []


# Quick import guard for environments without cv2.
try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]
