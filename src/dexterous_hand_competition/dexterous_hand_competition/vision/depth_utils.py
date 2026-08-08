"""Depth image alignment and validation utilities.

Convention: depth values are in millimetres (16UC1 format from Orbbec camera).
"""

import cv2
import numpy as np


def align_depth_to_per_pixel_map(
    depth: np.ndarray,
    d2c_map: np.ndarray,
) -> np.ndarray | None:
    """Warp depth to colour-image space using a per-pixel (dx, dy) map.

    Orbbec publishes ``/ob_camera_head/depth_to_color`` as a ``32FC2`` image
    where channel 0 = dx and channel 1 = dy for every pixel in the *depth*
    image.  This function builds an identity coordinate grid and adds the
    displacement field, then remaps.

    Args:
        depth: raw depth image (H_d, W_d), uint16, units mm.
        d2c_map: displacement map (H_d, W_d, 2), float32, from the
            depth_to_color topic.

    Returns:
        Aligned depth image with shape (H_d, W_d) and dtype uint16, or None
        on failure.
    """
    if depth is None or d2c_map is None:
        return depth
    if depth.size == 0 or d2c_map.size == 0:
        return None
    if d2c_map.ndim < 2 or d2c_map.shape[-1] < 2:
        return None
    try:
        h, w = depth.shape[:2]
        dx = d2c_map[:, :, 0].astype(np.float32)
        dy = d2c_map[:, :, 1].astype(np.float32)
        yv, xv = np.mgrid[0:h, 0:w].astype(np.float32)
        map_x = xv + dx
        map_y = yv + dy
        aligned = cv2.remap(
            depth.astype(np.float32), map_x, map_y,
            cv2.INTER_NEAREST,
        )
        aligned[aligned <= 0] = 0
        return aligned.astype(np.uint16)
    except Exception:
        return None


def get_depth_at_pixel(
    depth: np.ndarray,
    u: float,
    v: float,
    patch_radius: int = 3,
) -> float | None:
    """Read median depth around (u, v), returns mm or None."""
    if depth is None or depth.size == 0:
        return None
    h, w = depth.shape[:2]
    x = int(round(u))
    y = int(round(v))
    r = max(1, int(patch_radius))
    x0 = max(0, x - r)
    x1 = min(w - 1, x + r)
    y0 = max(0, y - r)
    y1 = min(h - 1, y + r)
    patch = depth[y0:y1 + 1, x0:x1 + 1]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def validate_table_height(
    depth_mm: float,
    expected_mm: float,
    tolerance_mm: float = 30.0,
) -> bool:
    """Check whether a depth value is consistent with the table surface."""
    return abs(depth_mm - expected_mm) <= tolerance_mm
