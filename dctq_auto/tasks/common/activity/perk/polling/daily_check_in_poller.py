"""Poller nhận diện trạng thái 30 ô Điểm danh; không thực hiện thao tác trên thiết bị."""

import cv2

from dctq_auto.config.constants import (
    _TEMPLATE_DA_DIEM_DANH,
    _TEMPLATE_DIEM_DANH_BU,
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
        """Trả trạng thái từng ô, ngày thường kế tiếp và danh sách ngày bù.

        Mọi ô không nhận diện là đã điểm danh vẫn được xem là chưa hoàn thành,
        giống quy tắc xử lý trước đây. Template điểm danh bù chỉ bổ sung thông tin
        trạng thái hiển thị, không loại ô đó khỏi danh sách ứng viên.
        """
        already_template = templates.get(_TEMPLATE_DA_DIEM_DANH)
        catchup_template = templates.get(_TEMPLATE_DIEM_DANH_BU)
        if already_template is None or catchup_template is None:
            log(f"[{account.display_name}] Thiếu template trạng thái ngày điểm danh.")
            return None

        day_regions = self.build_day_regions(screen_width, screen_height)
        days = []
        already_days = set()
        log(f"[{account.display_name}] Bắt đầu quét trạng thái {len(day_regions)} ngày.")

        for day, search_rect in day_regions:
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
                    state = "catchup_available" if catchup_match is not None else "not_completed"
                    if catchup_match is not None:
                        report_template_match(
                            log,
                            context=f"[{account.display_name}] Ngày {day}",
                            template=catchup_template,
                            match=catchup_match,
                        )
                    log(f"[{account.display_name}] Ngày {day} chưa điểm danh.")
            except (ValueError, cv2.error) as exc:
                log(f"[{account.display_name}] Lỗi nhận diện trạng thái ngày {day}: {exc}")
                return None
            except Exception as exc:
                log(f"[{account.display_name}] Không kiểm tra được ngày {day}: {exc}")
                return None

            days.append({
                "day": day,
                "state": state,
                "search_rect": search_rect,
            })

        # Giữ nguyên cách xác định của task cũ: ngày thường là ngày ngay sau
        # ngày đã hoàn thành có số lớn nhất; các ngày thiếu phía trước là ứng viên bù.
        target_day = max(already_days, default=0) + 1
        catchup_days = [
            item["day"]
            for item in days
            if item["day"] < target_day and item["state"] != "completed"
        ]

        log(
            f"[{account.display_name}] Ngày cần điểm danh thường: {target_day}; "
            f"các ngày có thể điểm danh bù: {catchup_days}."
        )
        return {
            "days": days,
            "already_days": already_days,
            "day_regions": day_regions,
            "target_day": target_day,
            "catchup_days": catchup_days,
        }
