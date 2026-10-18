"""Metadata nhiệm vụ đăng xuất tài khoản clone."""
from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_logout",
    label="Đăng xuất",
    description="Đăng xuất sau khi hoàn tất các nhiệm vụ của tài khoản.",
    category="clone",
)
