"""Template matching utilities based on OpenCV cv2.matchTemplate."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np


class TemplateMatch(NamedTuple):
    """A match rectangle in (top, left, right, bottom) order, plus similarity."""

    top: int
    left: int
    right: int
    bottom: int
    score: float

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.top, self.left, self.right, self.bottom


def _load_image(value: str | Path | np.ndarray, label: str) -> np.ndarray:
    if isinstance(value, np.ndarray):
        image = value
    else:
        path = Path(value)
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Cannot read {label} image: {path}")
    if image.size == 0 or image.ndim not in (2, 3):
        raise ValueError(f"{label} image is empty or has an unsupported shape")
    return image


def match_template(
    image: str | Path | np.ndarray,
    template: str | Path | np.ndarray,
    *,
    search_rect: tuple[int, int, int, int] | None = None,
    threshold: float = 0.8,
    method: int = cv2.TM_CCOEFF_NORMED,
    grayscale: bool = True,
) -> TemplateMatch | None:
    """Find a template in an image using cv2.matchTemplate.

    Args:
        image: Source image path or OpenCV/numpy image.
        template: Smaller template image path or OpenCV/numpy image.
        search_rect: Optional (top, left, right, bottom) search region in the
            source image. Right and bottom are exclusive, matching normal
            Python/OpenCV crop conventions. If omitted, search the full image.
        threshold: Minimum similarity from 0 to 1. For TM_SQDIFF_NORMED,
            similarity is computed as 1 - normalized minimum difference.
        method: OpenCV matchTemplate method. Prefer normalized methods.
        grayscale: Convert both images to grayscale before matching.

    Returns:
        TemplateMatch with a RECT in original-image coordinates, or None when
        the best match does not meet threshold.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    source = _load_image(image, "source")
    needle = _load_image(template, "template")

    if grayscale:
        if source.ndim == 3:
            source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        if needle.ndim == 3:
            needle = cv2.cvtColor(needle, cv2.COLOR_BGR2GRAY)
    elif source.ndim != needle.ndim or (
        source.ndim == 3 and source.shape[2] != needle.shape[2]
    ):
        raise ValueError("Source and template must have matching channel layouts")

    image_height, image_width = source.shape[:2]
    template_height, template_width = needle.shape[:2]

    if search_rect is None:
        top, left, right, bottom = 0, 0, image_width, image_height
    else:
        if len(search_rect) != 4:
            raise ValueError("search_rect must be (top, left, right, bottom)")
        top, left, right, bottom = map(int, search_rect)
        if top < 0 or left < 0 or right > image_width or bottom > image_height:
            raise ValueError("search_rect is outside the source image")
        if right <= left or bottom <= top:
            raise ValueError("search_rect must have positive width and height")

    region = source[top:bottom, left:right]
    region_height, region_width = region.shape[:2]
    if template_width > region_width or template_height > region_height:
        raise ValueError("Template must fit entirely inside the search region")

    result = cv2.matchTemplate(region, needle, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
        match_x, match_y = min_loc
        if method == cv2.TM_SQDIFF_NORMED:
            score = max(0.0, min(1.0, 1.0 - float(min_val)))
            accepted = score >= threshold
        else:
            # Unnormalized SQDIFF is an error metric, not a 0..1 similarity.
            score = float(min_val)
            accepted = True
    else:
        match_x, match_y = max_loc
        score = float(max_val)
        accepted = score >= threshold

    if not accepted:
        return None

    match_top = top + int(match_y)
    match_left = left + int(match_x)
    return TemplateMatch(
        top=match_top,
        left=match_left,
        right=match_left + int(template_width),
        bottom=match_top + int(template_height),
        score=score,
    )
