# QMSBR website

This repository contains only the public website shell, publication tooling,
tests, and legal metadata for **QMSBR: Quantitative Methods for Social and
Behavioral Research**. Canonical chapters, PDFs, lecture notes, data, and
supplements live in the private sibling `materials/` repository.

Release 2026.1 publishes exactly Chapters 01–04 as HTML and reviewed PDFs, plus
the reviewed Chapter 01 classroom-note PDF. It publishes no standalone script,
syntax, dataset, lab, exercise, project, documentation, or ZIP resource.

## Local workflow

One-time setup requires Python, R 4.5.1, and network access. From this directory:

```powershell
python -m pip install --require-hashes -r requirements-release.txt
Push-Location ../materials
Rscript --vanilla -e "source('renv/activate.R'); renv::restore(prompt = FALSE)"
Pop-Location
python tools/manage.py bootstrap-quarto
```

The Python command installs the exact checked PyYAML release, `renv::restore()`
recreates the private R library from `../materials/renv.lock`, and the final
command installs the pinned portable Quarto under ignored local state. Then:

```powershell
python tools/manage.py sync
python tools/manage.py check
python tools/manage.py build
python tools/manage.py serve
```

The default materials location is the sibling `../materials`. Override it with
`--materials-root C:\path\to\materials` or `QMSBR_MATERIALS_ROOT` when the two
repositories are checked out elsewhere. Disposable staging and rendered output
are kept under the ignored `website/.qmsbr/` directory.

`sync` derives the exact private publication manifest from the catalogue and
approval record. `check` verifies the split source boundary and every approved
hash. `build` assembles an empty, allowlisted Quarto project, renders with the
pinned Quarto version, validates output and links, then promotes the result to
`.qmsbr/site`. Nothing is published or pushed by these commands.

The resulting site is explicitly a **nondeployable local preview**. Public
release creation, GitHub Pages deployment, tags, and pushes remain disabled
until the remote owner and protected publication workflow are configured.

The repository URL and GitHub Pages site URL are intentionally absent until the
GitHub owner name is confirmed.
