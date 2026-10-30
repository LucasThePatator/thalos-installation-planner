import argparse
import sys
from pathlib import Path

from pdf_export import write_combined_pdf
from sheet_data import DEFAULT_SHEET_URL, SheetFetchError, fetch_rows
from svg_render import render_by_category, render_by_person, render_person_sheet
from tree_builder import assign_category_colors, build_items, sorted_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Thalos installation/rangement A4 flowcharts.")
    parser.add_argument(
        "--csv",
        default=DEFAULT_SHEET_URL,
        help="URL or local path to the sheet CSV export (defaults to the live Google Sheet).",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write the generated SVG files to.",
    )
    args = parser.parse_args()

    try:
        rows = fetch_rows(args.csv)
    except SheetFetchError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    category_colors = assign_category_colors(rows)

    installation_items = build_items(rows, "amene_par", "provenance", category_colors)
    installation_by_provenance_items = build_items(rows, "provenance", "amene_par", category_colors)
    cleanup_items = build_items(rows, "repris_par", "destination", category_colors)
    cleanup_by_destination_items = build_items(rows, "destination", "repris_par", category_colors)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # (output filename, items, title, render function, its extra kwargs).
    # render_by_* can return more than one page when its content would
    # otherwise have to shrink past a readable size — those extra pages
    # become "_2.svg", "_3.svg", ... siblings of the same chart.
    chart_specs = [
        (
            "installation_par_categorie.svg", installation_items,
            "Installation par catégorie — Thalos Halloween 2026", render_by_category,
            {"box_label": "catégorie", "badge_label": "amené par"},
        ),
        (
            "installation_par_personne.svg", installation_items,
            "Installation par personne — Thalos Halloween 2026", render_by_person,
            {"box_label": "personne (amène)"},
        ),
        (
            "installation_par_provenance.svg", installation_by_provenance_items,
            "Installation par provenance — Thalos Halloween 2026", render_by_person,
            {"box_label": "provenance"},
        ),
        (
            "rangement_par_categorie.svg", cleanup_items,
            "Rangement par catégorie — Thalos Halloween 2026", render_by_category,
            {"box_label": "catégorie", "badge_label": "repris par"},
        ),
        (
            "rangement_par_personne.svg", cleanup_items,
            "Rangement par personne — Thalos Halloween 2026", render_by_person,
            {"box_label": "personne (reprend)"},
        ),
        (
            "rangement_par_destination.svg", cleanup_by_destination_items,
            "Rangement par destination — Thalos Halloween 2026", render_by_person,
            {"box_label": "destination", "subgroup_key": "secondary", "badge_label": "repris par"},
        ),
    ]
    charts: dict[str, str] = {}
    for base_filename, items, title, render, kwargs in chart_specs:
        stem, ext = base_filename.rsplit(".", 1)
        pages = render(items, category_colors, title, **kwargs)
        for i, svg in enumerate(pages, start=1):
            filename = base_filename if i == 1 else f"{stem}_{i}.{ext}"
            charts[filename] = svg
    for filename, svg in charts.items():
        (output_dir / filename).write_text(svg, encoding="utf-8")

    pdf_path = output_dir / "thalos_logistique.pdf"
    write_combined_pdf(charts, pdf_path)

    # One big-letter checklist page per "repris par" person, combined into a
    # single PDF so each volunteer's page is easy to print/find inside it.
    # A person with too many items to fit one page gets consecutive pages
    # instead of shrunk-past-legible text.
    persons = sorted_names({item["person"] for item in cleanup_items})
    checklists: dict[str, str] = {}
    for person in persons:
        person_items = [item for item in cleanup_items if item["person"] == person]
        for i, svg in enumerate(render_person_sheet(person, person_items)):
            checklists[f"{person}#{i}"] = svg
    checklists_path = output_dir / "rangement_checklists.pdf"
    write_combined_pdf(checklists, checklists_path)

    print(
        f"{len(rows)} objets — {len(charts)} fichiers A4 + {pdf_path} + "
        f"{checklists_path} ({len(checklists)} pages)"
    )


if __name__ == "__main__":
    main()
