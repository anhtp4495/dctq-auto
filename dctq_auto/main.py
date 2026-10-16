"""Application entry point."""

import logging

from dctq_auto.adb.client import AdbClient
from dctq_auto.config.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = AdbClient(serial=settings.adb_serial)
    device = client.connect()
    screenshot_path = client.save_screenshot(device, settings.screenshot_dir)
    logging.getLogger(__name__).info("ADB connected; screenshot saved to %s", screenshot_path)


if __name__ == "__main__":
    main()
