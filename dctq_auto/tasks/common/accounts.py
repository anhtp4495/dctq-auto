"""Đọc danh sách tài khoản từ file INI.

Chỉ hỗ trợ [Accounts] và [DisabledAccounts]. Không ghi mật khẩu vào log.
Nếu username xuất hiện ở cả hai section, DisabledAccounts được ưu tiên.

Mỗi dòng hỗ trợ:
    username = password
    username = password = display_name

Nếu không khai báo display_name, giá trị mặc định bằng username.
"""
import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameAccount:
    username: str
    password: str
    enabled: bool = True
    display_name: str = ""

    def __post_init__(self) -> None:
        # Keep older GameAccount(username, password[, enabled]) callers compatible.
        if not self.display_name:
            object.__setattr__(self, "display_name", self.username)


def load_accounts(path: str | Path) -> list[GameAccount]:
    """Đọc file INI UTF-8/UTF-8-BOM, trả về cả tài khoản bật và tắt."""
    account_file = Path(path).expanduser()
    if not account_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy file tài khoản: {account_file}")

    parser = configparser.ConfigParser(
        interpolation=None, strict=True, delimiters=("=",), comment_prefixes=("#", ";"),
        inline_comment_prefixes=None, empty_lines_in_values=False,
    )
    parser.optionxform = str
    try:
        with account_file.open("r", encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except configparser.Error as exc:
        raise ValueError(f"File tài khoản không phải INI hợp lệ: {exc}") from exc

    required = {"Accounts"}
    supported = {"Accounts", "DisabledAccounts"}
    missing = required - set(parser.sections())
    unknown = set(parser.sections()) - supported
    if missing:
        raise ValueError(
            "File INI thiếu section: " + ", ".join(f"[{name}]" for name in sorted(missing))
        )
    if unknown:
        raise ValueError(
            "Section không được hỗ trợ: " + ", ".join(f"[{name}]" for name in sorted(unknown))
        )

    active = {}
    disabled = {}
    sections = [("Accounts", active)]
    if parser.has_section("DisabledAccounts"):
        sections.append(("DisabledAccounts", disabled))

    for section, target in sections:
        for raw_username, raw_value in parser.items(section, raw=True):
            username = raw_username.strip()
            # The first '=' separates password from the optional display name.
            parts = raw_value.split("=", 1)
            password = parts[0].strip()
            display_name = parts[1].strip() if len(parts) > 1 else username
            if not username or not password:
                raise ValueError(f"Section [{section}] có tài khoản thiếu username hoặc password.")
            if username in target:
                raise ValueError(f"Tài khoản '{username}' bị lặp trong [{section}].")
            target[username] = (password, display_name or username)

    accounts = [
        GameAccount(username, password, True, display_name)
        for username, (password, display_name) in active.items()
        if username not in disabled
    ]
    accounts.extend(
        GameAccount(username, password, False, display_name)
        for username, (password, display_name) in disabled.items()
    )
    if not accounts:
        raise ValueError("File INI chưa có tài khoản hợp lệ trong [Accounts] hoặc [DisabledAccounts].")
    return accounts
