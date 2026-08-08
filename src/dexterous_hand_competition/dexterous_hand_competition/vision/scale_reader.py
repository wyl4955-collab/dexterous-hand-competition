"""Seven-segment LCD digit recognition for the electronic scale.

The scale has a white background with black digits.  We extract the configured
ROI, binarise, segment each digit cell, and classify using seven-segment
structure (which segments are lit).

This is more robust than template matching under changing lighting because
the geometric structure of a seven-segment display is invariant.
"""

from dataclasses import dataclass
from collections import deque

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Seven-segment pattern → digit lookup.
# Segments are labelled:
#
#      a
#    f   b
#      g
#    e   c
#      d
#
# We sample 7 regions inside a normalised 20x30 cell.  Each region is scored
# as lit (1) if >50% of its pixels are white after thresholding.
# ---------------------------------------------------------------------------

SEGMENT_PATTERNS: dict[tuple, str] = {
    (1, 1, 1, 0, 1, 1, 1): '0',
    (0, 1, 1, 0, 0, 0, 0): '1',
    (1, 1, 0, 1, 1, 0, 1): '2',
    (1, 1, 1, 1, 0, 0, 1): '3',
    (0, 1, 1, 0, 0, 1, 1): '4',
    (1, 0, 1, 1, 0, 1, 1): '5',
    (1, 0, 1, 1, 1, 1, 1): '6',
    (1, 1, 1, 0, 0, 0, 0): '7',
    (1, 1, 1, 1, 1, 1, 1): '8',
    (1, 1, 1, 1, 0, 1, 1): '9',
}

# Each tuple is (cx_ratio, cy_ratio, w_ratio, h_ratio) in the cell.
SEGMENT_ROIS = {
    'a': (0.50, 0.08, 0.20, 0.12),
    'b': (0.78, 0.15, 0.10, 0.30),
    'c': (0.78, 0.55, 0.10, 0.30),
    'd': (0.50, 0.80, 0.20, 0.12),
    'e': (0.12, 0.55, 0.10, 0.30),
    'f': (0.12, 0.15, 0.10, 0.30),
    'g': (0.50, 0.46, 0.20, 0.10),
}


@dataclass(frozen=True)
class ScaleResult:
    value_grams: float
    confidence: float
    raw_digits: str


