"""Manually test a single ADB tap on an Android emulator.

Run from the repository root:
    py scripts/try_adb_click.py --serial emulator-5554 --x 500 --y 500

Choose coordinates carefully: the tap may activate a button in the game.
"""

from __future__ import annotations

import argparse
import sys

from adbutils import adb


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send one tap to an Android device through ADB."
    )
    parser.add_argument(
        "--serial",
        default="emulator-5554",
        help="ADB device serial (default: emulator-5554)",
    )
    parser.add_argument("--x", type=int, required=True, help="Tap X coordinate")
    parser.add_argument("--y", type=int, required=True, help="Tap Y coordinate")
    args = parser.parse_args()

    if args.x < 0 or args.y < 0:
        parser.error("--x and --y must be non-negative")

    try:
        device = adb.device(serial=args.serial)
        state = device.get_state()
        if state != "device":
            print(f"Device {args.serial} is not online (state: {state}).", file=sys.stderr)
            return 1

        size = device.shell("wm size").strip()
        print(f"Device: {args.serial} ({state})")
        print(f"Screen: {size}")
        print(f"Sending one tap at x={args.x}, y={args.y} ...")
        device.click(args.x, args.y)
        print("Tap command sent.")
        return 0
    except Exception as exc:
        print(f"ADB tap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
