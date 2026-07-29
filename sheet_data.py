"""Fetch and parse the Thalos installation-planning Google Sheet."""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1GBzIrW-1pkUjUGPe0fx344l_zYtaQugbRDKMMaWiyrg/export?format=csv&gid=261909291"
)

NON_RENSEIGNE = "Non renseigné"


@dataclass(frozen=True)
class Row:
    objet: str
    categorie: str
    provenance: str
    amene_par: str
    repris_par: str
    destination: str


def _clean(value: str | None) -> str:
    value = (value or "").strip()
    return value or NON_RENSEIGNE


def _read_csv_text(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as response:  # noqa: S310 (trusted sheet export URL)
            return response.read().decode("utf-8-sig")
    with open(source, encoding="utf-8-sig") as handle:
        return handle.read()


def fetch_rows(source: str = DEFAULT_SHEET_URL) -> list[Row]:
    """Fetch the sheet (from a URL or a local CSV path) and parse it into Rows."""
    text = _read_csv_text(source)
    reader = csv.DictReader(io.StringIO(text))
    rows: list[Row] = []
    for record in reader:
        objet = (record.get("Objet") or "").strip()
        if not objet:
            continue
        rows.append(
            Row(
                objet=objet,
                categorie=_clean(record.get("Catégorie")),
                provenance=_clean(record.get("Provenance")),
                amene_par=_clean(record.get("Amené par")),
                repris_par=_clean(record.get("Repris par")),
                destination=_clean(record.get("Destination")),
            )
        )
    return rows
