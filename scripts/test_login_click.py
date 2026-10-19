"""Manual ADB test: tap the login form username field and type a test value.

Run from the repository root:
    python scripts/test_login_click.py

Coordinates are based on the supplied 1920x1080 screenshot. Verify the emulator
resolution before running; this script only types the harmless test string "xxx"
into the username field and does not submit the login form.
"""
import subprocess
import time

ADB = "adb"
DEVICE = "emulator-5554"


def adb(*args: object) -> None:
    command = [ADB, "-s", DEVICE, *map(str, args)]
    print(">", " ".join(command))
    subprocess.run(command, check=True)


def click_rect(rect: tuple[int, int, int, int]) -> None:
    """Tap the center of a rectangle: (left, top, right, bottom)."""
    left, top, right, bottom = rect
    x = (left + right) // 2
    y = (top + bottom) // 2
    print(f"Click rect={rect} -> ({x}, {y})")
    adb("shell", "input", "tap", x, y)
    time.sleep(0.5)


def type_text(text: str) -> None:
    """Type text through Android's input command; spaces use %s."""
    adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(0.5)


if __name__ == "__main__":
    # Coordinates from the supplied screenshot (assumed 1920x1080).
    username_rect = (564, 389, 686, 413)

    # Safe first test: tap username and type "xxx"; do not submit the form.
    click_rect(username_rect)
    type_text("xxx")
