"""Poller cho chế độ Giao Tranh có giới hạn thời gian."""

import time

from .base_poller import BasePoller


class TimeLimitPoller(BasePoller):
    """Đánh dấu kết thúc khi thời gian triển khai trận đã vượt giới hạn."""

    def check(self, context) -> dict | None:
        observation = super().check(context)
        if observation is None:
            return None

        started_at = context.get("battle_started_at")
        if started_at is None:
            return observation

        seconds = context["battle_config"].time_limit_seconds
        elapsed = time.monotonic() - started_at
        if elapsed >= seconds:
            account = context["account"]
            context["log"](
                f"[{account.username}] Đã vượt thời gian tối đa "
                f"{seconds} giây (thực tế {elapsed:.1f} giây)."
            )
            observation["should_end"] = True
            observation["end_reason"] = "time_limit"
        return observation
