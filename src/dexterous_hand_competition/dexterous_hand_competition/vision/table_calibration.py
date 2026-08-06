"""Pixel-to-table homography helper."""

import numpy as np


class TableCalibration:
    def __init__(self, homography: list[list[float]], calibrated: bool):
        matrix = np.asarray(homography, dtype=np.float64)
        if matrix.shape != (3, 3):
            raise ValueError('homography must be a 3x3 matrix')
        self.matrix = matrix
        self.calibrated = bool(calibrated)

    def pixel_to_table(self, u: float, v: float) -> tuple[float, float] | None:
        if not self.calibrated:
            return None
        result = self.matrix @ np.array([u, v, 1.0], dtype=np.float64)
        if abs(result[2]) < 1e-9:
            return None
        return float(result[0] / result[2]), float(result[1] / result[2])

