"""Tương thích ngược cho API nhận diện lựa chọn game cũ.

Logic chính hiện nằm trong dctq_auto.tasks.muu_binh.chon_thuong_phong_thu.
"""
from dctq_auto.tasks.muu_binh.chon_thuong_phong_thu import (
    chon_thuong_phong_thu,
    get_screen_image,
)

recognize_game_options = chon_thuong_phong_thu

__all__ = ["get_screen_image", "recognize_game_options", "chon_thuong_phong_thu"]
