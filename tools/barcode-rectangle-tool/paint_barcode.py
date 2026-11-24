#!/usr/bin/env python3
"""Paint a dark barcode cover with a light inset in a JPEG image."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw


def brightness(rgb: tuple[int, int, int]) -> int:
    return 2126 * rgb[0] + 7152 * rgb[1] + 722 * rgb[2]


def paint(path: Path, x: int, y: int, width: int, height: int) -> int:
    with Image.open(path) as original:
        image = original.convert("RGB")
        pixels = list(image.getdata())
        darkest = min(pixels, key=brightness)
        lightest = max(pixels, key=brightness)
        left = max(0, min(image.width - 1, x))
        top = max(0, min(image.height - 1, y))
        right = max(left, min(image.width - 1, x + width - 1))
        bottom = max(top, min(image.height - 1, y + height - 1))
        border = max(1, round(image.width * 0.005 / 2))
        draw = ImageDraw.Draw(image)
        draw.rectangle((left, top, right, bottom), fill=darkest)
        inner = (left + border, top + border, right - border, bottom - border)
        if inner[0] <= inner[2] and inner[1] <= inner[3]:
            draw.rectangle(inner, fill=lightest)
        exif = original.getexif()
        image.save(path, "JPEG", quality=95, subsampling=0, exif=exif)
    return border


if __name__ == "__main__":
    try:
        border_pixels = paint(Path(sys.argv[1]), *map(int, sys.argv[2:6]))
        print(f"Saved. Inset border: {border_pixels}px.")
    except (IndexError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
