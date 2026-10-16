"""Kiểu dữ liệu chung cho các nhiệm vụ.

TaskSpec mô tả một hành động để worker tổng và giao diện dùng chung:
- khóa bật/tắt trong cấu hình;
- tên hiển thị;
- khóa số lượt (nếu có);
- nhóm và mô tả tiếng Việt.

Module nhiệm vụ không được tự cập nhật thanh tiến trình giao diện.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    """Metadata của một nhiệm vụ tự động hóa."""

    key: str
    label: str
    description: str
    category: str
    count_key: str | None = None
    enabled_key: str | None = None
    default_count: int = 1

    def is_enabled(self, config: dict) -> bool:
        """Kiểm tra nhiệm vụ có được bật trong cấu hình hay không."""
        flag = self.enabled_key or self.key
        return bool(config.get(flag))

    def get_count(self, config: dict) -> int:
        """Lấy số lượt cần chạy, luôn tối thiểu là 1."""
        if not self.count_key:
            return self.default_count
        try:
            return max(1, int(config.get(self.count_key, self.default_count)))
        except (TypeError, ValueError):
            return self.default_count
