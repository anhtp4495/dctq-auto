"""Poller nhận diện trạng thái nhận Lễ bao Quốc Vận; không thao tác trên thiết bị."""

import cv2

from dctq_auto.config.constants import (
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


class NationalFortuneGiftPoller:
    """Nhận diện trạng thái hiện tại của Lễ bao Quốc Vận."""

    TEMPLATE_NAMES = (
        _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
        _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
        _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1,
        _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2,
        _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    )

    STATE_BY_TEMPLATE = {
        _TEMPLATE_NHAN_LE_BAO_MIEN_PHI: "claim_available",
        _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI: "claimed",
        _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1: "dismiss_notice",
        _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2: "dismiss_notice",
        _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN: "tab_selected",
    }

    def poll(self, screen_bgr, templates, account, log) -> dict:
        """Tìm trạng thái đầu tiên khớp theo thứ tự ưu tiên."""
        for template_name in self.TEMPLATE_NAMES:
            template = templates.get(template_name)
            if template is None:
                log(
                    f"[{account.display_name}] Không tải được template "
                    f"{template_name}; bỏ qua."
                )
                continue

            try:
                match = match_template(
                    screen_bgr,
                    template.image,
                    threshold=template.threshold,
                    method=template.method,
                    search_rect=template.search_rect,
                    grayscale=template.grayscale,
                )
            except (ValueError, cv2.error) as exc:
                log(
                    f"[{account.display_name}] Lỗi template matching "
                    f"{template_name}: {exc}"
                )
                continue

            if match is None:
                continue

            report_template_match(
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )
            return {
                "state": self.STATE_BY_TEMPLATE[template_name],
                "template_name": template_name,
                "template": template,
                "match": match,
            }

        return {
            "state": "not_found",
            "template_name": None,
            "template": None,
            "match": None,
        }
