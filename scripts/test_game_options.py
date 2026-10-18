"""Manually test tapping one of three game options through ADB.

Run from the repository root, for example:
    py scripts/test_game_options.py --option 1
    py scripts/test_game_options.py --option 2
    py scripts/test_game_options.py --option 3

The coordinates are initial estimates. Check the screenshot and confirm before
sending a tap; only one option is tapped per run.
"""

from __future__ import annotations

import argparse
import re
import sys

from adbutils import adb


OPTIONS = {
    1: (500, 500),
    2: (1000, 500),
    3: (1400, 500),
}


def get_screen_size(device) -> tuple[int, int] | None:
    output = device.shell("wm size")
    matches = re.findall(r"(\d+)x(\d+)", output)
    if not matches:
        return None
    # If Android reports both physical and override sizes, use the last one.
    return int(matches[-1][0]), int(matches[-1][1])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tap one estimated game-option coordinate via ADB."
    )
    parser.add_argument(
        "--serial",
        default="emulator-5554",
        help="ADB device serial (default: emulator-5554)",
    )
    parser.add_argument(
        "--option",
        type=int,
        choices=(1, 2, 3),
        required=True,
        help="Which option to tap: 1, 2, or 3",
    )
    parser.add_argument("--x", type=int, help="Override the option's X coordinate")
    parser.add_argument("--y", type=int, help="Override the option's Y coordinate")
    args = parser.parse_args()

    default_x, default_y = OPTIONS[args.option]
    x = default_x if args.x is None else args.x
    y = default_y if args.y is None else args.y

    if x < 0 or y < 0:
        parser.error("Coordinates must be non-negative")
    if (args.x is None) != (args.y is None):
        parser.error("Pass both --x and --y when overriding coordinates")

    try:
        device = adb.device(serial=args.serial)
        state = device.get_state()
        if state != "device":
            print(
                f"Device {args.serial} is not online (state: {state}).",
                file=sys.stderr,
            )
            return 1

        size = get_screen_size(device)
        print(f"Device: {args.serial} ({state})")
        if size:
            width, height = size
            print(f"Screen size: {width}x{height}")
            if x >= width or y >= height:
                print(
                    f"Coordinate ({x}, {y}) is outside the screen bounds.",
                    file=sys.stderr,
                )
                return 1
        else:
            print("Warning: could not read screen size; coordinate bounds not checked.")

        print(f"Option {args.option} will be tapped at x={x}, y={y}.")
        print("Check the emulator screen before continuing.")
        confirmation = input("Type TAP to send the tap, or anything else to cancel: ")
        if confirmation.strip() != "TAP":
            print("Cancelled; no tap was sent.")
            return 0

        device.click(x, y)
        print(f"Tap command sent for option {args.option}.")
        return 0
    except Exception as exc:
        print(f"ADB option test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
