"""Screenshot loading utilities."""

from pathlib import Path

import cv2
import numpy as np


def load_screenshot(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read screenshot: {path}")
    return image
