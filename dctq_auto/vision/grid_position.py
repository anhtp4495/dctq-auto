"""Map a template-match rectangle to a row-major stage number."""

from __future__ import annotations

from math import floor
from typing import Mapping, Sequence


def stage_number_from_match(
    match_rect: Mapping[str, int] | Sequence[int],
    *,
    grid_origin: tuple[int, int],
    cell_width: int,
    cell_height: int,
    columns: int = 10,
    total_stages: int = 100,
) -> int | None:
    """Return the 1-based stage number containing the match rectangle center.

    Coordinates use (top, left, right, bottom) order. For a sequence, the
    order is identical. grid_origin is (top, left) in screenshot coordinates.
    The right and bottom edges of rectangles are exclusive.

    Returns None when the match center falls outside the configured grid.
    """
    if isinstance(match_rect, Mapping):
        top = int(match_rect["top"])
        left = int(match_rect["left"])
        right = int(match_rect["right"])
        bottom = int(match_rect["bottom"])
    else:
        if len(match_rect) != 4:
            raise ValueError("match_rect must contain top, left, right, bottom")
        top, left, right, bottom = map(int, match_rect)

    if right <= left or bottom <= top:
        raise ValueError("match_rect must have positive width and height")
    if cell_width <= 0 or cell_height <= 0:
        raise ValueError("cell_width and cell_height must be positive")
    if columns <= 0 or total_stages <= 0:
        raise ValueError("columns and total_stages must be positive")

    origin_top, origin_left = map(int, grid_origin)

    # Use the center so small matching offsets do not change the selected cell.
    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0

    col = floor((center_x - origin_left) / cell_width)
    row = floor((center_y - origin_top) / cell_height)

    if row < 0 or col < 0 or col >= columns:
        return None

    stage_number = row * columns + col + 1
    if stage_number > total_stages:
        return None
    return stage_number
