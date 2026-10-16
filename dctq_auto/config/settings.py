"""Environment-based settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    adb_serial: str | None = None
    log_dir: Path = Path("logs")
    screenshot_dir: Path = Path("artifacts/screenshots")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        serial = os.getenv("ADB_SERIAL", "").strip() or None
        return cls(
            adb_serial=serial,
            log_dir=Path(os.getenv("LOG_DIR", "logs")),
            screenshot_dir=Path(os.getenv("SCREENSHOT_DIR", "artifacts/screenshots")),
        )
