"""Listing parser for verwaltungsvorschriften-im-internet.de.

The upstream portal is HTML-only (no structured index). Entries sit in
a nested <ul> tree on the landing page, each entry being an <a> whose
text contains the short title and whose href points at the per-VwV
HTML page.

The page groups VwVs by Ressort (h2-level heading) and Bereich
(h3-level heading); some sub-pages add a fourth level via h4 or a
strong-tagged paragraph. This parser walks the document in tree order,
keeps a per-level heading stack, and snapshots that stack onto every
emitted `VwVEntry` so writers can later reconstruct `Ressort > Bereich
> ...` navigation paths.

Tolerant to malformed HTML; unknown link patterns are skipped rather
than raised, and entries without any heading context come back with an
empty breadcrumb tuple instead of an exception.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...http import get

LANDING_URL = "http://www.verwaltungsvorschriften-im-internet.de/"

_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# Paragraphs the portal uses as visible breadcrumb-like markers
# instead of real heading tags. We treat these as "depth 4" so they
# nest below h2/h3 sections without overriding them.
_PSEUDO_HEADING_CLASSES = ("jncategory", "jnressort", "jnbereich")

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class VwVEntry:
    short: str
    title: str
    url: str
    breadcrumb: tuple[str, ...] = field(default_factory=tuple)


def fetch_listing(limit: int | None = None) -> list[VwVEntry]:
    raw = get(LANDING_URL).content
    entries = parse_listing_html(raw)
    if limit is not None:
        entries = entries[:limit]
    return entries


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _classify(elem) -> tuple[str, int] | None:
    """Return ('heading', depth) | ('link', 0) | ('pseudo', depth) | None."""
    tag = (elem.tag or "").lower()
    if tag in _HEADING_LEVELS:
        return ("heading", _HEADING_LEVELS[tag])
    if tag == "a":
        return ("link", 0)
    if tag == "p":
        cls = (elem.get("class") or "").lower()
        if any(c in cls for c in _PSEUDO_HEADING_CLASSES):
            return ("pseudo", 4)
    return None


def parse_listing_html(raw: bytes) -> list[VwVEntry]:
    try:
        from lxml import html as lxml_html
    except ImportError as exc:
        raise RuntimeError("lxml required for VwV listing parser") from exc

    doc = lxml_html.fromstring(raw)
    entries: list[VwVEntry] = []
    # Keep one slot per heading depth (1..6). When a deeper heading
    # appears, lower-depth slots stay; when a same-or-shallower
    # heading appears, all deeper slots are cleared so we don't carry
    # stale context across siblings.
    stack: dict[int, str] = {}

    for elem in doc.iter():
        kind = _classify(elem)
        if not kind:
            continue
        what, depth = kind

        if what in ("heading", "pseudo"):
            label = _norm(elem.text_content())
            if not label:
                continue
            stack[depth] = label
            for d in list(stack):
                if d > depth:
                    stack.pop(d, None)
            continue

        # link
        href = elem.get("href") or ""
        text = _norm(elem.text_content())
        if not text or not href:
            continue
        if not href.endswith(".html") and "/inhalt" not in href:
            continue
        if "/" in href and not href.startswith("http"):
            abs_url = LANDING_URL.rstrip("/") + "/" + href.lstrip("./")
        else:
            abs_url = href

        short, _, title = text.partition(" ")
        breadcrumb = tuple(stack[d] for d in sorted(stack))
        entries.append(
            VwVEntry(
                short=short.strip(),
                title=(title or short).strip(),
                url=abs_url,
                breadcrumb=breadcrumb,
            )
        )

    return entries
