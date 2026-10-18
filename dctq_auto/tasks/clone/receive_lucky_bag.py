"""Metadata nhiệm vụ nhận túi phúc cho tài khoản clone."""
from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_receive_lucky_bag",
    label="Nhận túi phúc",
    description="Nhận túi phúc cho tài khoản hiện tại.",
    category="clone",
)
