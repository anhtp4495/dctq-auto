"""Lớp cơ sở cho polling và chuẩn hóa observation của Quân đoàn."""

import cv2
from importlib import import_module

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


class BaseGuildPoller:
    """Thực hiện một nhịp polling; lớp con chịu trách nhiệm phân loại trạng thái."""

    category_key = ""
    state_by_template = {}
    step_id = None
    task_module = None

    @classmethod
    def create(cls, context):
        """Chỉ tạo Poller khi step tương ứng được chọn."""
        if cls.step_id not in context["steps"]:
            return None
        return cls()

    def run(self, context):
        """Chạy trọn quy trình nghiệp vụ của task tương ứng."""
        if self.step_id not in context["steps"]:
            context["log"](
                f"[{context['account'].display_name}] [Quân đoàn] "
                f"{self.category_key}: không có step; bỏ qua."
            )
            return context["steps"]

        module = import_module(
            f"dctq_auto.tasks.common.guild.{self.task_module}"
        )
        return module.run(
            context["worker"],
            context["account"],
            context["steps"],
            context["device"],
            context.get("ocr_client"),
            context["log"],
            screenshot=context.get("screenshot"),
        )

    def poll(self, screen_bgr, templates, template_names, account, log):
        """Trả observation đã được lớp con phân loại."""
        context = {
            "screen": screen_bgr,
            "templates": templates,
            "template_names": tuple(template_names),
            "account": account,
            "log": log,
        }
        return self.check(context)

    def check(self, context) -> dict:
        """Lớp con phân loại observation theo nghiệp vụ của task."""
        raise NotImplementedError

    def _match_first(self, context) -> dict:
        """Tìm template đầu tiên khớp theo thứ tự ưu tiên của phase hiện tại."""
        account = context["account"]
        log = context["log"]
        screen = context["screen"]

        for template_name in context["template_names"]:
            template = context["templates"].get(template_name)
            if template is None:
                log(
                    f"[{account.display_name}] [Quân đoàn] "
                    f"Không tải được template {template_name}; bỏ qua."
                )
                continue

            try:
                matched = match_template(
                    screen,
                    template.image,
                    threshold=template.threshold,
                    method=template.method,
                    search_rect=template.search_rect,
                    grayscale=template.grayscale,
                )
            except (ValueError, cv2.error) as exc:
                log(
                    f"[{account.display_name}] [Quân đoàn] "
                    f"Lỗi matching template {template_name}: {exc}"
                )
                continue

            if matched is None:
                continue

            report_template_match(
                log,
                context=f"[{account.display_name}] [Quân đoàn] [{self.category_key}]",
                template=template,
                match=matched,
            )
            return {
                "category": self.category_key,
                "state": self.state_by_template.get(template_name, "recognized"),
                "template_name": template_name,
                "template": template,
                "match": matched,
            }

        return {
            "category": self.category_key,
            "state": "not_found",
            "template_name": None,
            "template": None,
            "match": None,
        }
