"""Metadata nhiệm vụ báo danh quân đoàn cho tài khoản clone."""
from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_guild_check_in",
    label="Báo danh quân đoàn",
    description="Báo danh quân đoàn cho tài khoản hiện tại.",
    category="clone",
)
