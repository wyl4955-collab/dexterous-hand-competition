"""Calibrated table-coordinate to joint-target mapping."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspacePoint:
    x_m: float
    y_m: float
    layers: dict[str, dict[int, float]]


class WorkspaceMapper:
    """Bilinear interpolation over a rectangular calibrated grid."""

    def __init__(
        self,
        x_values: list[float],
        y_values: list[float],
        points: dict[tuple[int, int], WorkspacePoint],
        calibrated: bool = False,
    ):
        self.x_values = sorted(float(value) for value in x_values)
        self.y_values = sorted(float(value) for value in y_values)
        self.points = points
        self.calibrated = bool(calibrated)

    def contains(self, x_m: float, y_m: float) -> bool:
        return (
            self.calibrated
            and len(self.x_values) >= 2
            and len(self.y_values) >= 2
            and self.x_values[0] <= x_m <= self.x_values[-1]
            and self.y_values[0] <= y_m <= self.y_values[-1]
        )

    @staticmethod
    def _bracket(values: list[float], value: float) -> tuple[int, int]:
        for index in range(len(values) - 1):
            if values[index] <= value <= values[index + 1]:
                return index, index + 1
        raise ValueError('value is outside calibrated grid')

    def map_table_to_joints(
        self,
        x_m: float,
        y_m: float,
        layer: str,
    ) -> dict[int, float] | None:
        if not self.contains(x_m, y_m):
            return None

        xi0, xi1 = self._bracket(self.x_values, x_m)
        yi0, yi1 = self._bracket(self.y_values, y_m)
        x0, x1 = self.x_values[xi0], self.x_values[xi1]
        y0, y1 = self.y_values[yi0], self.y_values[yi1]

        corners = [
            self.points.get((xi0, yi0)),
            self.points.get((xi1, yi0)),
            self.points.get((xi0, yi1)),
            self.points.get((xi1, yi1)),
        ]
        if any(point is None or layer not in point.layers for point in corners):
            return None

        tx = 0.0 if x1 == x0 else (x_m - x0) / (x1 - x0)
        ty = 0.0 if y1 == y0 else (y_m - y0) / (y1 - y0)
        weights = [
            (1.0 - tx) * (1.0 - ty),
            tx * (1.0 - ty),
            (1.0 - tx) * ty,
            tx * ty,
        ]

        joint_ids = set(corners[0].layers[layer])
        if any(set(point.layers[layer]) != joint_ids for point in corners[1:]):
            return None

        return {
            joint_id: sum(
                weight * point.layers[layer][joint_id]
                for point, weight in zip(corners, weights)
            )
            for joint_id in joint_ids
        }

