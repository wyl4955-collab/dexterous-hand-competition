import numpy as np

from dexterous_hand_competition.vision.depth_utils import (
    get_depth_at_pixel,
    validate_table_height,
)


class TestGetDepthAtPixel:
    def test_returns_median_of_patch(self):
        depth = np.array([
            [100, 200, 300],
            [400, 500, 600],
            [700, 800, 900],
        ], dtype=np.uint16)
        val = get_depth_at_pixel(depth, 1.0, 1.0, patch_radius=1)
        # 3x3 patch median of 100..900 = 500
        assert val == 500.0

    def test_ignores_zero_pixels(self):
        depth = np.array([
            [0, 0, 0],
            [0, 600, 0],
            [0, 0, 0],
        ], dtype=np.uint16)
        val = get_depth_at_pixel(depth, 1.0, 1.0, patch_radius=1)
        assert val == 600.0

    def test_returns_none_when_all_zero(self):
        depth = np.zeros((10, 10), dtype=np.uint16)
        assert get_depth_at_pixel(depth, 5.0, 5.0) is None

    def test_returns_none_for_none_input(self):
        assert get_depth_at_pixel(None, 0, 0) is None

    def test_returns_none_for_empty(self):
        assert get_depth_at_pixel(np.array([]), 0, 0) is None

    def test_clamps_to_image_bounds(self):
        depth = np.ones((5, 5), dtype=np.uint16) * 300
        val = get_depth_at_pixel(depth, 4.0, 4.0, patch_radius=1)
        assert val == 300.0

    def test_out_of_bounds_returns_none(self):
        depth = np.ones((5, 5), dtype=np.uint16) * 300
        assert get_depth_at_pixel(depth, 100.0, 100.0) is None


class TestValidateTableHeight:
    def test_within_tolerance(self):
        assert validate_table_height(750.0, 750.0, 30.0) is True

    def test_outside_tolerance(self):
        assert validate_table_height(800.0, 750.0, 30.0) is False

    def test_edge_of_tolerance(self):
        assert validate_table_height(780.0, 750.0, 30.0) is True
        assert validate_table_height(781.0, 750.0, 30.0) is False
