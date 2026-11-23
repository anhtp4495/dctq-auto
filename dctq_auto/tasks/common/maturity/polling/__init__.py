"""Các poller theo category của Trưởng Thành."""

from dctq_auto.tasks.common.maturity.polling.lord_poller import LordPoller
from dctq_auto.tasks.common.maturity.polling.treasure_poller import TreasurePoller


_POLLERS = {
    "chua_cong": LordPoller,
    "than_binh": TreasurePoller,
}


def create_poller(category: str, context):
    """Tạo poller theo category; trả về None nếu category chưa được hỗ trợ."""
    poller_class = _POLLERS.get(category)
    if poller_class is None:
        label = context.get("label", category)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] "
            f"[{label}] Chưa có poller, bỏ qua category."
        )
        return None

    try:
        return poller_class()
    except Exception as exc:
        label = context.get("label", category)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] "
            f"[{label}] Không tạo được poller: {exc}; bỏ qua category."
        )
        return None
