from pathlib import Path

import pytest

from dctq_auto.tasks.clone.accounts import load_accounts


def test_load_accounts_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    account_file = tmp_path / "accounts.txt"
    account_file.write_text(
        "# tài khoản test\n\nuser1|pass1\nuser2@example.com|pass|with|pipes\n",
        encoding="utf-8",
    )

    accounts = load_accounts(account_file)

    assert [(account.username, account.password) for account in accounts] == [
        ("user1", "pass1"),
        ("user2@example.com", "pass|with|pipes"),
    ]


def test_load_accounts_rejects_invalid_line(tmp_path: Path) -> None:
    account_file = tmp_path / "accounts.txt"
    account_file.write_text("user_without_password\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Dòng 1"):
        load_accounts(account_file)


def test_load_accounts_rejects_empty_file(tmp_path: Path) -> None:
    account_file = tmp_path / "accounts.txt"
    account_file.write_text("# chưa có tài khoản\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chưa có tài khoản"):
        load_accounts(account_file)
