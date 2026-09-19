# QMSBR website plan

How the public site is put together: one navigation model, one page
inventory, one theme, one build. The aim is that a reader lands anywhere
and finds the same top row, the same sidebar for the unit being read, and
a page that says plainly what is available and what is not. A change that
touches the frame is made once here and repeated in the practice project
so the two read as one site.

**Ownership.** This plan owns the site's navigation model, page inventory,
theme, build and freeze, the add-a-chapter procedure, and the shared frame
that the practice pages repeat. Three companion documents live in the
author's private working repositories, beside the sources this site
publishes: the publication plan (`materials/PUBLICATION_PLAN.md`) owns the
repositories and the privacy boundary, the copy into this repository, the
PDF rebuild, the licence and the release backlog; the WebR plan
(`materials/webr/WEBR_PLAN.md`) owns the practice project behind
`practice/`; and the chapter technical documents own what a chapter
teaches. Nothing here decides content.

## 1. What is in this repository

- `part-one/` — the Part One introduction, the Part One concept reference,
  Chapters 1--9, each `.qmd` beside its reviewed `.pdf`, and the data files
  the chapters read
- `part-two/` — the Part Two introduction, the Part Two concept reference,
  Chapters 1--4, with their PDFs and data
- `index.qmd`, `about.qmd`, `argument-approach.qmd` — the three site pages
- `practice/` — the R-support pages, rendered from `materials/webr` and
  copied in as static files; `_quarto.yml` lists the folder as a project
  resource, so the build copies it into `_site` untouched
- `_freeze/` — the committed execution cache the CI build restores from
- `_quarto.yml` — the only configuration file
- `styles.scss`, `assets/` — theme and favicon
- `references.bib`, `apa.csl` — the site's own copies of the bibliography
  and citation style
- `LICENSE` — the terms for everything the site ships

The site renders the HTML for each chapter; the PDF beside it is offered as
a download.

## 2. Navigation

### The top row

The navbar is pinned, so the row is on screen at every scroll position on
every page. The brand text is **QMSBR** and the brand is the Home button;
there is no separate Home item. The items, in order:

| Item | Target |
|:--|:--|
| Part One | `part-one/part_one_introduction.qmd` |
| Part Two | `part-two/part_two_introduction.qmd` |
| Part Three | `index.qmd#part-three` — muted and unclickable |
| R support | `practice/index.html` |
| Argument Approach | `argument-approach.qmd` |
| About | `about.qmd` |

Search and the repository icon sit on the right. The two Part buttons land
on their part introductions, which is why an introduction is also the first
entry of its sidebar.

**Muted items.** A navigation entry for a unit that is not yet available is
an ordinary link whose `href` ends in `#part-three`, `#supplement-a` or
`#supplement-b`. One shared CSS rule, selecting on those endings, mutes the
entry to a colour that still meets AA contrast on its background and sets
`pointer-events: none` and `cursor: default`; a small script in
`include-after-body` sets `aria-disabled="true"` and `tabindex="-1"` on the
same links, so keyboard and screen-reader users meet the same state that the
colour shows. Both sites carry the rule and the script. Nothing unreleased
is listed as a live link, and nothing unreleased is hidden either: the muted
entry and the card it points at say what the unit will be and that it is not
yet available.

### Sidebars

The book site uses Quarto's multiple docked sidebars, each with an `id`, a
`title` and its own `contents`. A page belongs to one of them:

- **Part One** — `part-one/part_one_introduction.qmd` with the text
  *Introduction*, `part-one/part_one_concept_reference.qmd` as *Concept
  reference*, then Chapters 1--9 by title.
- **Part Two** — `part-two/part_two_introduction.qmd`,
  `part-two/part_two_concept_reference.qmd`, then Chapters 1--4.
- **Argument Approach** — `argument-approach.qmd` as *The argument-based
  approach*, then *A. How to Read a Quantitative Study as an Argument*
  (`argument-approach.qmd#supplement-a`) and *B. Extending the
  Argument-Based Approach to Quantitative Studies*
  (`argument-approach.qmd#supplement-b`), both muted by the rule above.

Home and About carry no sidebar. The practice site has one docked sidebar of
its own (WebR plan, Section 1).

## 3. Pages

**Home (`index.qmd`).** A site summary in learner-facing prose: what QMSBR
is and who it is for, how the site is organized, and how to start. Then a
**Collections** section of five cards — Part One, Part Two, Part Three
(muted, carrying the id `part-three`: multilevel and longitudinal models,
reserved, not yet available), R support, and Argument Approach (muted,
listing supplements A and B as not yet available). Then **How to use this
site** (read online or download the PDF, the concept reference, the practice
pages, and the note that a course may add its own materials) and **What
comes next** (Part One Chapters 10--14 by number and title, Part Two's SEM
continuation, Part Three, and the supplementary chapters). The author band
closes the page.

