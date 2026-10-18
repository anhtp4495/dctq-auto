"""Các module nhiệm vụ tự động hóa game."""

from dctq_auto.tasks.game_options import get_screen_image, recognize_game_options
from dctq_auto.tasks.muu_binh import chon_thuong_phong_thu

__all__ = [
    "get_screen_image",
    "recognize_game_options",
    "chon_thuong_phong_thu",
]
