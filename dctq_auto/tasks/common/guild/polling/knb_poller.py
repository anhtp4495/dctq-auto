"""Poller nhận diện trạng thái quy trình đóng góp KNB trong Quân đoàn."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)

from .base_poller import BaseGuildPoller


# Ưu tiên điều kiện kết thúc và mức KNB cao trước; nút vào đặt sau các mức.
_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
)
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)


class KnbPoller(BaseGuildPoller):
    """Chỉ nhận diện trạng thái và trả observation; task_guild thực hiện thao tác."""

    step_id = _STEP_QUAN_DOAN_DONG_GOP_KNB
    category_key = "dong_gop_knb"

    state_by_template = {
        _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB: "entry",
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_GOP_KNB: "close_donation_screen",
        _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB: "insufficient_conditions",
        _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB: "donate_10",
        _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB: "donate_20",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        """Nhận diện một trạng thái KNB theo danh sách template của phase."""
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "entry",
            "donate_10",
            "donate_20",
            "close_donation_screen",
        }
        observation["completed"] = observation["state"] in {
            "insufficient_conditions",
            "guild_main",
        }
        return observation
