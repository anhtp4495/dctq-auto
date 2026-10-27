"""Fast pixel-based comparison for a cropped screenshot region."""

from pathlib import Path

import cv2
import numpy as np


def compare_image_rect(
    template_path: str | Path,
    rect_image: np.ndarray,
    tolerance: float = 0.5,
    pixel_threshold: int = 10,
) -> bool:
    """Compare a cropped screenshot region with a saved PNG template."""
    if not 0 <= tolerance <= 100:
        raise ValueError("tolerance must be between 0 and 100")
    if not 0 <= pixel_threshold <= 255:
        raise ValueError("pixel_threshold must be between 0 and 255")
    if not isinstance(rect_image, np.ndarray) or rect_image.size == 0:
        return False

    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if template is None:
        return False

    if rect_image.ndim == 2:
        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    elif rect_image.ndim != 3 or rect_image.shape[2] != 3:
        return False

    if template.shape != rect_image.shape or rect_image.dtype != np.uint8:
        return False

    diff = cv2.absdiff(template, rect_image)
    if diff.ndim == 3:
        different_pixels = np.any(diff > pixel_threshold, axis=2)
    else:
        different_pixels = diff > pixel_threshold

    difference_percent = float(np.count_nonzero(different_pixels)) / different_pixels.size * 100.0
    return difference_percent <= tolerance
