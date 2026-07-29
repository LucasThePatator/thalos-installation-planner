import argparse
from pathlib import Path

from pdf_export import write_combined_pdf
from sheet_data import DEFAULT_SHEET_URL, fetch_rows
from svg_render import render_by_category, render_by_person
from tree_builder import assign_category_colors, build_items


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

    rows = fetch_rows(args.csv)
    category_colors = assign_category_colors(rows)

    installation_items = build_items(rows, "amene_par", "provenance", category_colors)
    installation_by_provenance_items = build_items(rows, "provenance", "amene_par", category_colors)
    cleanup_items = build_items(rows, "repris_par", "destination", category_colors)
    cleanup_by_destination_items = build_items(rows, "destination", "repris_par", category_colors)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    charts = {
        "installation_par_categorie.svg": render_by_category(
            installation_items, category_colors, "Installation par catégorie — Thalos Halloween 2026"
        ),
        "installation_par_personne.svg": render_by_person(
            installation_items, category_colors, "Installation par personne — Thalos Halloween 2026"
        ),
        "installation_par_provenance.svg": render_by_person(
            installation_by_provenance_items, category_colors, "Installation par provenance — Thalos Halloween 2026"
        ),
        "rangement_par_categorie.svg": render_by_category(
            cleanup_items, category_colors, "Rangement par catégorie — Thalos Halloween 2026"
        ),
        "rangement_par_personne.svg": render_by_person(
            cleanup_items, category_colors, "Rangement par personne — Thalos Halloween 2026"
        ),
        "rangement_par_destination.svg": render_by_person(
            cleanup_by_destination_items, category_colors, "Rangement par destination — Thalos Halloween 2026"
        ),
    }
    for filename, svg in charts.items():
        (output_dir / filename).write_text(svg, encoding="utf-8")

    pdf_path = output_dir / "thalos_planning.pdf"
    write_combined_pdf(charts, pdf_path)

    print(f"{len(rows)} objets — {len(charts)} fichiers A4 + {pdf_path} écrits dans {output_dir}/")


if __name__ == "__main__":
    main()
