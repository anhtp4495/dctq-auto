"""ADB device wrapper based on adbutils."""

from pathlib import Path

from adbutils import AdbDevice, adb


class AdbClient:
    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial

    @staticmethod
    def list_devices() -> list[AdbDevice]:
        """Return devices currently visible to the ADB server."""
        return adb.device_list()

    def connect(self) -> AdbDevice:
        if not self.serial:
            raise RuntimeError("Chưa chọn thiết bị ADB. Hãy quét và chọn LDPlayer.")
        device = adb.device(serial=self.serial)
        device.get_state()
        return device

    @staticmethod
    def save_screenshot(device: AdbDevice, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "current_screen.png"
        device.screenshot().save(str(output_path))
        return output_path
