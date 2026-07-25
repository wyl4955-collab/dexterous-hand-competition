"""Bean detection using HSV color segmentation + contour analysis."""

import cv2
import numpy as np
from typing import List
from .world_state import BeanInfo


class BeanDetector:
    def __init__(self, hsv_lower=(15, 50, 50), hsv_upper=(35, 255, 255)):
        self.hsv_lower = np.array(hsv_lower)
        self.hsv_upper = np.array(hsv_upper)
        self.min_area = 30
        self.max_area = 500
        self.min_circularity = 0.5

    def detect(self, image: np.ndarray) -> List[BeanInfo]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)

        # Morphological cleanup
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        beans = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue
            perimeter = cv2.arcLength(cnt, True)
            if perimeter < 1:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity < self.min_circularity:
                continue

            M = cv2.moments(cnt)
            if M['m00'] < 1:
                continue
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            radius = np.sqrt(area / np.pi)

            # Pixel to world conversion (placeholder — real calibration needed)
            # For now use a simple linear mapping: 1px ≈ 0.3mm at 40cm height
            world_x = cx * 0.3
            world_y = cy * 0.3

            beans.append(BeanInfo(
                pixel_x=cx, pixel_y=cy,
                world_x=world_x, world_y=world_y,
                radius_px=radius, confidence=circularity
            ))

        return beans

    def draw(self, image, beans, selected_idx=None):
        vis = image.copy()
        for i, b in enumerate(beans):
            color = (0, 255, 0) if i == selected_idx else (0, 0, 255)
            cv2.circle(vis, (int(b.pixel_x), int(b.pixel_y)),
                       int(b.radius_px), color, 2)
            cv2.putText(vis, f'#{i}', (int(b.pixel_x) + 10, int(b.pixel_y)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return vis
