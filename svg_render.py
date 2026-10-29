"""Render a flat item list as a static SVG flowchart, one box per group with
its objects floating inside (sub-grouped once more, no connecting lines),
sized to fit exactly one A4 portrait page."""

from __future__ import annotations

import colorsys
import html
import math

from tree_builder import sorted_names

PAGE_W = 210.0  # A4 portrait, millimetres
PAGE_H = 297.0
MARGIN = 10.0
TITLE_H = 14.0

# A box column needs to stay at least this wide (in the unscaled layout
# space) for the `max_scale` cap in `_solve_scale` to not itself force the
# page below MIN_SCALE — see MIN_SCALE below. Low enough to not bind at
# up to 3 columns; the real minimum legible width is enforced by MIN_SCALE.
BOX_W_MIN = 40.0
COL_GAP = 8.0
BOX_BAR_W = 2.4
# Chrome (headers, badge padding, inter-subgroup/box gaps) measured at ~53%
# of total unscaled layout height on real data — these were trimmed from
# their original, more generous values specifically to claw pages back after
# the chip/badge font floor below made chrome a much bigger share of each
# page than it used to be.
HEADER_H = 6.5
SUB_BADGE_H = 4.6
SUB_BADGE_GAP = 1.8
SUB_GAP = 2.2
SUB_BOX_PAD = 1.0
CHIP_ROW_H = 4.6
CHIP_GAP_X = 4.6
CHIP_GAP_Y = 1.0
CHIP_PAD_X = 8.5
CHIP_RIGHT_PAD = 6.0
CHIP_FONT_SIZE = 3.3
BADGE_FONT_SIZE = 3.3  # equal to CHIP_FONT_SIZE: the smaller of the two drives MIN_SCALE up
TITLE_FONT_SIZE = 4.1
LEGEND_FONT_SIZE = 4.3  # unscaled text (outside the <g scale(...)>), so this is its final printed size
BOX_BOTTOM_PAD = 2.0
BOX_GAP = 3.5

NEUTRAL_BORDER = "#a9a8a2"
NEUTRAL_BADGE = "#8a8a86"
INK = "#0b0b0b"
OBJECT_INK = "#0b0b0b"
NOTE_INK = "#898781"

# Every font-size inside the `<g transform="scale(...)">` is itself multiplied
# by that scale when rendered, so a small base font plus a small scale can
# print well under a legible size. MIN_FONT_PT is the floor; MIN_SCALE is
# derived from it so the smallest scaled font (chip/badge) never prints
# smaller than MIN_FONT_PT, no matter how much content forces the scale down
# — content that doesn't fit at that floor spills onto another page instead
# (see _paginate_boxes / _split_box_by_subgroups).
#
# 12pt (the usual "readable minimum") was tried first and technically works,
# but on the real data it blows up page count 5-6x (105 items, many with
# long French names) and forces most names to truncate. 9pt is a deliberate
# compromise: still clearly larger than the ~4-5pt this rendered at before
# any floor existed, but only ~2-3x the original page count instead of 5-6x.
MIN_FONT_PT = 9
MIN_FONT_MM = MIN_FONT_PT * 25.4 / 72
# Rounded up to the 4 decimal places `_render_page` prints the scale at
# (f"scale({scale:.4f})") and padded slightly beyond that: `_render_page`'s
# own tolerance-free checks compare the *printed* scale's effective font
# size against the floor, so a value that rounds down at print time would
# fail there even though the unrounded scale clears the floor.
MIN_SCALE = math.ceil(MIN_FONT_MM / min(CHIP_FONT_SIZE, BADGE_FONT_SIZE, TITLE_FONT_SIZE) * 1e4 + 1) / 1e4
# Kept close to MIN_SCALE rather than letting content grow toward the old
# 1.5 ceiling: a bigger gap between MIN_SCALE and MAX_SCALE means narrower
# columns on average, which on live data roughly doubles how many item
# names get truncated for not much legibility gain.
MAX_SCALE = MIN_SCALE + 0.1
assert MAX_SCALE >= MIN_SCALE


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, lightness: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


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
    char_w = font_size * 0.68  # both callers render bold titles, which are wider than plain text
    max_chars = max(3, int(max_width_mm / char_w))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _chip_width(label: str) -> float:
    return 3.5 + _text_width(label, CHIP_FONT_SIZE) * 1.18  # bold object name renders wider than the estimate


