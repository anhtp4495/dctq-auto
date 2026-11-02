"""Lớp chiến đấu cơ sở - chuẩn bị và triển khai đội hình."""


class BaseBattle:
    """Giao diện chung cho các chiến thuật triển khai võ tướng."""

    def prepare(self, context) -> bool:
        """Chuẩn bị dữ liệu chiến thuật trước khi triển khai đội hình."""
        return True

    def deploy(self, context) -> bool:
        """Triển khai đội hình cho một trận mới."""
        raise NotImplementedError
