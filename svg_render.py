"""Render a flat item list as a static SVG flowchart, one box per group with
its objects floating inside (sub-grouped once more, no connecting lines),
sized to fit exactly one A4 portrait page."""

from __future__ import annotations

import colorsys
import html

from tree_builder import sorted_names

PAGE_W = 210.0  # A4 portrait, millimetres
PAGE_H = 297.0
MARGIN = 10.0
TITLE_H = 12.0

BOX_W_MIN = 70.0
COL_GAP = 8.0
BOX_BAR_W = 2.4
HEADER_H = 8.0
SUB_BADGE_H = 4.6
SUB_BADGE_GAP = 1.8
SUB_GAP = 3.8
SUB_BOX_PAD = 1.4
CHIP_ROW_H = 5.0
CHIP_GAP_X = 4.6
CHIP_GAP_Y = 1.5
CHIP_PAD_X = 8.5
CHIP_RIGHT_PAD = 6.0
CHIP_FONT_SIZE = 3.3
BADGE_FONT_SIZE = 3.0
TITLE_FONT_SIZE = 4.1
BOX_BOTTOM_PAD = 3.5
BOX_GAP = 6.0

NEUTRAL_BORDER = "#a9a8a2"
NEUTRAL_BADGE = "#8a8a86"
INK = "#0b0b0b"
OBJECT_INK = "#0b0b0b"
NOTE_INK = "#898781"

MIN_SCALE, MAX_SCALE = 0.35, 1.5


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, lightness: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _generate_shades(base_hex: str, count: int) -> list[str]:
    """Same hue/saturation as base_hex, stepped lightness — a sequential
    single-hue ramp so sibling sub-boxes read as "the same tone, subtly
    different" rather than arbitrary unrelated colors."""
    h, _, s = _hex_to_hls(base_hex)
    s = max(s, 0.35)
    if count <= 1:
        return [_hls_to_hex(h, 0.34, s)]
    lo, hi = 0.26, 0.46
    return [_hls_to_hex(h, lo + (hi - lo) * i / (count - 1), s) for i in range(count)]


def _readable_text_color(hex_color: str, max_l: float = 0.42) -> str:
    """Darken a hue just enough to stay legible as solid text on a near-white
    background — some categorical hues (yellow, aqua, magenta) are too light
    to read reliably otherwise."""
    h, lightness, s = _hex_to_hls(hex_color)
    return _hls_to_hex(h, min(lightness, max_l), s) if lightness > max_l else hex_color


def _text_width(text: str, font_size: float) -> float:
    return len(text) * font_size * 0.56


def _fit_text(text: str, max_width_mm: float, font_size: float) -> str:
    char_w = font_size * 0.56
    max_chars = max(3, int(max_width_mm / char_w))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _layout_chips(items: list[dict], box_w: float, start_y: float, first_row_right_pad: float = 0.0) -> float:
    """Flow items left-to-right, wrapping like tags. `first_row_right_pad`
    reserves room on the opening row only, for a title badge floated at the
    top-right — so the object list starts packed at the very top instead of
    below a separate header line. Returns the content bottom."""
    x = CHIP_PAD_X
    y = start_y
    row = 0
    for item in items:
        label = item["name"] + (f" · {item['note']}" if item.get("note") else "")
        item["_label"] = label
        chip_w = 3.5 + _text_width(label, CHIP_FONT_SIZE) * 1.18  # bold object name renders wider than the estimate
        right_pad = CHIP_RIGHT_PAD + (first_row_right_pad if row == 0 else 0.0)
        # On the badge row, even the first chip must wrap away if it doesn't
        # fit beside the badge (row 1+ has the full width, so it fits there).
        if x + chip_w > box_w - right_pad and (x > CHIP_PAD_X or row == 0):
            x = CHIP_PAD_X
            y += CHIP_ROW_H + CHIP_GAP_Y
            row += 1
        item["_lx"] = x
        item["_ly"] = y + CHIP_ROW_H / 2
        x += chip_w + CHIP_GAP_X
    return y + CHIP_ROW_H


def _build_subgroups(items: list[dict], key: str, dot_color) -> list[dict]:
    names = sorted_names({item[key] for item in items})
    groups = []
    for name in names:
        group_items = [item for item in items if item[key] == name]
        groups.append(
            {
                "title": name,
                "dot_color": dot_color(group_items[0]) if dot_color else None,
                "items": group_items,
            }
        )
    return groups