def _fit_chip_label(name: str, note: str | None, max_chip_w: float) -> tuple[str, str | None]:
    """A chip can't wrap below its own width the way a box's text can reflow
    across rows, so a single very long item name can push a chip wider than
    the box itself — scale/pagination can't fix that. Shrink the displayed
    name/note (dropping the note first, then truncating the name) so the
    chip always fits within one row."""
    if _chip_width(name + (f" · {note}" if note else "")) <= max_chip_w:
        return name, note
    if note and _chip_width(name) <= max_chip_w:
        return name, None
    # Binary search the longest name prefix (plus an ellipsis) whose chip fits.
    lo, hi = 1, len(name)
    best = name[:1]
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = name[:mid].rstrip() + "…"
        if _chip_width(candidate) <= max_chip_w:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best, None


def _layout_chips(items: list[dict], box_w: float, start_y: float, first_row_right_pad: float = 0.0) -> float:
    """Flow items left-to-right, wrapping like tags. `first_row_right_pad`
    reserves room on the opening row only, for a title badge floated at the
    top-right — so the object list starts packed at the very top instead of
    below a separate header line. Returns the content bottom."""
    x = CHIP_PAD_X
    y = start_y
    row = 0
    # The widest a chip could ever need to be and still open a fresh row —
    # used as the hard cap for truncating any single item's displayed label.
    max_chip_w = max(1.0, box_w - CHIP_PAD_X - CHIP_RIGHT_PAD)
    for item in items:
        name, note = _fit_chip_label(item["name"], item.get("note"), max_chip_w)
        item["_display_name"] = name
        item["_display_note"] = note
        label = name + (f" · {note}" if note else "")
        item["_label"] = label
        chip_w = _chip_width(label)
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
        sg["_badge_w"] = 4.6 + _text_width(sg["title"], BADGE_FONT_SIZE) * 1.22  # bold badge text renders wider than the estimate
        content_bottom = _layout_chips(sg["items"], box_w, y, first_row_right_pad=sg["_badge_w"] + 3.0)
        sg["_bottom"] = content_bottom
        last_bottom = content_bottom
        y = content_bottom + SUB_GAP
    box["_h"] = last_bottom + BOX_BOTTOM_PAD


def _fits_in_n_cols(heights: list[float], n_cols: int, cap: float) -> bool:
    """Can `heights` be split into at most `n_cols` contiguous runs, each
    summing to at most `cap`?"""
    count = 1
    running = 0.0
    for h in heights:
        if h > cap:
            return False
        if running + h > cap:
            count += 1
            running = h
        else:
            running += h
    return count <= n_cols


def _split_columns(boxes: list[dict], n_cols: int) -> list[list[dict]]:
    """Split boxes into at most n_cols columns, keeping original order within
    each column, minimizing the tallest column — the classic "partition an
    array into k contiguous parts to minimize the largest part" problem,
    solved by binary-searching the smallest feasible cap and then greedily
    filling columns up to it.

    A sequential "fill until running >= average, then move on" heuristic
    (the previous approach) looks only at boxes already placed, never ahead,
    so one tall box right after a short one can get stuck in the same column
    as the short one even though its own height alone would have balanced
    the page — in the worst case leaving a later column completely empty.
    Binary search avoids that since it only accepts a cap once it's verified
    the whole sequence actually fits in n_cols parts at that height."""
    if not boxes:
        return [[] for _ in range(n_cols)]
    heights = [box["_h"] + BOX_GAP for box in boxes]
    lo, hi = max(heights), sum(heights)
    for _ in range(50):
        if lo >= hi:
            break
        mid = (lo + hi) / 2
        if _fits_in_n_cols(heights, n_cols, mid):
            hi = mid
        else:
            lo = mid
    cap = hi

    columns: list[list[dict]] = []
    current: list[dict] = []
    running = 0.0
    for box, h in zip(boxes, heights):
        if current and running + h > cap:
            columns.append(current)
            current = []
            running = 0.0
        current.append(box)
        running += h
    columns.append(current)
    while len(columns) < n_cols:
        columns.append([])
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


