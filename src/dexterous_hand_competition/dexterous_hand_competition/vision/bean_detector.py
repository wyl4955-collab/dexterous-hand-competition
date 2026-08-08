"""Traditional OpenCV soybean detector for a fixed source-container ROI.

Includes lightweight multi-frame tracking so that ``target_id`` is stable
across frames and ``failure_count`` can be maintained by the task layer.
"""

from dataclasses import dataclass
import math
import time

import cv2
import numpy as np

from .table_calibration import TableCalibration


@dataclass(frozen=True)
class Detection:
    target_id: int
    u: float
    v: float
    x_m: float
    y_m: float
    confidence: float
    edge_distance_px: float
    nearest_neighbor_px: float


# ---------------------------------------------------------------------------
# Lightweight bipartite matching (greedy nearest-neighbour).
# Sufficient for the ~5-30 beans expected on the table.
# ---------------------------------------------------------------------------

def _match_detections(
    current: list[dict],
    previous: list[dict],
    max_distance_m: float = 0.03,
) -> list[int]:
    """Greedy assignment of current→previous based on table-coordinate distance.

    Returns a list the same length as *current*.  Entry *i* is the index in
    *previous* that was matched, or -1 for a new bean.
    """
    used = [False] * len(previous)
    assignments = [-1] * len(current)

    # Build all pairs sorted by distance.
    pairs = []
    for ci, cur in enumerate(current):
        for pi, prev in enumerate(previous):
            dx = cur['x_m'] - prev['x_m']
            dy = cur['y_m'] - prev['y_m']
            d = math.hypot(dx, dy)
            if d <= max_distance_m:
                pairs.append((d, ci, pi))

    pairs.sort(key=lambda p: p[0])
    for _, ci, pi in pairs:
        if assignments[ci] == -1 and not used[pi]:
            assignments[ci] = pi
            used[pi] = True

    return assignments


# ---------------------------------------------------------------------------
# BeanDetector
# ---------------------------------------------------------------------------

class BeanDetector:
    def __init__(self, config: dict, calibration: TableCalibration):
        self.config = config
        self.calibration = calibration

        # Tracking state
        self._prev_detections: list[dict] = []
        self._prev_stamp = 0.0
        self._next_id = 1
        self._failure_counts: dict[int, int] = {}
        self._max_track_age_sec = 2.0

    # -- ROI ----------------------------------------------------------------
    def _roi(self, image: np.ndarray):
        roi = self.config['source_roi']
        x = int(roi['x'])
        y = int(roi['y'])
        width = int(roi['width'])
        height = int(roi['height'])
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError('source ROI is invalid')
        if x + width > image.shape[1] or y + height > image.shape[0]:
            raise ValueError('source ROI is outside the image')
        return image[y:y + height, x:x + width], x, y

    # -- detection ----------------------------------------------------------
    def detect(
        self,
        image_bgr: np.ndarray,
        stamp_sec: float | None = None,
    ) -> tuple[list[Detection], np.ndarray]:
        """Run detection + tracking on one frame.

        Args:
            image_bgr: colour image.
            stamp_sec: monotonic timestamp for tracking age-out.
                Defaults to ``time.monotonic()``.

        Returns:
            (detections, debug_image)
        """
        if stamp_sec is None:
            stamp_sec = time.monotonic()

        debug = image_bgr.copy()
        roi_image, offset_x, offset_y = self._roi(image_bgr)
        hsv = cv2.cvtColor(roi_image, cv2.COLOR_BGR2HSV)

        lower = np.array(self.config['hsv_lower'], dtype=np.uint8)
        upper = np.array(self.config['hsv_upper'], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        kernel_size = int(self.config.get('morph_kernel', 3))
        kernel_size = max(1, kernel_size | 1)
        kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        min_area = float(self.config['min_area_px'])
        max_area = float(self.config['max_area_px'])
        min_circularity = float(self.config['min_circularity'])
        edge_margin = float(self.config['edge_margin_px'])

        candidates = []
        roi_height, roi_width = mask.shape
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0.0:
                continue
            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
            if circularity < min_circularity:
                continue

            moments = cv2.moments(contour)
            if moments['m00'] == 0.0:
                continue
            local_u = moments['m10'] / moments['m00']
            local_v = moments['m01'] / moments['m00']
            edge_distance = min(
                local_u,
                local_v,
                roi_width - local_u,
                roi_height - local_v,
            )
            if edge_distance < edge_margin:
                continue

            u = local_u + offset_x
            v = local_v + offset_y
            table = self.calibration.pixel_to_table(u, v)
            if table is None:
                continue
            confidence = min(1.0, max(0.0, circularity))
            candidates.append(
                {
                    'u': u,
                    'v': v,
                    'x_m': float(table[0]),
                    'y_m': float(table[1]),
                    'confidence': confidence,
                    'edge_distance_px': edge_distance,
                }
            )

        # -- multi-frame association ----------------------------------------
        # Age out old tracks.
        if stamp_sec - self._prev_stamp > self._max_track_age_sec:
            self._prev_detections.clear()
            self._next_id = 1

        assignments = _match_detections(candidates, self._prev_detections)

        detections: list[Detection] = []
        for ci, candidate in enumerate(candidates):
            pi = assignments[ci]
            if pi >= 0:
                tid = self._prev_detections[pi]['id']
            else:
                tid = self._next_id
                self._next_id += 1

            nearest = 9999.0
            for cj, other in enumerate(candidates):
                if cj == ci:
                    continue
                d = math.hypot(
                    candidate['u'] - other['u'],
                    candidate['v'] - other['v'],
                )
                if d < nearest:
                    nearest = d

            detections.append(
                Detection(
                    target_id=tid,
                    u=candidate['u'],
                    v=candidate['v'],
                    x_m=candidate['x_m'],
                    y_m=candidate['y_m'],
                    confidence=candidate['confidence'],
                    edge_distance_px=candidate['edge_distance_px'],
                    nearest_neighbor_px=nearest,
                )
            )

            cv2.circle(debug, (int(candidate['u']), int(candidate['v'])), 8, (0, 255, 0), 2)
            cv2.putText(
                debug,
                str(tid),
                (int(candidate['u']) + 8, int(candidate['v']) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        roi = self.config['source_roi']
        cv2.rectangle(
            debug,
            (int(roi['x']), int(roi['y'])),
            (int(roi['x'] + roi['width']), int(roi['y'] + roi['height'])),
            (255, 0, 0),
            2,
        )

        # Store for next frame.
        self._prev_detections = [
            {
                'id': d.target_id,
                'x_m': d.x_m,
                'y_m': d.y_m,
            }
            for d in detections
        ]
        self._prev_stamp = stamp_sec

        return detections, debug

    # -- failure tracking ---------------------------------------------------
    def record_failure(self, target_id: int):
        """Called by the task layer when a pick attempt fails."""
        self._failure_counts[target_id] = (
            self._failure_counts.get(target_id, 0) + 1
        )

    def record_success(self, target_id: int):
        """Called when a pick succeeds — resets the counter for that ID."""
        self._failure_counts.pop(target_id, None)

    def reset_tracking(self):
        """Forget all tracked IDs (e.g. when the task resets)."""
        self._prev_detections.clear()
        self._next_id = 1
        self._failure_counts.clear()
        self._prev_stamp = 0.0

    def get_failure_map(self) -> dict[int, int]:
        """Return a copy of {target_id: failure_count}."""
        return dict(self._failure_counts)
