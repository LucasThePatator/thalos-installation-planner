# thalos-installation-planner

Generates printable A4 logistics charts for the Thalos Halloween event from
the shared Google Sheet: who brings/takes back what, grouped either by
category or by person.

## Usage

```bash
uv run python3 main.py
```

Produces, in `output/`:

- `installation_par_categorie.svg`
- `installation_par_personne.svg`
- `installation_par_provenance.svg`
- `rangement_par_categorie.svg`
- `rangement_par_personne.svg`
- `rangement_par_destination.svg`
- `thalos_planning.pdf` — all six charts combined
- `rangement_checklists.pdf` — one big-letter checklist page per person,
  for the "rangement" (take-back) items they're responsible for

Each SVG is sized to exactly one A4 page and can be printed directly from a
browser. Text never prints smaller than 12pt: if a chart's content doesn't
fit one page at that size, it spills onto additional same-named pages
instead (`<name>_2.svg`, `_3.svg`, ...), included alongside the first page
in `thalos_planning.pdf`.

### Options

```bash
uv run python3 main.py --csv <path-or-url> --output-dir <dir>
```

- `--csv`: URL or local path to the sheet CSV export. Defaults to the live
  Google Sheet (must be link-shared/viewable).
- `--output-dir`: where to write the generated files. Defaults to `output/`.
