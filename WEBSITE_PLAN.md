# QMSBR website plan

How the public site is put together: one navigation model, one page
inventory, one theme, one build. The aim is that a reader lands anywhere
and finds the same top row, the same sidebar for the unit being read, and
a page that says plainly what is available and what is not. A change that
touches the frame is made once here and repeated in the practice project
so the two read as one site.

**Ownership.** This plan owns how the site presents its pages: the
navigation model and its sidebars, the page inventory, layout, theme, build
and freeze, the add-a-chapter procedure, and the shared frame that the
practice pages repeat. What a page says belongs to the technical document
(tech doc) that governs it, in the author's private instructor repository:
the Home, About and Argument Approach pages, and the practice project's
shared pages (its home, Workspace page and data register), to the Part One
tech doc, Section 3 (`instructor/part_one_tech.qmd`); each part's
introduction and concept reference to that part's tech doc, Section 3 (the
Part One tech doc, or `instructor/part-two/part_two_tech.qmd` for Part
Two); and each chapter to its chapter tech doc. Two companion documents live in the author's
private materials repository, beside the sources this site publishes: the
publication plan (`materials/PUBLICATION_PLAN.md`) owns the repositories
and the privacy boundary, the copy into this repository, the PDF rebuild,
the licence and the release backlog; the WebR plan
(`materials/webr/WEBR_PLAN.md`) owns the practice project behind
`practice/`. Nothing here decides content: where this plan names what a
page carries, it does so to place it in the layout, and the tech doc's
wording and order govern.

## 1. What is in this repository

- `part-one/` — the Part One introduction, the Part One concept reference,
  Chapters 1--14 and Argument Chapters A/B, each `.qmd` beside its reviewed
  `.pdf`, and the data files the chapters read
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
- `koma_heading_tags.tex` — the synchronized PDF heading support from
  `materials/`, retained with the copied sources for reproducible PDF builds
- `LICENSE` — the terms for everything the site ships

The site renders the HTML for each available chapter; the PDF beside it is
offered as
a download near the title and through `format-links: [pdf]` in the margin.
These links appear on each part introduction and concept reference too;
formats without reviewed public files are not offered.

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

Search sits on the right; the public reading interface carries no
development-repository link. The two Part buttons land
on their part introductions, which is why an introduction is also the first
entry of its sidebar.

**Muted items.** Navigation entries for unavailable units point to their
labelled placeholders. Shared CSS mutes those entries while retaining AA
contrast; `include-after-body` applies `aria-disabled="true"` and
`tabindex="-1"` so keyboard and screen-reader users meet the same state.
The current navigation placeholders are Part Three and Argument C. Part Two
Chapters 5--12 remain later work for publication and are described on Home;
the public Part Two sidebar contains Chapters 1--4.
The earlier `#supplement-a` and `#supplement-b` anchors remain live aliases
on the Argument Approach page, whose A/B sections link to the books.
The practice project repeats the same navigation rules.

### Sidebars

The book site uses Quarto's multiple docked sidebars, each with an `id`, a
`title` and its own `contents`. A part's sidebar is titled with the part's
full title as its tech doc gives it, such as *Part One: Foundations,
Regression, and Generalized Linear Models*. A page belongs to one of them:

- **Part One** — `part-one/part_one_introduction.qmd` with the text
  *Introduction*, `part-one/part_one_concept_reference.qmd` as *Concept
  reference*, then Chapters 1--14 by title.
- **Part Two** — `part-two/part_two_introduction.qmd`,
  `part-two/part_two_concept_reference.qmd`, then Chapters 1--4.
- **Argument Approach** — `argument-approach.qmd` as *The argument-based
  approach*, then the three argument chapters: *A. How to Read a
  Quantitative Study as an Argument* (`part-one/chapter_arg_a.qmd`),
  *B. Extending the Argument-Based Approach to Quantitative Studies*
  (`part-one/chapter_arg_b.qmd`), and *C. Arguments involving latent
  variables or an additional measurement layer*
  (`argument-approach.qmd#argument-c`). C's wording names its scope until
  its technical specification fixes the title. A and B are live book links;
  C stays muted until available.

