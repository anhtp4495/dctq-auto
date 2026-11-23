"""Lớp cơ sở cho các poller của Trưởng Thành."""

import time


class BaseMaturityPoller:
    """Định nghĩa polling và cập nhật tiến trình dùng chung."""

    poll_interval = 1.0
    category_key = ""
    progress_steps = ()

    def __init__(self):
        self.waiting_for_main = False
        self._progress_id = None
        self._progress_current = 0
        self._completed_steps = set()

    def _ensure_progress(self, context) -> None:
        """Tạo tiến trình riêng cho category khi poller bắt đầu chạy."""
        if self._progress_id is not None:
            return

        worker = context["worker"]
        label = context.get("label", self.category_key)
        self._progress_id = worker.UpdateOrCreateProcessProgress(
            name=f"Trưởng thành - {label}",
            status="running",
            current=0,
            total=len(self.progress_steps) + 1,
            message=f"Đang xử lý {label}",
        )

    def record_action(self, key: str, context) -> None:
        """Ghi nhận một thao tác đã click thành công."""
        self._ensure_progress(context)
        if key in self._completed_steps:
            return

        labels = dict(self.progress_steps)
        label = labels.get(key)
        if label is None:
            return

        self._completed_steps.add(key)
        self._progress_current += 1
        context["worker"].UpdateOrCreateProcessProgress(
            name=f"Trưởng thành - {context.get('label', self.category_key)}",
            status="running",
            current=self._progress_current,
            total=len(self.progress_steps) + 1,
            message=f"Đã hoàn thành: {label}",
        )

    def finish(self, context, status: str, message: str) -> None:
        """Cập nhật trạng thái kết thúc của tiến trình category."""
        self._ensure_progress(context)
        worker = context["worker"]
        total = len(self.progress_steps) + 1
        current = total if status == "success" else self._progress_current
        self._progress_id = worker.UpdateOrCreateProcessProgress(
            name=f"Trưởng thành - {context.get('label', self.category_key)}",
            status=status,
            current=current,
            total=total,
            message=message,
        )
        worker.UpdateProcessStatus(self._progress_id, status)

    def poll(self, context) -> dict | None:
        """Chờ một nhịp, kiểm tra trạng thái tạm dừng rồi lấy observation."""
        self._ensure_progress(context)
        if not context["worker"]._wait_if_paused():
            context["log"](
                f"[{context['account'].display_name}] "
                "Đã dừng khi polling Trưởng Thành."
            )
            self.finish(context, "stopped", "Đã dừng")
            return None

        time.sleep(self.poll_interval)
        observation = self.check(context)
        if observation is None:
            self.finish(context, "failed", "Không chụp được màn hình")
        return observation

    def check(self, context) -> dict | None:
        """Lớp con triển khai nhận diện trạng thái."""
        raise NotImplementedError
