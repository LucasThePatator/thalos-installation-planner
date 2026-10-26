"""Shared test helpers.

`assert_fits_a4` is the pixel-level overflow check developed live in an earlier
session to track down a real bug (a single very-long item name rendering a
chip wider than its box). A geometry-only check — reading `x`/`width` out of
the SVG's `<rect>`/`<text>` elements — had missed that bug because it never
accounted for actual glyph widths. Rasterizing and scanning for opaque pixels
outside the page is what actually caught it, so that's what's kept here
instead of the cheaper but blind geometry approach.
"""

from __future__ import annotations

import io
import re

import cairosvg
from PIL import Image

PAGE_W, PAGE_H = 210.0, 297.0
PAD_MM = 30.0


def _widen(svg: str) -> str:
    """Grow the SVG's canvas by PAD_MM on every side without moving any of
    its content — anything that used to render past the original A4 edges
    becomes visible pixels in the new margin instead of being clipped away."""
    widened = svg.replace(
        f'viewBox="0 0 {PAGE_W} {PAGE_H}"',
        f'viewBox="{-PAD_MM} {-PAD_MM} {PAGE_W + 2 * PAD_MM} {PAGE_H + 2 * PAD_MM}"',
    )
    widened = re.sub(r'width="[\d.]+mm"', f'width="{PAGE_W + 2 * PAD_MM}mm"', widened, count=1)
    widened = re.sub(r'height="[\d.]+mm"', f'height="{PAGE_H + 2 * PAD_MM}mm"', widened, count=1)
    return widened


def assert_fits_a4(svg: str, label: str = "") -> None:
    """Fail if any non-background content in `svg` renders outside the
    original A4 page rectangle."""
    png_bytes = cairosvg.svg2png(bytestring=_widen(svg).encode("utf-8"))
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w_px, h_px = img.size
    px_per_mm = w_px / (PAGE_W + 2 * PAD_MM)
    pad_px = int(PAD_MM * px_per_mm)
    alpha = img.split()[-1]

    # Skip a 2px skirt right at the page boundary: the page background
    # rect's own edge antialiases a faint (<= ~25/255) line there, which
    # isn't real content spilling over.
    skirt = 2
    regions = {
        "top": alpha.crop((0, 0, w_px, max(0, pad_px - skirt))),
        "bottom": alpha.crop((0, h_px - pad_px + skirt, w_px, h_px)),
        "left": alpha.crop((0, 0, max(0, pad_px - skirt), h_px)),
        "right": alpha.crop((w_px - pad_px + skirt, 0, w_px, h_px)),
    }
    max_outside = max(region.getextrema()[1] for region in regions.values())
    assert max_outside <= 40, f"{label}: content spills outside the A4 page (max alpha outside = {max_outside})"
