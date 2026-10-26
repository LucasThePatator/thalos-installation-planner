from conftest import assert_fits_a4

from svg_render import render_by_category, render_by_person, render_person_sheet


def _items(n_persons: int, n_per_person: int, *, category: str = "Deco", color: str = "#e06666") -> list[dict]:
    return [
        {
            "category": category,
            "person": f"PersonneAvecUnNomAssezLong{p:03d}",
            "name": f"ObjetAssezLong{o}",
            "note": "une note",
            "color": color,
        }
        for p in range(n_persons)
        for o in range(n_per_person)
    ]


def test_normal_sized_chart_stays_one_page():
    """Regression guard: a handful of items shouldn't trigger pagination —
    only genuine overflow should add pages."""
    items = _items(n_persons=3, n_per_person=2)
    category_colors = {"Deco": "#e06666"}

    pages = render_by_category(items, category_colors, "Test", box_label="catégorie", badge_label="amené par")

    assert len(pages) == 1
    assert_fits_a4(pages[0], "normal category chart")


def test_oversized_category_paginates_across_boxes():
    """One category with far more people than a page can hold at a readable
    scale must split into box-level pages instead of shrinking unreadably."""
    items = _items(n_persons=120, n_per_person=8)
    category_colors = {"Deco": "#e06666"}

    pages = render_by_category(items, category_colors, "Stress test", box_label="catégorie", badge_label="amené par")

    assert len(pages) > 1
    for i, svg in enumerate(pages):
        assert_fits_a4(svg, f"oversized category page {i}")


def test_oversized_person_paginates_across_subgroups():
    """A single person with far more categories than one page can hold must
    split by subgroup (category) — the box-level split alone can't help
    since there's only one box."""
    person_items = [
        {
            "category": f"CategorieAssezLongueNumero{c:03d}",
            "person": "Solo",
            "name": f"ItemAssezLong{o}",
            "note": "une note",
            "color": "#333333",
        }
        for c in range(60)
        for o in range(8)
    ]

    pages = render_person_sheet("Solo", person_items)

    assert len(pages) > 1
    for i, svg in enumerate(pages):
        assert_fits_a4(svg, f"oversized person-sheet page {i}")


def test_multi_column_layout_fits():
    many_cats = {f"Cat{c}": "#336699" for c in range(5)}
    items = [
        {"category": cat, "person": f"PersonneLongue{p:03d}", "name": "ObjetLong", "note": "note", "color": "#336699"}
        for cat in many_cats
        for p in range(30)
    ]

    pages = render_by_category(items, many_cats, "Multi-col stress", box_label="catégorie", badge_label="amené par")

    for i, svg in enumerate(pages):
        assert_fits_a4(svg, f"multi-column page {i}")


def test_single_item_with_very_long_name_does_not_overflow_its_chip():
    """Regression test for a real bug found against live data: a single item
    whose name is long enough to make its own chip wider than the box can't
    be helped by pagination at all — the chip itself must be truncated."""
    long_name = (
        "Un nom d'objet absurdement long pour tester la troncature des puces "
        "individuelles vraiment tres long"
    )
    person_items = [{"category": "Point Info", "person": "X", "name": long_name, "note": None, "color": "#000000"}]

    pages = render_person_sheet("X", person_items)

    assert len(pages) == 1
    assert_fits_a4(pages[0], "long chip name")


def test_render_by_person_fits():
    items = _items(n_persons=3, n_per_person=2)
    category_colors = {"Deco": "#e06666"}

    pages = render_by_person(items, category_colors, "Test", box_label="personne (amène)")

    for i, svg in enumerate(pages):
        assert_fits_a4(svg, f"render_by_person page {i}")


def test_render_by_person_can_badge_by_a_non_category_field():
    """E.g. a chart boxed by destination, badged by "repris par" instead of
    category — the badge dimension and the box dimension are independent."""
    items = [
        {"category": "Deco", "person": "Cube", "name": "Lampe", "note": None, "color": "#e06666", "secondary": "Alice"},
        {"category": "Buvette", "person": "Cube", "name": "Verre", "note": None, "color": "#1baf7a", "secondary": "Bob"},
    ]
    category_colors = {"Deco": "#e06666", "Buvette": "#1baf7a"}

    pages = render_by_person(
        items, category_colors, "Test", box_label="destination", subgroup_key="secondary", badge_label="repris par"
    )

    assert len(pages) == 1
    assert "Étiquettes = repris par" in pages[0]
    assert "Alice" in pages[0]
    assert "Bob" in pages[0]
    assert_fits_a4(pages[0], "badge-by-secondary page")