def _layout_box(box: dict, box_w: float) -> None:
    y = HEADER_H + 1.8
    last_bottom = y
    for sg in box["subgroups"]:
        sg["_y"] = y
        sg["_badge_w"] = 4.2 + _text_width(sg["title"], BADGE_FONT_SIZE)
        content_bottom = _layout_chips(sg["items"], box_w, y, first_row_right_pad=sg["_badge_w"] + 3.0)
        sg["_bottom"] = content_bottom
        last_bottom = content_bottom
        y = content_bottom + SUB_GAP
    box["_h"] = last_bottom + BOX_BOTTOM_PAD


def _split_columns(boxes: list[dict], n_cols: int) -> list[list[dict]]:
    """Split boxes into n_cols columns, keeping original order within each
    column, breaking as close to an even height split as possible — a
    simple sequential masonry rather than a full bin-pack, so related boxes
    stay easy to scan top-to-bottom instead of jumping between columns."""
    total_h = sum(box["_h"] + BOX_GAP for box in boxes)
    target = total_h / n_cols
    columns: list[list[dict]] = [[] for _ in range(n_cols)]
    col_idx = 0
    running = 0.0
    for box in boxes:
        if col_idx < n_cols - 1 and running >= target and columns[col_idx]:
            col_idx += 1
            running = 0.0
        columns[col_idx].append(box)
        running += box["_h"] + BOX_GAP
    return columns


def _layout_columns(boxes: list[dict], col_w: float, n_cols: int) -> tuple[list[list[dict]], float]:
    for box in boxes:
        _layout_box(box, col_w)
    columns = _split_columns(boxes, n_cols)
    max_h = 0.0
    for col_i, column in enumerate(columns):
        cy = 0.0
        for box in column:
            box["_x"] = col_i * (col_w + COL_GAP)
            box["_y"] = cy
            cy += box["_h"] + BOX_GAP
        max_h = max(max_h, max(0.0, cy - BOX_GAP))
    return columns, max_h


