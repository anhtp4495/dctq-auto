"""Poller nhận diện trạng thái 30 ô Điểm danh; không thực hiện thao tác trên thiết bị."""

import cv2

from dctq_auto.config.constants import (
    _TEMPLATE_DA_DIEM_DANH,
    _TEMPLATE_DIEM_DANH_BU,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


class DailyCheckInPoller:
    """Quét 30 ô và xác định ngày thường/ngày có thể điểm danh bù."""

    ROW_BOUNDS = (
        (405, 537),
        (554, 689),
        (704, 841),
        (853, 992),
    )
    ROW_LENGTHS = (9, 9, 9, 3)

    @classmethod
    def build_day_regions(cls, screen_width: int, screen_height: int):
        """Tạo vùng tìm kiếm 30 ô theo lưới 9 + 9 + 9 + 3."""
        scale_x = screen_width / 1920
        scale_y = screen_height / 1080
        day_regions = []
        day = 1

        for row_index, (top, bottom) in enumerate(cls.ROW_BOUNDS):
            for column in range(cls.ROW_LENGTHS[row_index]):
                left = round((480 + column * 150) * scale_x)
                right = round((620 + column * 150) * scale_x)
                region = (
                    round(top * scale_y),
                    left,
                    right,
                    round(bottom * scale_y),
                )
                day_regions.append((day, region))
                day += 1

        return day_regions

    def __init__(self):
        # Giữ danh sách ô đã chọn để các lần poll sau chỉ kiểm tra lại các ô này.
        self._target_cells = None

    @staticmethod
    def _match_day(screen_bgr, template, search_rect):
        return match_template(
            screen_bgr,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=search_rect,
            grayscale=template.grayscale,
        )

    def poll(
        self,
        screen_bgr,
        screen_width: int,
        screen_height: int,
        templates,
        account,
        log,
    ) -> dict | None:
        """Trả đúng một state: xác nhận, một ô cần điểm danh hoặc hoàn tất.

        Lần đầu quét 30 ô để lưu danh sách mục tiêu. Những lần sau chỉ kiểm tra
        các ô đã lưu. Mọi ô chưa nhận diện là đã điểm danh vẫn được xem là còn thiếu.
        """
        already_template = templates.get(_TEMPLATE_DA_DIEM_DANH)
        catchup_template = templates.get(_TEMPLATE_DIEM_DANH_BU)
        if already_template is None or catchup_template is None:
            log(f"[{account.display_name}] Thiếu template trạng thái ngày điểm danh.")
            return None

        # Hộp thoại xác nhận điểm danh bù được ưu tiên nhận diện trước
        # khi quét lại các ô ngày.
        confirmation_template = templates.get(_TEMPLATE_XAC_NHAN_DIEM_DANH_BU)
        if confirmation_template is None:
            log(f"[{account.display_name}] Thiếu template xác nhận điểm danh bù.")
            return None
        try:
            confirmation_match = match_template(
                screen_bgr,
                confirmation_template.image,
                threshold=confirmation_template.threshold,
                method=confirmation_template.method,
                search_rect=confirmation_template.search_rect,
                grayscale=confirmation_template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(
                f"[{account.display_name}] Lỗi nhận diện xác nhận điểm danh bù: {exc}"
            )
            return None

        if confirmation_match is not None:
            report_template_match(
                log,
                context=f"[{account.display_name}] Xác nhận điểm danh bù",
                template=confirmation_template,
                match=confirmation_match,
            )
            return {
                "state": "confirmation_required",
                "template_name": _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
                "template": confirmation_template,
                "match": confirmation_match,
            }

        all_day_regions = self.build_day_regions(screen_width, screen_height)
        is_initial_poll = self._target_cells is None

        if is_initial_poll:
            days = []
            already_days = set()
            log(
                f"[{account.display_name}] Bắt đầu quét trạng thái "
                f"{len(all_day_regions)} ngày."
            )
            for day, search_rect in all_day_regions:
                try:
                    already_match = self._match_day(
                        screen_bgr, already_template, search_rect
                    )
                    if already_match is not None:
                        already_days.add(day)
                        state = "completed"
                        log(f"[{account.display_name}] Ngày {day} đã điểm danh.")
                    else:
                        catchup_match = self._match_day(
                            screen_bgr, catchup_template, search_rect
                        )
                        state = (
                            "catchup_available"
                            if catchup_match is not None
                            else "not_completed"
                        )
                        if catchup_match is not None:
                            report_template_match(
                                log,
                                context=f"[{account.display_name}] Ngày {day}",
                                template=catchup_template,
                                match=catchup_match,
                            )
                        log(f"[{account.display_name}] Ngày {day} chưa điểm danh.")
                except (ValueError, cv2.error) as exc:
                    log(
                        f"[{account.display_name}] Lỗi nhận diện trạng thái "
                        f"ngày {day}: {exc}"
                    )
                    return None
                except Exception as exc:
                    log(
                        f"[{account.display_name}] Không kiểm tra được "
                        f"ngày {day}: {exc}"
                    )
                    return None

                days.append({
                    "day": day,
                    "state": state,
                    "search_rect": search_rect,
                })

            target_day = max(already_days, default=0) + 1
            catchup_days = [
                item["day"]
                for item in days
                if item["day"] < target_day and item["state"] != "completed"
            ][:3]
            selected_days = [target_day, target_day + 1, *catchup_days]
            region_by_day = dict(all_day_regions)
            self._target_cells = [
                {"day": day, "search_rect": region_by_day[day]}
                for day in selected_days
                if day in region_by_day
            ]
            log(
                f"[{account.display_name}] Đã lưu thứ tự các ô cần xử lý: "
                f"{[item['day'] for item in self._target_cells]}."
            )
            # Lần quét đầu đã có trạng thái từng ô, không cần quét lại.
            pending_days = {
                item["day"] for item in days
                if item["state"] != "completed"
            }
            for item in self._target_cells:
                if item["day"] in pending_days:
                    return {
                        "state": "check_in",
                        "day": item["day"],
                        "search_rect": item["search_rect"],
                    }
            return {"state": "completed"}

        # Những lần poll sau chỉ kiểm tra các ô đã lưu, theo đúng thứ tự.
        log(
            f"[{account.display_name}] Kiểm tra lại "
            f"{len(self._target_cells)} ô đã lưu."
        )
        for item in self._target_cells:
            try:
                already_match = self._match_day(
                    screen_bgr, already_template, item["search_rect"]
                )
            except (ValueError, cv2.error) as exc:
                log(
                    f"[{account.display_name}] Lỗi nhận diện trạng thái "
                    f"ngày {item['day']}: {exc}"
                )
                return None

            if already_match is not None:
                log(f"[{account.display_name}] Ngày {item['day']} đã điểm danh.")
                continue

            log(f"[{account.display_name}] Cần xử lý ngày {item['day']}.")
            return {
                "state": "check_in",
                "day": item["day"],
                "search_rect": item["search_rect"],
            }

        return {"state": "completed"}

