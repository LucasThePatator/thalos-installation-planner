"""Build the flat item list (one entry per object) used by both chart layouts."""

from __future__ import annotations

from operator import attrgetter

from color_utils import hex_to_hls, hls_to_hex
from sheet_data import Row

# Fixed-order categorical palette (dataviz skill reference palette), validated
# with the skill's validate_palette.js for adjacent-pair CVD/normal-vision
# separation in light mode. Past these 8, assign_category_colors shades a
# repeated hue instead of reusing it outright — see _extended_category_color.
CATEGORY_PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#6250d6",  # violet
    "#e34948",  # red
]

NON_RENSEIGNE = "Non renseigné"


def _extended_category_color(base_hex: str, lap: int) -> str:
    """Beyond the validated 8-hue CATEGORY_PALETTE, reuse a hue's angle at a
    shifted lightness rather than repeating the same color outright — every
    node colored this way (a box, a badge) always carries its own visible
    text label too, so this tier doesn't need to clear the same independent
    CVD gate the base 8 do. It only needs to never collide exactly with an
    earlier category's color, which alternating lightness offsets guarantee
    as long as a single hue doesn't need a 5th lap (unlikely for a one-event
    category list)."""
    h, lightness, s = hex_to_hls(base_hex)
    offsets = [0.18, -0.18, 0.30, -0.30]
    offset = offsets[(lap - 1) % len(offsets)]
    new_lightness = min(0.82, max(0.22, lightness + offset))
    return hls_to_hex(h, new_lightness, max(s, 0.35))


def assign_category_colors(rows: list[Row]) -> dict[str, str]:
    categories = sorted({row.categorie for row in rows})
    colors: dict[str, str] = {}
    for index, category in enumerate(categories):
        base_hex = CATEGORY_PALETTE[index % len(CATEGORY_PALETTE)]
        lap = index // len(CATEGORY_PALETTE)
        colors[category] = base_hex if lap == 0 else _extended_category_color(base_hex, lap)
    return colors


def sorted_names(names: set[str]) -> list[str]:
    """Alphabetical, with the "Non renseigné" fallback always pinned last."""
    named = sorted(n for n in names if n != NON_RENSEIGNE)
    return named + ([NON_RENSEIGNE] if NON_RENSEIGNE in names else [])


def build_items(rows: list[Row], person_attr: str, provenance_attr: str, category_colors: dict[str, str]) -> list[dict]:
    get_person = attrgetter(person_attr)
    get_provenance = attrgetter(provenance_attr)
    items = []
    for index, row in enumerate(sorted(rows, key=lambda r: (r.categorie, r.objet))):
        person = get_person(row)
        provenance = get_provenance(row)
        items.append(
            {
                "id": f"obj-{index}",
                "name": row.objet,
                "category": row.categorie,
                "color": category_colors[row.categorie],
                "person": person,
                # The other role field, always present — lets a chart badge
                # or subgroup by it directly (e.g. "repris par" on a chart
                # boxed by destination) instead of only by category.
                "secondary": provenance,
                # Only worth showing as a note if it adds information beyond the person grouping.
                "note": provenance if provenance not in (person, NON_RENSEIGNE) else None,
            }
        )
    return items
