from pathlib import Path

from pypdf import PdfReader

from pdf_export import write_combined_pdf

_SVG_A = '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297"><rect width="210" height="297" fill="#fff"/></svg>'
_SVG_B = '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297"><rect width="210" height="297" fill="#eee"/></svg>'


def test_write_combined_pdf_produces_one_page_per_svg(tmp_path: Path):
    output_path = tmp_path / "combined.pdf"

    write_combined_pdf({"a.svg": _SVG_A, "b.svg": _SVG_B}, output_path)

    assert output_path.exists()
    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 2


def test_write_combined_pdf_creates_parent_directories(tmp_path: Path):
    output_path = tmp_path / "nested" / "dir" / "combined.pdf"

    write_combined_pdf({"a.svg": _SVG_A}, output_path)

    assert output_path.exists()
