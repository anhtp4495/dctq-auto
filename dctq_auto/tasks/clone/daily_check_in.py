"""Metadata nhiệm vụ điểm danh tài khoản clone."""
from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_daily_check_in",
    label="Điểm danh",
    description="Điểm danh hằng ngày cho tài khoản hiện tại.",
    category="clone",
)
