"""Metadata nhiệm vụ đăng nhập tài khoản clone."""
from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_login",
    label="Đăng nhập",
    description="Đăng nhập vào tài khoản đang được xử lý.",
    category="clone",
)