def _solve_scale(boxes: list[dict], n_cols: int, avail_w: float, avail_h: float, max_scale: float) -> tuple[float, float]:
    """Iteratively solve for scale and column width together so the columns
    always fill the full page width — a wider column wraps fewer chip rows,
    which in turn lets the scale grow back towards 1, rather than shrinking
    width and height in lockstep and leaving empty margins on the sides.

    Unlike the old version, the returned scale is NOT clamped to MIN_SCALE:
    a value below MIN_SCALE means this content genuinely doesn't fit on one
    page at a readable size, which callers use to decide whether to spill
    onto another page instead of shrinking text past legibility."""
    # Cap scale so col_w never needs to shrink past BOX_W_MIN to keep filling
    # the width — past that floor, growing the scale further would instead
    # push the box past the page's right edge.
    min_total_w = n_cols * BOX_W_MIN + COL_GAP * (n_cols - 1)
    max_scale = min(max_scale, avail_w / min_total_w) if min_total_w > 0 else max_scale

    scale = 1.0
    total_w = avail_w
    col_w = max(BOX_W_MIN, (total_w - COL_GAP * (n_cols - 1)) / n_cols)
    for _ in range(8):
        _, content_h = _layout_columns(boxes, col_w, n_cols)
        new_scale = min(max_scale, avail_h / content_h) if content_h else max_scale
        new_scale = max(new_scale, 1e-3)  # keep the iteration numerically stable; MIN_SCALE is checked by callers
        if abs(new_scale - scale) < 1e-3:
            scale = new_scale
            break
        scale = new_scale
        total_w = avail_w / scale
        col_w = max(BOX_W_MIN, (total_w - COL_GAP * (n_cols - 1)) / n_cols)

    # The fixed-point search above can oscillate instead of converging —
    # a column width change can flip how many rows a chip list wraps to,
    # which is a discontinuous function of col_w, so the loop can exit on
    # the iteration cap with a `scale` that doesn't actually match the
    # `col_w` being returned. Rather than trust that pairing, independently
    # cap scale by what height AND width actually require for this exact
    # col_w — safe regardless of how col_w was derived, since both
    # content_h * scale <= avail_h and content_w * scale <= avail_w end up
    # guaranteed, instead of relying on the two to have converged together.
    _, content_h = _layout_columns(boxes, col_w, n_cols)
    content_w = n_cols * col_w + COL_GAP * (n_cols - 1)
    scale_h = avail_h / content_h if content_h else max_scale
    scale_w = avail_w / content_w if content_w else max_scale
    scale = max(min(max_scale, scale_h, scale_w), 1e-3)

    return scale, col_w


def _split_box_by_subgroups(box: dict, n_cols: int, avail_w: float, avail_h: float, max_scale: float) -> list[dict]:
    """A box that's too tall even alone (e.g. one category with far more
    people/items than a page can hold at a readable scale) can't be helped
    by box-level pagination, since there's only one of it — split its
    subgroups into several same-titled boxes instead, each one sized to fit
    alone, so later box-level pagination can place them across pages."""
    subgroups = box["subgroups"]
    if not subgroups:
        return [box]
    chunks: list[list[dict]] = []
    current: list[dict] = []
    for sg in subgroups:
        candidate = current + [sg]
        probe = {"title": box["title"], "border_color": box["border_color"], "subgroups": candidate}
        scale, _ = _solve_scale([probe], n_cols, avail_w, avail_h, max_scale)
        if scale >= MIN_SCALE or not current:
            current = candidate
        else:
            chunks.append(current)
            current = [sg]
    chunks.append(current)
    if len(chunks) == 1:
        return [box]
    total = len(chunks)
    return [
        {"title": f'{box["title"]} ({i}/{total})', "border_color": box["border_color"], "subgroups": chunk}
        for i, chunk in enumerate(chunks, start=1)
    ]


