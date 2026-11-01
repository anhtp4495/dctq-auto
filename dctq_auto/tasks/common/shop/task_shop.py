"""Điều phối các tác vụ thuộc màn hình [Cửa hàng]."""

from dctq_auto.config.constants import _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
from dctq_auto.tasks.common.shop import task_close_shop, task_open_shop
from dctq_auto.tasks.common.shop.war import task_buy_fortune_lot, task_open_shop_war


_SHOP_STEP_IDS = {
    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở shop, chạy các tác vụ đã chọn, sau đó đóng giao diện shop."""
    if not _SHOP_STEP_IDS.intersection(steps):
        return steps

    shop_open_attempted = False
    try:
        shop_open_attempted = True
        if not task_open_shop.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được [Cửa hàng]; giữ nguyên step.")
            return steps

        if _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH in steps:
            if task_open_shop_war.run(
                worker, account, steps, device, ocr_client, log
            ):
                steps = task_buy_fortune_lot.run(
                    worker, account, steps, device, ocr_client, log
                )
            else:
                log(f"[{account.username}] Không mở được [Shop Chiến Tranh]; giữ lại step mua Quẻ lành.")
        return steps
    finally:
        if shop_open_attempted:
            try:
                closed = task_close_shop.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được [Cửa hàng].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi đóng [Cửa hàng]: {exc}")
