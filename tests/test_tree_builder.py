from sheet_data import NON_RENSEIGNE, Row
from tree_builder import CATEGORY_PALETTE, assign_category_colors, build_items, sorted_names


def _row(**overrides) -> Row:
    defaults = {
        "objet": "Chaise",
        "categorie": "Mobilier",
        "provenance": "Local",
        "amene_par": "Alice",
        "repris_par": "Bob",
        "destination": "Cube",
    }
    defaults.update(overrides)
    return Row(**defaults)


def test_sorted_names_alphabetical_with_non_renseigne_pinned_last():
    names = {"Zoe", "Alice", NON_RENSEIGNE, "Bob"}

    assert sorted_names(names) == ["Alice", "Bob", "Zoe", NON_RENSEIGNE]


def test_sorted_names_omits_non_renseigne_when_absent():
    assert sorted_names({"Zoe", "Alice"}) == ["Alice", "Zoe"]


def test_assign_category_colors_stable_and_unique_past_palette_size():
    """Regression guard: a sheet with more categories than CATEGORY_PALETTE
    entries used to wrap around and hand two different categories the exact
    same color (e.g. with 9 categories and an 8-color palette, the 9th was
    pixel-identical to the 1st) — every category must get its own color."""
    categories = [f"Cat{i}" for i in range(2 * len(CATEGORY_PALETTE) + 2)]
    rows = [_row(categorie=c) for c in categories]

    colors = assign_category_colors(rows)

    assert len(colors) == len(categories)
    sorted_categories = sorted(categories)
    assert colors[sorted_categories[0]] == CATEGORY_PALETTE[0]
    assert len(set(colors.values())) == len(categories), "two categories got the same color"


def test_build_items_maps_person_and_category():
    rows = [_row(categorie="Mobilier", amene_par="Alice", provenance="Local")]
    colors = assign_category_colors(rows)

    items = build_items(rows, "amene_par", "provenance", colors)

    assert len(items) == 1
    item = items[0]
    assert item["name"] == "Chaise"
    assert item["category"] == "Mobilier"
    assert item["person"] == "Alice"
    assert item["color"] == colors["Mobilier"]


def test_build_items_note_hidden_when_it_duplicates_person():
    # provenance == amene_par here: showing it again as a note would be redundant.
    rows = [_row(amene_par="Alice", provenance="Alice")]
    colors = assign_category_colors(rows)

    items = build_items(rows, "amene_par", "provenance", colors)

    assert items[0]["note"] is None


def test_build_items_note_hidden_when_non_renseigne():
    rows = [_row(amene_par="Alice", provenance=NON_RENSEIGNE)]
    colors = assign_category_colors(rows)

    items = build_items(rows, "amene_par", "provenance", colors)

    assert items[0]["note"] is None


def test_build_items_note_shown_when_it_adds_information():
    rows = [_row(amene_par="Alice", provenance="Local")]
    colors = assign_category_colors(rows)

    items = build_items(rows, "amene_par", "provenance", colors)

    assert items[0]["note"] == "Local"
