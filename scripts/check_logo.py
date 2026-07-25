#!/usr/bin/env python3
"""Pre-push logo sanity check for GitHub/Hugging Face display.

The script validates a raster logo image and writes a checkerboard preview so
you can confirm the logo is visible before committing or pushing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw


DEFAULT_CANDIDATES = (
    "assets/logo.png",
    "docs/assets/logo.png",
    "static/logo.png",
    "logo.png",
)


@dataclass
class LogoReport:
    path: str
    format: str
    width: int
    height: int
    file_size_bytes: int
    aspect_ratio: float
    visible_pixel_ratio: float
    visible_bbox_ratio: float
    unique_visible_colors: int
    preview_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that a logo image is suitable before pushing."
    )
    parser.add_argument(
        "--logo",
        type=Path,
        default=None,
        help=(
            "Path to the logo file. If omitted, common paths are tried: "
            + ", ".join(DEFAULT_CANDIDATES)
        ),
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=256,
        help="Minimum width and height in pixels. Default: 256.",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=2.0,
        help="Maximum file size in MB. Default: 2.",
    )
    parser.add_argument(
        "--min-visible-ratio",
        type=float,
        default=0.03,
        help="Minimum ratio of non-transparent pixels. Default: 0.03.",
    )
    parser.add_argument(
        "--min-bbox-ratio",
        type=float,
        default=0.20,
        help="Minimum visible-content bounding-box ratio. Default: 0.20.",
    )
    parser.add_argument(
        "--allow-wide",
        action="store_true",
        help="Allow non-square logos, useful for README banners.",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("generated/logo_preview.png"),
        help="Output path for the checkerboard preview.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the validation report as JSON.",
    )
    return parser.parse_args()


def find_logo(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        return explicit_path

    for candidate in DEFAULT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path

    choices = "\n".join(f"  - {candidate}" for candidate in DEFAULT_CANDIDATES)
    raise FileNotFoundError(
        "No logo file found. Add one of these paths or pass --logo:\n" + choices
    )


def fail(message: str) -> None:
    print(f"Logo check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def count_unique_visible_colors(image: Image.Image, alpha_threshold: int = 20) -> int:
    thumb = image.copy()
    thumb.thumbnail((128, 128), Image.Resampling.LANCZOS)
    rgba = thumb.convert("RGBA")
    colors = {
        (r, g, b, a)
        for r, g, b, a in rgba.getdata()
        if a > alpha_threshold
    }
    return len(colors)


def visible_pixel_ratio(image: Image.Image, alpha_threshold: int = 20) -> float:
    rgba = image.convert("RGBA")
    pixels = rgba.getdata()
    visible = sum(1 for _, _, _, alpha in pixels if alpha > alpha_threshold)
    return visible / (rgba.width * rgba.height)


def visible_bbox_ratio(image: Image.Image, alpha_threshold: int = 20) -> float:
    alpha = image.convert("RGBA").getchannel("A")
    mask = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return 0.0

    left, top, right, bottom = bbox
    bbox_area = (right - left) * (bottom - top)
    return bbox_area / (image.width * image.height)


def make_checkerboard(size: int = 640, square: int = 32) -> Image.Image:
    image = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    colors = ((238, 238, 238, 255), (255, 255, 255, 255))
    for y in range(0, size, square):
        for x in range(0, size, square):
            color = colors[((x // square) + (y // square)) % 2]
            draw.rectangle((x, y, x + square - 1, y + square - 1), fill=color)
    return image


def write_preview(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    canvas = make_checkerboard()
    logo = image.convert("RGBA")
    logo.thumbnail((512, 512), Image.Resampling.LANCZOS)
    x = (canvas.width - logo.width) // 2
    y = (canvas.height - logo.height) // 2
    canvas.alpha_composite(logo, (x, y))
    canvas.save(output_path)


def validate_logo(path: Path, args: argparse.Namespace) -> LogoReport:
    require(path.exists(), f"{path} does not exist.")
    require(path.is_file(), f"{path} is not a file.")

    size = path.stat().st_size
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    require(size <= max_bytes, f"{path} is {size} bytes; max is {max_bytes}.")

    try:
        with Image.open(path) as image:
            image.load()
            image_format = image.format or "unknown"
            width, height = image.size
            aspect_ratio = width / height if height else 0.0
            visible_ratio = visible_pixel_ratio(image)
            bbox_ratio = visible_bbox_ratio(image)
            unique_colors = count_unique_visible_colors(image)

            require(
                image_format.lower() in {"png", "jpeg", "jpg", "webp"},
                f"{path} is {image_format}; use PNG, JPG/JPEG, or WEBP.",
            )
            require(
                width >= args.min_size and height >= args.min_size,
                (
                    f"{path} is {width}x{height}; expected at least "
                    f"{args.min_size}x{args.min_size}."
                ),
            )

            if not args.allow_wide:
                require(
                    0.80 <= aspect_ratio <= 1.25,
                    (
                        f"{path} aspect ratio is {aspect_ratio:.2f}; "
                        "use a square-ish logo or pass --allow-wide."
                    ),
                )

            require(
                visible_ratio >= args.min_visible_ratio,
                (
                    f"{path} has only {visible_ratio:.2%} visible pixels; "
                    "the logo may be mostly transparent."
                ),
            )
            require(
                bbox_ratio >= args.min_bbox_ratio,
                (
                    f"{path} visible content occupies only {bbox_ratio:.2%} "
                    "of the canvas; crop or enlarge the mark."
                ),
            )
            require(
                unique_colors >= 3,
                f"{path} appears blank or nearly single-color after sampling.",
            )

            write_preview(image, args.preview)

            return LogoReport(
                path=str(path),
                format=image_format,
                width=width,
                height=height,
                file_size_bytes=size,
                aspect_ratio=round(aspect_ratio, 4),
                visible_pixel_ratio=round(visible_ratio, 4),
                visible_bbox_ratio=round(bbox_ratio, 4),
                unique_visible_colors=unique_colors,
                preview_path=str(args.preview),
            )
    except OSError as exc:
        fail(f"{path} could not be opened as an image: {exc}")


def print_report(report: LogoReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(report), indent=2))
        return

    print("Logo check passed.")
    print(f"  File: {report.path}")
    print(f"  Format: {report.format}")
    print(f"  Size: {report.width}x{report.height}px")
    print(f"  File size: {report.file_size_bytes} bytes")
    print(f"  Aspect ratio: {report.aspect_ratio}")
    print(f"  Visible pixels: {report.visible_pixel_ratio:.2%}")
    print(f"  Visible bounding box: {report.visible_bbox_ratio:.2%}")
    print(f"  Unique visible colors: {report.unique_visible_colors}")
    print(f"  Preview: {report.preview_path}")


def main() -> None:
    args = parse_args()
    logo_path = find_logo(args.logo)
    report = validate_logo(logo_path, args)
    print_report(report, args.json)


if __name__ == "__main__":
    main()
