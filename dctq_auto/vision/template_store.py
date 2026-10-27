"""Đọc và cache các template được khai báo trong config/templates.json."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "dctq_auto" / "config" / "templates.json"

_METHODS = {
    "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
    "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
}


@dataclass(frozen=True)
class LoadedTemplate:
    """Template đã được cắt sẵn cùng các tham số so khớp."""

    id: str
    name: str
    display_name: str
    image: np.ndarray
    threshold: float
    method: int


@lru_cache(maxsize=16)
def _load_screen_templates(screen_name: str) -> dict[str, LoadedTemplate]:
    """Đọc config và cắt template một lần cho mỗi màn hình; kết quả được cache."""
    try:
        config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        screen_config = config["screens"][screen_name]
        source_path = _REPO_ROOT / screen_config["source_image"]
        source_image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if source_image is None:
            raise FileNotFoundError(f"Không đọc được source_image: {source_path}")
        definitions = screen_config["templates"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Không tải được cấu hình template màn hình %s từ %s: %s", screen_name, _CONFIG_PATH, exc)
        return {}

    source_height, source_width = source_image.shape[:2]
    loaded: dict[str, LoadedTemplate] = {}

    for name, definition in definitions.items():
        if not isinstance(definition, dict):
            logger.warning("Template %s.%s không có cấu hình dạng object; bỏ qua.", screen_name, name)
            continue

        rect = definition.get("rect")
        if not isinstance(rect, dict):
            logger.warning("Template %s.%s thiếu rect; bỏ qua.", screen_name, name)
            continue

        try:
            top = int(rect["top"])
            left = int(rect["left"])
            right = int(rect["right"])
            bottom = int(rect["bottom"])
            threshold = float(definition.get("threshold", 0.85))
            method_name = definition.get("match_method", "TM_CCOEFF_NORMED")
            method = _METHODS[method_name]
        except (KeyError, TypeError, ValueError):
            logger.warning("rect/threshold/match_method của template %s.%s không hợp lệ; bỏ qua.", screen_name, name)
            continue

        if not 0.0 <= threshold <= 1.0:
            logger.warning("threshold của template %s.%s nằm ngoài [0, 1]; bỏ qua.", screen_name, name)
            continue

        if (
            top < 0 or left < 0 or right > source_width or bottom > source_height
            or right <= left or bottom <= top
        ):
            logger.warning(
                "Rect template %s.%s không hợp lệ: top=%s, left=%s, right=%s, bottom=%s; "
                "ảnh gốc %sx%s. Bỏ qua.",
                screen_name, name, top, left, right, bottom, source_width, source_height,
            )
            continue

        template_image = source_image[top:bottom, left:right].copy()
        if template_image.size == 0:
            logger.warning("Template %s.%s cắt ra ảnh rỗng; bỏ qua.", screen_name, name)
            continue

        template_image.setflags(write=False)
        loaded[name] = LoadedTemplate(
            id=name,
            name=name,
            display_name=str(definition.get("name", name)),
            image=template_image,
            threshold=threshold,
            method=method,
        )

    return loaded


def get_templates(template_names: tuple[str, ...] | list[str]) -> dict[str, LoadedTemplate]:
    """Tải template theo định dạng ``screen_name/template_name``.

    Ví dụ: ``get_templates(("accounts/waiting", "accounts/profile"))``.
    Khóa kết quả giữ nguyên đường dẫn được truyền vào để tránh trùng tên giữa
    các màn hình. Template chưa khai báo hoặc không hợp lệ sẽ bị bỏ qua.
    """
    loaded: dict[str, LoadedTemplate] = {}
    screens: dict[str, dict[str, LoadedTemplate]] = {}

    for template_path in template_names:
        try:
            screen_name, template_name = template_path.split("/", 1)
        except (AttributeError, ValueError):
            logger.warning(
                "Đường dẫn template %r không hợp lệ; dùng định dạng screen_name/template_name.",
                template_path,
            )
            continue

        if not screen_name or not template_name or "/" in template_name:
            logger.warning("Đường dẫn template %r không hợp lệ; bỏ qua.", template_path)
            continue

        if screen_name not in screens:
            screens[screen_name] = _load_screen_templates(screen_name)

        template = screens[screen_name].get(template_name)
        if template is not None:
            loaded[template_path] = template

    return loaded


def clear_template_cache() -> None:
    """Xóa cache nếu templates.json hoặc ảnh nguồn vừa được cập nhật."""
    _load_screen_templates.cache_clear()
