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


def crop_by_rect(image_path: str, rect: tuple[int, int, int, int]):
    """Crop RECT in (top, left, right, bottom) order; right/bottom are exclusive."""
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    top, left, right, bottom = rect
    height, width = image.shape[:2]
    if top < 0 or left < 0 or right > width or bottom > height:
        raise ValueError(
            f"RECT (top, left, right, bottom)={rect} is outside image bounds "
            f"(width={width}, height={height})"
        )
    if right <= left or bottom <= top:
        raise ValueError(
            f"RECT (top, left, right, bottom)={rect} must have positive width "
            "and height. Note: expected order is TOP LEFT RIGHT BOTTOM."
        )
    return image[top:bottom, left:right]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find a template in a source image. RECT arguments use "
            "(TOP, LEFT, RIGHT, BOTTOM) order."
        )
    )
    parser.add_argument("image", help="Path to the original/source image")
    parser.add_argument(
        "template",
        help="Path to template image; may be the full-size original image when --template-rect is used",
    )
    parser.add_argument(
        "--rect", nargs=4, type=int, metavar=("TOP", "LEFT", "RIGHT", "BOTTOM"),
        help="Optional search area in source-image coordinates: TOP LEFT RIGHT BOTTOM",
    )
    parser.add_argument(
        "--template-rect", nargs=4, type=int,
        metavar=("TOP", "LEFT", "RIGHT", "BOTTOM"),
        help="Crop this rectangle from the template image before matching: TOP LEFT RIGHT BOTTOM",
    )
    parser.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold (0..1, default: 0.8)")
    parser.add_argument("--method", choices=METHODS, default="TM_CCOEFF_NORMED")
    parser.add_argument("--color", action="store_true", help="Match color channels instead of grayscale")
    parser.add_argument("--output", help="Optional path to save source image with the match rectangle")
    parser.add_argument(
        "--save-template-crop",
        help="Optional path to save the cropped template specified by --template-rect",
    )
    args = parser.parse_args()

    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")

    try:
        template_input = args.template
        if args.template_rect:
            template_input = crop_by_rect(args.template, tuple(args.template_rect))
            if args.save_template_crop:
                output_template = Path(args.save_template_crop)
                output_template.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(output_template), template_input):
                    parser.error(f"Could not write cropped template: {output_template}")
                print(
                    f"Cropped template saved: {output_template} "
                    f"(size={template_input.shape[1]}x{template_input.shape[0]})"
                )

        match = match_template(
            args.image,
            template_input,
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
