# QMSBR

**Quantitative Methods for Social and Behavioral Research** — a modular
collection of chapters on reading and producing quantitative research.

Site: <https://jinsong-chen.github.io/QMSBR/>

Every page carries the same pinned top row — Home, Part One, Part Two,
R support, Argument Approach, About — and the practice pages under
`practice/` repeat that row with relative paths back into the book site.

## What is here

- `part-one/` — Foundations, regression, and generalized linear models
  (introduction + Chapters 1–9), with the data Chapter 1 reads
- `part-two/` — Factor analysis and structural equation modeling
  (introduction + Chapters 1–4), with the data they use
- `practice/` — the R-support pages, rendered from `materials/webr` and copied
  in here as static files; `_quarto.yml` lists it as a project resource, so the
  build copies the folder into `_site` untouched
- `_freeze/` — the committed execution cache; the GitHub Actions build runs
  Quarto without R and restores results from here
- `_quarto.yml` — the only configuration file
- `index.qmd`, `about.qmd` — the two site pages

Each chapter has a `.qmd` source and a reviewed `.pdf` beside it. The site
renders the HTML; the PDF is offered as a download.

## Building locally

Requires [Quarto](https://quarto.org) 1.10.18 — the version
`.github/workflows/publish.yml` pins, and the version that produced the
committed `_freeze/` cache. R is also needed, with the packages the chapters
load: chiefly `ggplot2`, `car`, `carData`, `AER`, and `sandwich` in Part One,
and `lavaan`, `psych`, and `GPArotation` in Part Two.

```bash
quarto render --to html     # builds the site into _site/
quarto preview              # local preview with live reload
```

Always render with `--to html`. A bare `quarto render` would also fire the
`pdf` and `docx` formats that individual chapters declare.

## Adding or updating a chapter

1. Put the `.qmd` and its `.pdf` in `part-one/` or `part-two/`, together with
   any data file the chapter reads.
2. Add the `.qmd` to `render:` and to the sidebar in `_quarto.yml`.
3. Add its line to the matching collection column in `index.qmd`.
4. `quarto render --to html` and check the page locally.
5. Commit the regenerated `_freeze/` entry together with the sources.
6. Commit and push — GitHub Actions publishes the site.

The `practice/` folder is not edited here. It is re-rendered from
`materials/webr` and its output is recopied whole.

## Licence

CC BY 4.0 for text and figures, MIT for original code, CC0 1.0 for simulated
data. Third-party items keep their own terms. See [LICENSE](LICENSE).

Maintained by Jinsong Chen, Faculty of Education, The University of Hong Kong.
QMSBR is not an official University service.