def _paginate_boxes(boxes: list[dict], n_cols: int, avail_w: float, avail_h: float, max_scale: float) -> list[list[dict]]:
    """Greedily split boxes across pages so no single page needs to shrink
    its content below MIN_SCALE to fit — once adding the next box would
    force that, it starts a new page instead, so overflow becomes another
    sheet of the same chart rather than unreadable text."""
    if not boxes:
        return [[]]
    expanded: list[dict] = []
    for box in boxes:
        expanded.extend(_split_box_by_subgroups(box, n_cols, avail_w, avail_h, max_scale))
    pages: list[list[dict]] = []
    current: list[dict] = []
    for box in expanded:
        candidate = current + [box]
        scale, _ = _solve_scale(candidate, n_cols, avail_w, avail_h, max_scale)
        if scale >= MIN_SCALE or not current:
            current = candidate
        else:
            pages.append(current)
            current = [box]
    pages.append(current)
    return pages


def _render_page(boxes: list[dict], title: str | None, n_cols: int, max_scale: float, box_chrome: bool, legend: str | None = None) -> str:
    avail_w = PAGE_W - 2 * MARGIN
    title_h = TITLE_H if title else 0.0
    avail_h = PAGE_H - 2 * MARGIN - title_h

    # No MIN_SCALE floor here: pagination (_paginate_boxes / _split_box_by_subgroups)
    # is responsible for keeping every page's content above MIN_SCALE wherever a
    # split is possible. The one case that can still land below it — a single
    # subgroup too big to fit alone, forced onto its own page by the
    # `or not current` fallback — must shrink further rather than be clamped and
    # pushed off the page; staying inside the sheet takes priority over staying
    # above the readability floor.
    scale, col_w = _solve_scale(boxes, n_cols, avail_w, avail_h, max_scale)

    box_w = col_w
    content_w = n_cols * col_w + COL_GAP * (n_cols - 1)
    offset_x = MARGIN + max(0.0, (avail_w - content_w * scale) / 2)
    offset_y = MARGIN + title_h

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
        f'viewBox="0 0 {PAGE_W} {PAGE_H}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{PAGE_W}" height="{PAGE_H}" fill="#fcfcfb"/>')
    if title:
        parts.append(f'<text x="{MARGIN}" y="{MARGIN + 5}" font-size="5.6" font-weight="700" fill="{INK}">{_esc(title)}</text>')
        if legend:
            # Clarifies what the box titles and subgroup badges below actually
            # represent (e.g. "amené par" vs "provenance") — without it, two
            # charts with the same box/badge shapes but different grouping
            # keys are visually indistinguishable except for the main title.
            parts.append(f'<text x="{MARGIN}" y="{MARGIN + 10.5}" font-size="{LEGEND_FONT_SIZE}" fill="{NOTE_INK}">{_esc(legend)}</text>')

    parts.append(f'<g transform="translate({offset_x:.2f},{offset_y:.2f}) scale({scale:.4f})">')

    for box in boxes:
        x, y0, h = box["_x"], box["_y"], box["_h"]
        if box_chrome:
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
        else:
            # No frame — the name is just a plain page heading, category
            # clusters float directly on the page underneath it.
            box_title = _fit_text(box["title"], box_w, TITLE_FONT_SIZE * 1.5)
            parts.append(
                f'<text x="{x:.2f}" y="{y0 + HEADER_H / 2 + 1.6:.2f}" font-size="{TITLE_FONT_SIZE * 1.5}" font-weight="700" fill="{INK}">{_esc(box_title)}</text>'
            )

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
                display_name = item.get("_display_name", item["name"])
                display_note = item.get("_display_note", item.get("note"))
                note = f" · {display_note}" if display_note else ""
                parts.append(
                    f'<text x="{lx + 2.7:.2f}" y="{ly + 1.1:.2f}" font-size="{CHIP_FONT_SIZE}">'
                    f'<tspan font-weight="600" fill="{OBJECT_INK}">{_esc(display_name)}</tspan>'
                    + (f'<tspan fill="{NOTE_INK}">{_esc(note)}</tspan>' if note else "")
                    + "</text>"
                )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def _render(boxes: list[dict], title: str | None, n_cols: int = 2, max_scale: float = MAX_SCALE, box_chrome: bool = True, legend: str | None = None) -> list[str]:
    """Paginate boxes across as many A4 pages as needed and render each one.
    Returns one SVG string per page; callers get a single page back in the
    common case, more only when content would otherwise spill past MIN_SCALE."""
    avail_w = PAGE_W - 2 * MARGIN
    title_h = TITLE_H if title else 0.0
    avail_h = PAGE_H - 2 * MARGIN - title_h

    pages_of_boxes = _paginate_boxes(boxes, n_cols, avail_w, avail_h, max_scale)
    total = len(pages_of_boxes)
    svgs = []
    for i, page_boxes in enumerate(pages_of_boxes, start=1):
        page_title = f"{title} ({i}/{total})" if title and total > 1 else title
        svgs.append(_render_page(page_boxes, page_title, n_cols, max_scale, box_chrome, legend))
    return svgs


