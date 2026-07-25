"""Detect tweezer/spoon tip in the camera image."""
import cv2
import numpy as np
from .world_state import ToolInfo


class ToolDetector:
    """Detect tool tip using reflection + geometry heuristics."""

    def __init__(self):
        self.min_aspect_ratio = 3.0
        self.min_area = 100
        self.max_area = 2000
        self.brightness_threshold = 200

    def detect(self, image: np.ndarray):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, self.brightness_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_score = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue
            rect = cv2.minAreaRect(cnt)
            w, h = rect[1]
            if min(w, h) == 0:
                continue
            aspect = max(w, h) / min(w, h)
            if aspect > self.min_aspect_ratio:
                score = area * aspect
                if score > best_score:
                    best_score = score
                    M = cv2.moments(cnt)
                    if M['m00'] > 0:
                        cx = M['m10'] / M['m00']
                        cy = M['m01'] / M['m00']
                        # Tip is the furthest contour point from centroid (downward = larger y)
                        tip = max(cnt, key=lambda p: (p[0][0]-cx)**2 + (p[0][1]-cy)**2
                                  if p[0][1] > cy else 0)
                        best = ToolInfo(
                            pixel_x=tip[0][0], pixel_y=tip[0][1],
                            world_x=tip[0][0]*0.3, world_y=tip[0][1]*0.3, world_z=0
                        )
        return best