class ScaleReader:
    """Read the value displayed on a seven-segment LCD electronic scale."""

    def __init__(self, config: dict):
        roi = config.get('roi', {})
        self.roi = {
            'x': int(roi.get('x', 0)),
            'y': int(roi.get('y', 0)),
            'width': int(roi.get('width', 120)),
            'height': int(roi.get('height', 60)),
        }
        self.binary_threshold = int(config.get('binary_threshold', 0))
        self.min_digit_area = float(config.get('min_digit_area_px', 50))
        self.max_digit_area = float(config.get('max_digit_area_px', 800))
        self.min_segment_fill = float(config.get('min_segment_fill', 0.25))

        # Frame-to-frame stabilisation: require N consecutive equal readings.
        self._history: deque[float | None] = deque(maxlen=int(config.get('stable_frames', 3)))
        self._last_stable: ScaleResult | None = None

    # ------------------------------------------------------------------
    def read(self, image_bgr: np.ndarray) -> ScaleResult | None:
        """Extract the current scale reading. Returns None when unreadable."""
        h, w = image_bgr.shape[:2]
        rx, ry, rw, rh = self.roi['x'], self.roi['y'], self.roi['width'], self.roi['height']
        if rx < 0 or ry < 0 or rw <= 0 or rh <= 0:
            return None
        if rx + rw > w or ry + rh > h:
            return None

        roi = image_bgr[ry:ry + rh, rx:rx + rw]
        return self._process_roi(roi)

    def _process_roi(self, roi: np.ndarray) -> ScaleResult | None:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Black digits on white background → THRESH_BINARY_INV so digits are white.
        if self.binary_threshold > 0:
            _, binary = cv2.threshold(
                gray, self.binary_threshold, 255, cv2.THRESH_BINARY_INV,
            )
        else:
            # Otsu auto-threshold.
            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
            )

        # Find connected components that could be digit segments.
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        # Group contours into digit cells by horizontal position.
        cells = self._group_into_cells(contours, binary.shape)
        if not cells:
            return None

        digits_str = ''
        confidences = []
        for cell_rect, _ in cells:
            digit, conf = self._classify_cell(binary, cell_rect)
            if digit is not None:
                digits_str += digit
                confidences.append(conf)
            elif digits_str:
                digits_str += '?'

        if not digits_str:
            return None

        conf = float(np.mean(confidences)) if confidences else 0.0
        try:
            value = float(digits_str)
        except ValueError:
            value = 0.0

        result = ScaleResult(value_grams=value, confidence=conf, raw_digits=digits_str)
        return self._stabilise(result)

    # ------------------------------------------------------------------
    def _group_into_cells(
        self, contours: list, shape: tuple[int, int],
    ) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
        """Merge nearby contours into digit-cell candidates sorted left→right."""
        if not contours:
            return []

        h, w = shape
        # Build bounding boxes, filter by area.
        boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_digit_area or area > self.max_digit_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw <= 0 or bh <= 0:
                continue
            # Keep digits that are roughly the right aspect ratio.
            aspect = bh / float(bw) if bw > 0 else 0
            if aspect < 1.0 or aspect > 4.0:
                continue
            boxes.append((x, y, bw, bh))

        if not boxes:
            return []

        boxes.sort(key=lambda b: b[0])  # left→right

        # Merge overlapping boxes.
        merged = [list(boxes[0])]
        for bx in boxes[1:]:
            mx, my, mw, mh = merged[-1]
            overlap_x = max(0, min(mx + mw, bx[0] + bx[2]) - max(mx, bx[0]))
            if overlap_x > 0:
                # Merge
                nx = min(mx, bx[0])
                ny = min(my, bx[1])
                nw = max(mx + mw, bx[0] + bx[2]) - nx
                nh = max(my + mh, bx[1] + bx[3]) - ny
                merged[-1] = [nx, ny, nw, nh]
            else:
                merged.append(list(bx))

        cells = []
        for mx, my, mw, mh in merged:
            # Pad slightly.
            px0 = max(0, mx - 2)
            py0 = max(0, my - 2)
            px1 = min(w, mx + mw + 2)
            py1 = min(h, my + mh + 2)
            cells.append(((px0, py0, px1 - px0, py1 - py0), None))
        return cells

    # ------------------------------------------------------------------
    def _classify_cell(
        self, roi: np.ndarray, cell_rect: tuple[int, int, int, int],
    ) -> tuple[str | None, float]:
        """Classify one digit cell using seven-segment analysis."""
        x, y, cw, ch = cell_rect
        ch_img, cw_img = roi.shape[:2]

        segments = {}
        for seg_name, (cx_frac, cy_frac, wr, hr) in SEGMENT_ROIS.items():
            sx = int(cx_frac * cw + x)
            sy = int(cy_frac * ch + y)
            sw = max(1, int(wr * cw))
            sh = max(1, int(hr * ch))
            sx = max(0, min(cw_img - 1, sx))
            sy = max(0, min(ch_img - 1, sy))
            if sx + sw > cw_img:
                sw = cw_img - sx
            if sy + sh > ch_img:
                sh = ch_img - sy
            if sw <= 0 or sh <= 0:
                segments[seg_name] = 0
                continue
            patch = roi[sy:sy + sh, sx:sx + sw]
            nonzero = float(np.count_nonzero(patch))
            total = patch.size
            segments[seg_name] = 1 if nonzero / total >= self.min_segment_fill else 0

        pattern = tuple(int(segments.get(k, 0)) for k in ('a', 'b', 'c', 'd', 'e', 'f', 'g'))
        digit = SEGMENT_PATTERNS.get(pattern)
        conf = 1.0 if digit is not None else 0.0
        return digit, conf

    # ------------------------------------------------------------------
    def _stabilise(self, result: ScaleResult) -> ScaleResult | None:
        """Frame-to-frame debounce: require N equal consecutive values."""
        self._history.append(result.value_grams)
        # Check if last N are equal.
        values = list(self._history)
        if len(values) < self._history.maxlen:
            return None

        target = values[-1]
        if all(abs(v - target) < 0.01 for v in values[-self._history.maxlen:]):
            stable = ScaleResult(
                value_grams=target, confidence=result.confidence,
                raw_digits=result.raw_digits,
            )
            self._last_stable = stable
            return stable

        return self._last_stable

    def reset_stabiliser(self):
        self._history.clear()
        self._last_stable = None
