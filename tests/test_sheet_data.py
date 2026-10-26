from pathlib import Path

import pytest

from sheet_data import NON_RENSEIGNE, Row, SheetFetchError, fetch_rows

FIXTURES = Path(__file__).parent / "fixtures"


def test_fetch_rows_parses_expected_rows():
    rows = fetch_rows(str(FIXTURES / "sample.csv"))

    assert rows == [
        Row(
            objet="Tables x3",
            categorie="Figurines",
            provenance="Castagora",
            amene_par="David (Mac)",
            repris_par="David (Mac)",
            destination="Cube",
        ),
        Row(
            objet="Boisson",
            categorie="Buvette",
            provenance=NON_RENSEIGNE,
            amene_par="Lucas",
            repris_par="Lucas",
            destination=NON_RENSEIGNE,
        ),
    ]


def test_fetch_rows_skips_blank_objet_row(capsys):
    rows = fetch_rows(str(FIXTURES / "sample.csv"))

    assert len(rows) == 2  # the 3rd fixture row has a blank Objet
    assert "1 ligne" in capsys.readouterr().out


def test_fetch_rows_blank_cell_becomes_non_renseigne():
    rows = fetch_rows(str(FIXTURES / "sample.csv"))

    assert rows[1].provenance == NON_RENSEIGNE
    assert rows[1].destination == NON_RENSEIGNE


def test_fetch_rows_raises_on_missing_column():
    with pytest.raises(SheetFetchError, match="Destination de stockage"):
        fetch_rows(str(FIXTURES / "missing_column.csv"))


def test_fetch_rows_raises_on_html_response_instead_of_csv():
    with pytest.raises(SheetFetchError, match="HTML"):
        fetch_rows(str(FIXTURES / "html_login_page.csv"))


def test_fetch_rows_raises_clear_error_on_missing_file():
    with pytest.raises(SheetFetchError, match="Impossible de lire"):
        fetch_rows("/nonexistent/path/does-not-exist.csv")
