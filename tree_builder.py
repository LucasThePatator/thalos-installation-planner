"""Build the flat item list (one entry per object) used by both chart layouts."""

from __future__ import annotations

from operator import attrgetter

from sheet_data import Row

# Fixed-order categorical palette (dataviz skill reference palette, validated
# for adjacent-pair CVD/normal-vision separation). Slot 9 is an explicit
# extension for when the sheet has more than 8 categories; every node using it
# is always paired with a visible text label, so it doesn't need to pass the
# same CVD gate as the validated 8.
CATEGORY_PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
    "#8a5a3c",  # brown (extension slot, 9th+ category)
]

NON_RENSEIGNE = "Non renseigné"


def assign_category_colors(rows: list[Row]) -> dict[str, str]:
    categories = sorted({row.categorie for row in rows})
    return {
        category: CATEGORY_PALETTE[index % len(CATEGORY_PALETTE)]
        for index, category in enumerate(categories)
    }


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
