"""Small shared hex<->HLS helpers, used by both tree_builder (category color
assignment) and svg_render (badge/sub-box lightness shading)."""

from __future__ import annotations

import colorsys


def hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def hls_to_hex(h: float, lightness: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
