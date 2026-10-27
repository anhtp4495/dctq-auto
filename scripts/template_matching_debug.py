"""CLI debugger for dctq_auto.vision.template_matching."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dctq_auto.vision.template_matching import match_template  # noqa: E402


METHODS = {
    "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
    "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find a template in a source image and print RECT(top,left,right,bottom)."
    )
    parser.add_argument("image", help="Path to the original/source image")
    parser.add_argument("template", help="Path to the smaller template image")
    parser.add_argument(
        "--rect", nargs=4, type=int, metavar=("TOP", "LEFT", "RIGHT", "BOTTOM"),
        help="Optional search area in original-image coordinates"
    )
    parser.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold (0..1, default: 0.8)")
    parser.add_argument("--method", choices=METHODS, default="TM_CCOEFF_NORMED")
    parser.add_argument("--color", action="store_true", help="Match color channels instead of grayscale")
    parser.add_argument("--output", help="Optional path to save a copy of the source image with the match rectangle")
    args = parser.parse_args()

    try:
        match = match_template(
            args.image,
            args.template,
            search_rect=tuple(args.rect) if args.rect else None,
            threshold=args.threshold,
            method=METHODS[args.method],
            grayscale=not args.color,
        )
    except (FileNotFoundError, ValueError, cv2.error) as exc:
        parser.error(str(exc))

    if match is None:
        print(f"No match found at threshold {args.threshold:.3f}.")
        return 1

    print(f"RECT(top, left, right, bottom) = {match.rect}")
    print(f"Similarity score = {match.score:.6f}")

    if args.output:
        source = cv2.imread(args.image, cv2.IMREAD_COLOR)
        if source is None:
            parser.error(f"Cannot read source image: {args.image}")
        cv2.rectangle(
            source,
            (match.left, match.top),
            (match.right - 1, match.bottom - 1),
            (0, 255, 0),
            2,
        )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), source):
            parser.error(f"Could not write output image: {output_path}")
        print(f"Debug image saved: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