Home and About carry no sidebar. The practice site has one docked sidebar of
its own (WebR plan, Section 1).

## 3. Pages

The tech docs specify what each page says (see *Ownership*). This section
fixes where each page sits and which layout elements it uses, so that a
change of wording needs no change here.

**Home (`index.qmd`).** Full width (`page-layout: full`), with no sidebar
and no table of contents, and the body class `qmsbr-home`. The page opens
with the hero block (`.qmsbr-hero`: kicker, heading, the opening
paragraphs, two buttons, and the release line in `.release-strip`), then
carries its remaining parts in the order the Part One tech doc, Section 3,
gives: the **Collections** grid (`#collections`, five `.collection-card`s
in the order of the top row), *Using QMSBR in a course*, *How to use this
site*, *What comes next* as a `.roadmap-grid`, and the `.author-band`. The
Part Three card carries the id `part-three`, the `.unavailable` class and
`aria-disabled="true"`, and lists no link. The Argument Approach card keeps
its link to the approach page live and links A/B with their PDFs; C remains
in a `.card-muted-block`. Wherever a unit that is not yet available is named,
the `.badge-unavailable` chip marks it.

**About (`about.qmd`).** No sidebar. Its sections keep the anchors that the
footer and the Home page link to: `#citation`, `#licences` and `#courses`.

**Argument Approach (`argument-approach.qmd`).** Titled *The Argument-Based
Approach* and the first entry of its sidebar, with page navigation turned
off so that the unavailable C entry never becomes a pagination link. Its
closing section carries `argument-a`, `argument-b` and
`argument-c`, with `supplement-a` and `supplement-b` retained as aliases,
so the sidebar and existing links resolve. It reads `references.bib` and
`apa.csl` for its citations.

**Part introductions.** Each is the first entry of its sidebar and the
target of its Part button.

**Concept references.** `part-one/part_one_concept_reference.qmd` and
`part-two/part_two_concept_reference.qmd` are public units of their own,
the second entry of their part's sidebar. They are copied in like a
chapter; nothing on the site edits a table in place.

**Chapters.** One page per chapter, with the reviewed PDF beside it.
The download is visible in the reading column at every screen width.
Pages using margin contents also have a collapsed **Contents** menu below
the download on screens narrower than 768 pixels. Pages that explicitly
place their contents in the body retain that layout at every width.
These rules also apply to the part introductions and concept references.

## 4. Theme

`cosmo` with `styles.scss`. The palette is teal (`#0f6d72`) with a coral
accent on a paper background, set once in the SCSS defaults and exposed as
CSS variables for the cards and callouts. The stylesheet also carries the
scroll offset the pinned navbar needs, so an in-page jump does not land
under the bar, and the muted-link rule of Section 2. The page clips sideways
overflow so that the Home hero can bleed to full width; a wide table or
display equation therefore scrolls sideways inside its own box, so on a
phone the part beyond the screen edge stays reachable. A page's front-matter
`description` serves as its meta description and is hidden in the title
block, so the page's own first paragraph is the first one a reader sees.
The practice project shares the same palette in its own `theme.scss`, so
the top row reads as one bar across both sites.

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

The post-render step `tools/page_access.py` uses Python 3's standard
library, available locally and on the GitHub Actions runner. It adds the
reviewed PDF link after the title and wraps Quarto's `right-body` contents
copy in native HTML disclosure controls, giving that copy unique IDs.
The controls work without JavaScript; CSS shows the body contents only
when the margin contents is hidden. It changes rendered page navigation,
never the copied chapter source or PDF.
The same step removes next/previous controls and relationship links that
Quarto derives from an unavailable sidebar placeholder.

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
   its part's sidebar, in reading order. List under `project.resources` any
   data file a reader should be able to download that no page links: the
   build deploys a copied file only when a page links it or `resources:`
   names it.
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

A unit that publishes into a muted slot — an argument chapter, Part
Three — is the same work plus one step: the muted entry becomes an ordinary
link, and its card and section text drop the not-yet-available badge and
sentence.

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
