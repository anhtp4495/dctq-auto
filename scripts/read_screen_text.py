"""Extract visible Android UI text through ADB's UI hierarchy dump.

Run from the repository root:
    py scripts/read_screen_text.py
    py scripts/read_screen_text.py --serial emulator-5554

This reads Android accessibility/UI hierarchy text. Games that draw their UI
inside a custom canvas (for example some Unity games) may expose no option text;
use OCR on a screenshot in that case.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

from adbutils import adb


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List text labels exposed by the Android UI hierarchy."
    )
    parser.add_argument(
        "--serial",
        default="emulator-5554",
        help="ADB device serial (default: emulator-5554)",
    )
    args = parser.parse_args()

    try:
        device = adb.device(serial=args.serial)
        state = device.get_state()
        if state != "device":
            print(f"Device {args.serial} is not online (state: {state}).", file=sys.stderr)
            return 1

        # adbutils exposes Android's uiautomator dump via dump_hierarchy().
        xml_text = device.dump_hierarchy()
        root = ET.fromstring(xml_text)

        seen: set[str] = set()
        texts: list[str] = []
        for node in root.iter():
            text = (node.attrib.get("text") or "").strip()
            description = (node.attrib.get("content-desc") or "").strip()
            for value in (text, description):
                if value and value not in seen:
                    seen.add(value)
                    texts.append(value)

        if not texts:
            print("No text labels found in the Android UI hierarchy.")
            print(
                "The game may render text in a custom canvas. "
                "Try screenshot OCR as a fallback."
            )
            return 0

        print(f"Found {len(texts)} unique text/description label(s):")
        for index, value in enumerate(texts, start=1):
            print(f"{index}. {value}")
        return 0

    except ET.ParseError as exc:
        print(f"Could not parse UI hierarchy XML: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to read UI text via ADB: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
