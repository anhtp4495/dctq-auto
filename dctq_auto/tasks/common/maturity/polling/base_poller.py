"""Lớp cơ sở cho các poller của Trưởng Thành."""

import time


class BaseMaturityPoller:
    """Định nghĩa giao diện polling dùng chung cho từng category."""

    poll_interval = 1.0

    def poll(self, context) -> dict | None:
        """Chờ một nhịp, kiểm tra trạng thái tạm dừng rồi lấy observation."""
        if not context["worker"]._wait_if_paused():
            context["log"](
                f"[{context['account'].display_name}] "
                "Đã dừng khi polling Trưởng Thành."
            )
            return None

        time.sleep(self.poll_interval)
        return self.check(context)

    def check(self, context) -> dict | None:
        """Lớp con triển khai nhận diện trạng thái."""
        raise NotImplementedError
