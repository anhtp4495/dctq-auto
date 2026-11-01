"""Điều phối các tác vụ thuộc màn hình [Cửa hàng]."""

from dctq_auto.config.constants import _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
from dctq_auto.tasks.common.shop import task_close_shop, task_open_shop
from dctq_auto.tasks.common.shop.war import task_war


_SHOP_STEP_IDS = {
    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở shop, chạy các tác vụ đã chọn, sau đó đóng giao diện shop."""
    if not _SHOP_STEP_IDS.intersection(steps):
        return steps

    shop_opened = False
    try:
        if not task_open_shop.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được [Cửa hàng]; giữ nguyên step.")
            return steps
        shop_opened = True

        if _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH in steps:
            steps = task_war.run(
                worker, account, steps, device, ocr_client, log
            )
        return steps
    finally:
        if shop_opened:
            try:
                closed = task_close_shop.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được [Cửa hàng].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi đóng [Cửa hàng]: {exc}")
