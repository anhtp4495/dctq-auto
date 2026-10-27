"Basic OpenCV image matching utilities."

from pathlib import Path

import cv2
import numpy as np


def find_template(screen_path: Path, template_path: Path, threshold: float = 0.90) -> tuple[int, int] | None:
    screen = cv2.imread(str(screen_path), cv2.IMREAD_COLOR)
    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if screen is None:
        raise FileNotFoundError(f"Could not read screenshot: {screen_path}")
    if template is None:
        raise FileNotFoundError(f"Could not read template: {template_path}")
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        raise ValueError("Template dimensions must not exceed screenshot dimensions")
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    if score < threshold:
        return None
    height, width = template.shape[:2]
    return (location[0] + width // 2, location[1] + height // 2)


def compare_image_rect(
    template_path: str | Path,
    rect_image: np.ndarray,
    tolerance: float = 0.5,
    pixel_threshold: int = 10,
) -> bool:
    """Compare a cropped screenshot region with a saved PNG template.

    Args:
        template_path: Path to the template image (PNG recommended).
        rect_image: Already-cropped screenshot region as a NumPy array (BGR or grayscale).
        tolerance: Maximum percentage of pixels allowed to differ (0..100).
        pixel_threshold: Per-channel absolute difference ignored for each pixel (0..255).

    Returns:
        True when the percentage of differing pixels is within tolerance;
        False when images do not match or an input image cannot be read.

    Notes:
        Images must have the same dimensions. The function does not resize either image.
    """
    if not 0 <= tolerance <= 100:
        raise ValueError("tolerance must be between 0 and 100")
    if not 0 <= pixel_threshold <= 255:
        raise ValueError("pixel_threshold must be between 0 and 255")
    if not isinstance(rect_image, np.ndarray) or rect_image.size == 0:
        return False

    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if template is None:
        return False

    # Compare grayscale input in grayscale; otherwise compare all BGR channels.
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
