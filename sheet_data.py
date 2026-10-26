"""Fetch and parse the Thalos installation-planning Google Sheet."""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1GBzIrW-1pkUjUGPe0fx344l_zYtaQugbRDKMMaWiyrg/export?format=csv&gid=261909291"
)

NON_RENSEIGNE = "Non renseigné"

FETCH_TIMEOUT_S = 15

REQUIRED_COLUMNS = ["Objet", "Catégorie", "Provenance", "Amené par", "Repris par", "Destination de stockage"]


class SheetFetchError(Exception):
    """Raised for any sheet fetch/parse failure that needs a clear, actionable
    message instead of a raw urllib/csv traceback."""


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


def _looks_like_html(text: str) -> bool:
    """Google serves an HTML login/error page instead of a CSV when a sheet
    isn't publicly shared (or sharing was revoked) — that would otherwise get
    parsed as garbage CSV rows rather than reported as a fetch failure."""
    return text.lstrip()[:15].lower().startswith(("<!doctype html", "<html"))


def _read_csv_text(source: str) -> str:
    if source.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(source, timeout=FETCH_TIMEOUT_S) as response:
                content_type = response.headers.get_content_type()
                text = response.read().decode("utf-8-sig")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SheetFetchError(f"Impossible de joindre la feuille ({source}) : {exc}") from exc
        if content_type == "text/html" or _looks_like_html(text):
            raise SheetFetchError(
                f"La feuille n'est pas accessible publiquement (réponse HTML reçue au lieu d'un CSV) "
                f"pour {source} — vérifiez les droits de partage."
            )
        return text
    try:
        with open(source, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        raise SheetFetchError(f"Impossible de lire le fichier CSV ({source}) : {exc}") from exc
    if _looks_like_html(text):
        raise SheetFetchError(f"Le fichier {source} contient du HTML, pas un CSV.")
    return text


def fetch_rows(source: str = DEFAULT_SHEET_URL) -> list[Row]:
    """Fetch the sheet (from a URL or a local CSV path) and parse it into Rows."""
    text = _read_csv_text(source)
    reader = csv.DictReader(io.StringIO(text))

    found_columns = set(reader.fieldnames or [])
    missing = [column for column in REQUIRED_COLUMNS if column not in found_columns]
    if missing:
        raise SheetFetchError(
            f"Colonne(s) manquante(s) dans le CSV : {', '.join(missing)}. "
            f"Colonnes trouvées : {', '.join(reader.fieldnames or []) or '(aucune)'}."
        )

    rows: list[Row] = []
    skipped = 0
    for record in reader:
        objet = (record.get("Objet") or "").strip()
        if not objet:
            skipped += 1
            continue
        rows.append(
            Row(
                objet=objet,
                categorie=_clean(record.get("Catégorie")),
                provenance=_clean(record.get("Provenance")),
                amene_par=_clean(record.get("Amené par")),
                repris_par=_clean(record.get("Repris par")),
                destination=_clean(record.get("Destination de stockage")),
            )
        )
    if skipped:
        print(f"{skipped} ligne(s) ignorée(s) (Objet vide)")
    return rows
