"""Lớp cơ sở cho poller của các tác vụ Quân đoàn."""

import cv2

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


class BaseGuildPoller:
    """Thực hiện một nhịp polling và trả về template khớp đầu tiên."""

    def poll(self, screen_bgr, templates, template_names, account, log):
        if screen_bgr is None:
            return None, None

        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
                log(
                    f"[{account.display_name}] Không tải được template "
                    f"{template_name}; bỏ qua."
                )
                continue

            try:
                matched = match_template(
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

            if matched is not None:
                report_template_match(
                    log,
                    context=f"[{account.display_name}]",
                    template=template,
                    match=matched,
                )
                return template_name, matched

        return None, None
