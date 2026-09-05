# QMSBR

**Quantitative Methods for Social and Behavioral Research** — a modular
collection of chapters on reading and producing quantitative research.

Site: <https://jinsong-chen.github.io/QMSBR/>

## What is here

- `part-one/` — Foundations, regression, and generalized linear models
  (introduction + Chapters 1, 1a, 2–8)
- `part-two/` — Factor analysis and structural equation modeling
  (introduction + Chapters 1–4), with the R companions and data they use
- `supplement/` — shared render inputs used by the chapters
- `_quarto.yml` — the only configuration file
- `index.qmd`, `library.qmd`, `about.qmd` — the three site pages

Each chapter has a `.qmd` source and a reviewed `.pdf` beside it. The site
renders the HTML; the PDF is offered as a download.

## Building locally

Requires [Quarto](https://quarto.org) 1.8 or later and R with the packages the
Part Two chapters use (`lavaan`, `psych`, `GPArotation`, `DiagrammeR`,
`DiagrammeRsvg`, `rsvg`, `digest`).

```bash
quarto render --to html     # builds the site into _site/
quarto preview              # local preview with live reload
```

Always render with `--to html`. A bare `quarto render` would also fire the
`pdf` and `docx` formats that individual chapters declare.

## Adding or updating a chapter

1. Put the `.qmd` and its `.pdf` in `part-one/` or `part-two/`.
2. Add the `.qmd` to `render:` and to the sidebar in `_quarto.yml`.
3. Add one row to the table in `library.qmd`.
4. `quarto render --to html` and check the page locally.
5. Commit and push — GitHub Actions publishes the site.

## Licence

CC BY 4.0 for text and figures, MIT for original code, CC0 1.0 for simulated
data. Two third-party items keep their own terms. See [LICENSE](LICENSE).

Maintained by Jinsong Chen, Faculty of Education, The University of Hong Kong.
QMSBR is not an official University service.