def render_by_category(
    items: list[dict], category_colors: dict[str, str], title: str, *, box_label: str, badge_label: str
) -> list[str]:
    """`box_label`/`badge_label` name what each box and each subgroup badge
    actually groups by (e.g. "catégorie" / "amené par") — shown as a small
    legend under the title so the badges aren't ambiguous between charts."""
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
    legend = f"Cases = {box_label} · Étiquettes = {badge_label}"
    return _render(boxes, title, n_cols=2 if len(boxes) >= 3 else 1, legend=legend)


def render_by_person(
    items: list[dict],
    category_colors: dict[str, str],
    title: str,
    *,
    box_label: str,
    subgroup_key: str = "category",
    badge_label: str = "catégorie",
) -> list[str]:
    """`box_label` names what each box groups by (e.g. "personne (amène)" or
    "provenance"). Subgroup badges group by `subgroup_key` within each box —
    "category" (the default) colors each badge by its category, since that's
    inherently meaningful; any other key (e.g. "secondary", to badge by the
    other role field such as "repris par") has no such inherent color, so it
    falls back to a neutral badge color instead of implying a false category
    meaning. `badge_label` names that dimension for the legend."""
    persons = sorted_names({item["person"] for item in items})
    boxes = []
    for person in persons:
        person_items = [item for item in items if item["person"] == person]
        if not person_items:
            continue
        if subgroup_key == "category":
            subgroups = _build_subgroups(person_items, "category", dot_color=lambda it: it["color"])
        else:
            # The badge already shows this dimension — repeating it as a
            # per-item note underneath would just restate the badge text on
            # every single chip, so drop the note on these copies.
            deduped_items = [dict(it, note=None) for it in person_items]
            subgroups = _build_subgroups(deduped_items, subgroup_key, dot_color=None)
        boxes.append(
            {
                "title": person,
                "border_color": NEUTRAL_BORDER,
                "subgroups": subgroups,
            }
        )
    legend = f"Cases = {box_label} · Étiquettes = {badge_label}"
    return _render(boxes, title, n_cols=2 if len(boxes) >= 3 else 1, legend=legend)


def render_person_sheet(person_name: str, person_items: list[dict]) -> list[str]:
    """One person, one page, big letters — a personal checklist rather than
    the dense all-in-one overview. Categorized, no column split (one person
    never needs it), and allowed to scale up much further since it's the
    only content on the page. No small top title and no outer frame — just
    the person's name as a plain heading with category clusters below it.

    If one person's items don't fit on a single page at a readable scale,
    their categories spill onto additional pages instead of being shrunk
    past legibility, each page's heading marked with its page number."""
    max_scale = 3.0
    avail_w = PAGE_W - 2 * MARGIN
    avail_h = PAGE_H - 2 * MARGIN  # no top title bar on person sheets

    box = {
        "title": person_name,
        "border_color": NEUTRAL_BORDER,
        "subgroups": _build_subgroups(person_items, "category", dot_color=lambda it: it["color"]),
    }
    pages = _split_box_by_subgroups(box, 1, avail_w, avail_h, max_scale)
    return [_render_page([page_box], None, n_cols=1, max_scale=max_scale, box_chrome=False) for page_box in pages]