**About (`about.qmd`).** A short site summary, the author, how to cite,
licences, accessibility, and using QMSBR in a course.

**Argument Approach (`argument-approach.qmd`).** Titled *The Argument-Based
Approach*. The approach text, then a **Supplementary chapters** section with
two subsections carrying the ids `supplement-a` and `supplement-b`, each
naming its chapter and saying that it is not yet available.

**Part introductions.** Learner-facing guidance for the part: what it is and
who it is for, how its chapters build on each other, how to read a chapter,
and what comes later. Each is the first entry of its sidebar and the target
of its Part button.

**Concept references.** `part-one/part_one_concept_reference.qmd` and
`part-two/part_two_concept_reference.qmd` are public units of their own,
each a short opening on how to read the tables followed by the part's master
concept tables and notation. They are copied from the tech docs and checked
with the author's concept-reference sync tool; nothing on the site edits a
table in place.

**Chapters.** One page per chapter, with the reviewed PDF beside it.

## 4. Theme

`cosmo` with `styles.scss`. The palette is teal (`#0f6d72`) with a coral
accent on a paper background, set once in the SCSS defaults and exposed as
CSS variables for the cards and callouts. The stylesheet also carries the
scroll offset the pinned navbar needs, so an in-page jump does not land
under the bar, and the muted-link rule of Section 2. The practice project
shares the same palette in its own `theme.scss`, so the top row reads as one
bar across both sites.

## 5. Build and freeze

```bash
quarto render --to html     # builds the site into _site/
quarto preview              # local preview with live reload
```

Always render with `--to html`. A bare `quarto render` would also fire the
`pdf` and `docx` formats that individual chapters declare.

The build needs Quarto 1.10.18 — the version `.github/workflows/publish.yml`
pins, and the version that produced the committed `_freeze/` cache; keep the
two equal. A local render also needs R with the packages the chapters load:
chiefly `ggplot2`, `car`, `carData`, `AER` and `sandwich` in Part One, and
`lavaan`, `psych` and `GPArotation` in Part Two.

`_freeze/` stays committed. CI installs no R and no LaTeX, and restores
computed results from the cache, which is why the local render is not
optional: it is the step that executes a changed chapter's R and rewrites
its `_freeze/` entry. The entry's hash covers only the `.qmd` text, so when
a data file a chapter reads changes, delete that chapter's `_freeze/` entry
before rendering or the page keeps the old numbers.

## 6. Adding or updating a chapter

1. Copy the `.qmd`, the `.pdf` and any data file the chapter reads into
   `part-one/` or `part-two/` (publication plan, Section 4); copy
   `references.bib` and `apa.csl` too if the citations or the style changed.
2. Add the `.qmd` to `render:` in `_quarto.yml` and to the `contents:` of
   its part's sidebar, in reading order.
3. Add its line to that part's card on `index.qmd`, and remove it from
   **What comes next** if it was listed there. A retitled chapter needs both
   the sidebar entry and the card line updated.
4. Third-party material of any kind means one more line in `LICENSE` at the
   same time; a data file a chapter no longer reads is deleted from this
   repository and struck from `LICENSE` at the same time.
5. `quarto render --to html`, then check the page, its sidebar entry and its
   PDF link.
6. Commit the regenerated `_freeze/` entry with the sources and push; GitHub
   Actions renders and deploys.

A unit that publishes into a muted slot — a supplementary chapter, Part
Three — is the same work plus one step: the muted entry becomes an ordinary
link, and its card and section text drop the not-yet-available sentence.

`practice/` is never edited here. Fix the source in `materials/webr/` and
copy the rendered output in again (publication plan, Section 4.1).

## 7. The practice frame

The practice pages are a separate Quarto project, but they are part of the
same site to a reader, so they carry the same frame:

- the identical top row in the same order, with hrefs relative to
  `/practice/`: brand and Home `../index.html`,
  `../part-one/part_one_introduction.html`,
  `../part-two/part_two_introduction.html`, `../index.html#part-three`,
  `index.qmd` for R support, `../argument-approach.html`, `../about.html`
- the brand text **QMSBR**, not a variant of it
- the same teal palette
- the same muted-link CSS rule and the same `include-after-body` script

Any change to the top row, the brand, the palette or the muting rule is made
in `_quarto.yml` and `styles.scss` here and in `materials/webr/_quarto.yml`
and its theme in the same pass, and the practice output is re-rendered and
recopied so the deployed row matches. The practice site's own sidebar is
independent and does not change with the book sidebars.
