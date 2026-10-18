"""Đọc danh sách tài khoản clone từ file TXT.

Mỗi dòng có dạng: username|password
Dòng trống và dòng bắt đầu bằng # được bỏ qua. Không ghi mật khẩu vào log.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CloneAccount:
    username: str
    password: str


def load_accounts(path: str | Path) -> list[CloneAccount]:
    """Đọc và kiểm tra danh sách tài khoản từ file UTF-8/UTF-8-BOM."""
    account_file = Path(path).expanduser()
    if not account_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy file tài khoản: {account_file}")

    accounts: list[CloneAccount] = []
    for line_number, raw_line in enumerate(
        account_file.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            raise ValueError(
                f"Dòng {line_number} không đúng định dạng. Dùng username|password."
            )
        username, password = (part.strip() for part in line.split("|", 1))
        if not username or not password:
            raise ValueError(
                f"Dòng {line_number} thiếu username hoặc password."
            )
        accounts.append(CloneAccount(username=username, password=password))

    if not accounts:
        raise ValueError("File TXT chưa có tài khoản hợp lệ.")
    return accounts