def _render(boxes: list[dict], title: str, n_cols: int = 2) -> str:
    avail_w = PAGE_W - 2 * MARGIN
    avail_h = PAGE_H - 2 * MARGIN - TITLE_H

    # Solve for scale and column width together so the columns always fill
    # the full page width — a wider column wraps fewer chip rows, which in
    # turn lets the scale grow back towards 1, rather than shrinking width
    # and height in lockstep and leaving empty margins on the sides.
    scale = 1.0
    total_w = avail_w
    col_w = max(BOX_W_MIN, (total_w - COL_GAP * (n_cols - 1)) / n_cols)
    for _ in range(8):
        _, content_h = _layout_columns(boxes, col_w, n_cols)
        new_scale = max(MIN_SCALE, min(MAX_SCALE, avail_h / content_h if content_h else MAX_SCALE))
        if abs(new_scale - scale) < 1e-3:
            scale = new_scale
            break
        scale = new_scale
        total_w = avail_w / scale
        col_w = max(BOX_W_MIN, (total_w - COL_GAP * (n_cols - 1)) / n_cols)
    else:
        _layout_columns(boxes, col_w, n_cols)

    box_w = col_w
    content_w = n_cols * col_w + COL_GAP * (n_cols - 1)
    offset_x = MARGIN + max(0.0, (avail_w - content_w * scale) / 2)
    offset_y = MARGIN + TITLE_H

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
        f'viewBox="0 0 {PAGE_W} {PAGE_H}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{PAGE_W}" height="{PAGE_H}" fill="#fcfcfb"/>')
    parts.append(f'<text x="{MARGIN}" y="{MARGIN + 5}" font-size="5.6" font-weight="700" fill="{INK}">{_esc(title)}</text>')

    parts.append(f'<g transform="translate({offset_x:.2f},{offset_y:.2f}) scale({scale:.4f})">')

    for box in boxes:
        x, y0, h = box["_x"], box["_y"], box["_h"]
        parts.append(
            f'<rect x="{x:.2f}" y="{y0:.2f}" width="{box_w:.2f}" height="{h:.2f}" rx="3.5" '
            f'fill="{box["border_color"]}" fill-opacity="0.035" stroke="{box["border_color"]}" stroke-opacity="0.6" stroke-width="0.45"/>'
        )
        # Left accent bar identifies the box's own group (category or person) —
        # visually distinct from the badges (subgroup) and dots (object) below.
        parts.append(
            f'<rect x="{x + 1.3:.2f}" y="{y0 + 1.3:.2f}" width="{BOX_BAR_W}" height="{h - 2.6:.2f}" rx="1.1" fill="{box["border_color"]}" fill-opacity="0.85"/>'
        )
        box_title = _fit_text(box["title"], box_w - 16, TITLE_FONT_SIZE)
        parts.append(
            f'<text x="{x + 6.5:.2f}" y="{y0 + HEADER_H / 2 + 1.1:.2f}" font-size="{TITLE_FONT_SIZE}" font-weight="700" fill="{INK}">{_esc(box_title)}</text>'
        )
        parts.append(f'<line x1="{x + 3:.2f}" x2="{x + box_w - 3:.2f}" y1="{y0 + HEADER_H:.2f}" y2="{y0 + HEADER_H:.2f}" stroke="{box["border_color"]}" stroke-opacity="0.25" stroke-width="0.3"/>')

        for sg in box["subgroups"]:
            sy = y0 + sg["_y"]
            badge_color = sg["dot_color"] or NEUTRAL_BADGE
            # A very faint box ties the person/category badge to the objects
            # underneath it as one visual cluster.
            group_top = sy - SUB_BOX_PAD
            group_bottom = y0 + sg["_bottom"] + SUB_BOX_PAD
            parts.append(
                f'<rect x="{x + 3.5:.2f}" y="{group_top:.2f}" width="{box_w - 7:.2f}" height="{group_bottom - group_top:.2f}" rx="2" '
                f'fill="{badge_color}" fill-opacity="0.025" stroke="{badge_color}" stroke-opacity="0.22" stroke-width="0.28"/>'
            )
            badge_x = x + box_w - CHIP_RIGHT_PAD - sg["_badge_w"]
            badge_y = sy + (CHIP_ROW_H - SUB_BADGE_H) / 2
            parts.append(
                f'<rect x="{badge_x:.2f}" y="{badge_y:.2f}" width="{sg["_badge_w"]:.2f}" height="{SUB_BADGE_H}" rx="1.5" '
                f'fill="{badge_color}" fill-opacity="0.16" stroke="{badge_color}" stroke-opacity="0.7" stroke-width="0.3"/>'
            )
            parts.append(
                f'<text x="{badge_x + 2.1:.2f}" y="{badge_y + SUB_BADGE_H / 2 + 1.0:.2f}" font-size="{BADGE_FONT_SIZE}" font-weight="700" fill="{_readable_text_color(badge_color)}">{_esc(sg["title"])}</text>'
            )
            for item in sg["items"]:
                lx, ly = x + item["_lx"], y0 + item["_ly"]
                parts.append(f'<circle cx="{lx:.2f}" cy="{ly:.2f}" r="1.1" fill="{item["color"]}"/>')
                note = f" · {item['note']}" if item.get("note") else ""
                parts.append(
                    f'<text x="{lx + 2.7:.2f}" y="{ly + 1.1:.2f}" font-size="{CHIP_FONT_SIZE}">'
                    f'<tspan font-weight="600" fill="{OBJECT_INK}">{_esc(item["name"])}</tspan>'
                    + (f'<tspan fill="{NOTE_INK}">{_esc(note)}</tspan>' if note else "")
                    + "</text>"
                )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_by_category(items: list[dict], category_colors: dict[str, str], title: str) -> str:
    categories = sorted(category_colors)
    boxes = []
    for cat in categories:
        cat_items = [item for item in items if item["category"] == cat]
        if not cat_items:
            continue
        subgroups = _build_subgroups(cat_items, "person", dot_color=None)
        shades = _generate_shades(category_colors[cat], len(subgroups))
        for sg, shade in zip(subgroups, shades):
            sg["dot_color"] = shade
        boxes.append(
            {
                "title": cat,
                "border_color": category_colors[cat],
                "subgroups": subgroups,
            }
        )
    return _render(boxes, title, n_cols=2 if len(boxes) >= 3 else 1)


def render_by_person(items: list[dict], category_colors: dict[str, str], title: str) -> str:
    persons = sorted_names({item["person"] for item in items})
    boxes = []
    for person in persons:
        person_items = [item for item in items if item["person"] == person]
        if not person_items:
            continue
        boxes.append(
            {
                "title": person,
                "border_color": NEUTRAL_BORDER,
                "subgroups": _build_subgroups(person_items, "category", dot_color=lambda it: it["color"]),
            }
        )
    return _render(boxes, title, n_cols=2 if len(boxes) >= 3 else 1)
