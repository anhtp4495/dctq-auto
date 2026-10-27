"""Debug pixel-based comparison between a template image and a cropped screenshot region.

Example:
    python scripts/debug_image_compare.py assets/template.png tmp/rect.png
    python scripts/debug_image_compare.py assets/template.png tmp/rect.png --tolerance 1.0 --pixel-threshold 12
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

# Make the repository root importable when this script is run as:
# python scripts/debug_image_compare.py ...
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dctq_auto.vision.image_compare import compare_image_rect  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a saved template image with an image file containing "
            "the already-cropped screenshot RECT."
        )
    )
    parser.add_argument(
        "template",
        type=Path,
        help="Path to the reference/template image (PNG recommended).",
    )
    parser.add_argument(
        "rect_image",
        type=Path,
        help="Path to the screenshot image cropped to exactly the RECT being checked.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="Maximum percentage of pixels allowed to differ (0-100; default: 0.5).",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=int,
        default=10,
        help="Per-channel pixel difference ignored (0-255; default: 10).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.template.is_file():
        print(f"ERROR: Template file not found: {args.template}", file=sys.stderr)
        return 2
    if not args.rect_image.is_file():
        print(f"ERROR: RECT image file not found: {args.rect_image}", file=sys.stderr)
        return 2
    if not 0 <= args.tolerance <= 100:
        print("ERROR: --tolerance must be between 0 and 100.", file=sys.stderr)
        return 2
    if not 0 <= args.pixel_threshold <= 255:
        print("ERROR: --pixel-threshold must be between 0 and 255.", file=sys.stderr)
        return 2

    rect_image = cv2.imread(str(args.rect_image), cv2.IMREAD_COLOR)
    if rect_image is None:
        print(f"ERROR: Could not read RECT image: {args.rect_image}", file=sys.stderr)
        return 2

    template_image = cv2.imread(str(args.template), cv2.IMREAD_COLOR)
    if template_image is None:
        print(f"ERROR: Could not read template image: {args.template}", file=sys.stderr)
        return 2

    print(f"Template : {args.template} ({template_image.shape[1]}x{template_image.shape[0]})")
    print(f"RECT img : {args.rect_image} ({rect_image.shape[1]}x{rect_image.shape[0]})")
    print(f"Tolerance: {args.tolerance}%")
    print(f"Pixel threshold: {args.pixel_threshold}")

    if template_image.shape != rect_image.shape:
        print("RESULT: NO MATCH")
        print("Reason: image dimensions differ; both images must have the same width and height.")
        return 1

    try:
        matched = compare_image_rect(
            template_path=args.template,
            rect_image=rect_image,
            tolerance=args.tolerance,
            pixel_threshold=args.pixel_threshold,
        )
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"RESULT: {'MATCH' if matched else 'NO MATCH'}")
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
