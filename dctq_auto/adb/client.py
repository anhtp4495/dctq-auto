"""ADB device wrapper based on adbutils."""

from pathlib import Path

from adbutils import AdbDevice, adb


class AdbClient:
    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial

    def connect(self) -> AdbDevice:
        device = adb.device(serial=self.serial) if self.serial else adb.device()
        device.get_state()
        return device

    @staticmethod
    def save_screenshot(device: AdbDevice, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "current_screen.png"
        device.screenshot().save(str(output_path))
        return output_path
