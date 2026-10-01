"""Keep chapter contents and reviewed PDF downloads reachable at every width.

Runs after Quarto renders HTML. Uses only Python's standard library so the
local build and GitHub Pages build produce the same static controls.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
TOC = re.compile(r'<nav id="TOC-body"[^>]*>.*?</nav>', re.S)
TITLE = re.compile(r'<header id="title-block-header"[^>]*>.*?</header>', re.S)


def improve_page(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if 'class="qmsbr-page-download"' in html or 'class="qmsbr-mobile-contents"' in html:
        # Also normalize an existing processed page during incremental builds.
        html = html.replace('id="TOC-body"', 'id="qmsbr-contents"')
        path.write_text(html, encoding="utf-8")
        return False
    pdf = path.with_suffix(".pdf")
    has_pdf = (ROOT / path.relative_to(SITE)).with_suffix(".pdf").is_file()
    if has_pdf:
        title = TITLE.search(html)
        if not title:
            raise ValueError(f"Missing title block: {path}")
        if not pdf.is_file():
            raise ValueError(f"Missing reviewed PDF: {pdf}")
        download = (
            '\n<p class="qmsbr-page-download">'
            f'<a class="btn btn-outline-primary" href="{pdf.name}" download>'
            'Download PDF</a></p>\n'
        )
        html = html[:title.end()] + download + html[title.end():]
    toc = TOC.search(html)
    if toc:
        # Quarto's right-body layout repeats the sidebar's toc-* identifiers.
        # Give the body copy its own identifiers while keeping section targets.
        body = re.sub(r'id="toc-', 'id="body-toc-', toc.group())
        body = body.replace('id="TOC-body"', 'id="qmsbr-contents"')
        body = re.sub(r'<h2 id="body-toc-title">.*?</h2>', '', body, flags=re.S)
        body = body.replace('role="doc-toc"', 'role="doc-toc" aria-label="Contents"')
        details = (
            '<details class="qmsbr-mobile-contents">'
            '<summary>Contents</summary>' + body + '</details>'
        )
        html = html[:toc.start()] + details + html[toc.end():]
    elif has_pdf and not re.search(r'<nav id="TOC"[^>]*>', html[title.end():]):
        raise ValueError(f"Missing body contents: {path}")
    elif not has_pdf:
        return False
    path.write_text(html, encoding="utf-8")
    return True


count = 0
for directory in (SITE, SITE / "part-one", SITE / "part-two"):
    for page in sorted(directory.glob("*.html")):
        count += improve_page(page)
print(f"Chapter access: {count} pages updated.")
