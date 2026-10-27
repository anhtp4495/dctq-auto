"""Basic OpenCV template matching."""

from pathlib import Path

import cv2


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
