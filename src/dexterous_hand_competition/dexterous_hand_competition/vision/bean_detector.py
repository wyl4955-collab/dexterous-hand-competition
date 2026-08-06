"""Traditional OpenCV soybean detector for a fixed source-container ROI."""

from dataclasses import dataclass
import math

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


class BeanDetector:
    def __init__(self, config: dict, calibration: TableCalibration):
        self.config = config
        self.calibration = calibration

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

    def detect(self, image_bgr: np.ndarray) -> tuple[list[Detection], np.ndarray]:
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
            candidates.append((u, v, table[0], table[1], confidence, edge_distance))

        detections = []
        for index, candidate in enumerate(candidates):
            u, v, x_m, y_m, confidence, edge_distance = candidate
            distances = [
                math.hypot(u - other[0], v - other[1])
                for other_index, other in enumerate(candidates)
                if other_index != index
            ]
            nearest = min(distances) if distances else 9999.0
            detections.append(
                Detection(
                    target_id=index + 1,
                    u=u,
                    v=v,
                    x_m=x_m,
                    y_m=y_m,
                    confidence=confidence,
                    edge_distance_px=edge_distance,
                    nearest_neighbor_px=nearest,
                )
            )
            cv2.circle(debug, (int(u), int(v)), 8, (0, 255, 0), 2)
            cv2.putText(
                debug,
                str(index + 1),
                (int(u) + 8, int(v) - 8),
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
        return detections, debug

