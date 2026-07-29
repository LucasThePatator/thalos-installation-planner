"""Combine the generated A4 SVG charts into a single multi-page PDF."""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from pypdf import PdfWriter


def write_combined_pdf(svg_by_filename: dict[str, str], output_path: Path) -> None:
    writer = PdfWriter()
    for svg in svg_by_filename.values():
        pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
        writer.append(io.BytesIO(pdf_bytes))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)
