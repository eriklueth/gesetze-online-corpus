"""Parse the rechtsprechung-im-internet.de listing page.

The upstream provides a TOC at `/rii-toc.xml` (analogous to GII's
`gii-toc.xml`). Entries link to per-decision ZIP archives containing
XML + PDF. This module only handles discovery — the per-decision
fetch, canonicalize, render and commit lives in the sibling modules
(currently scaffolds).

Keep network access to this file so the renderer, writer, and commit
logic can be unit-tested against local fixtures without hitting the
upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...http import get

LISTING_URL = "https://www.rechtsprechung-im-internet.de/rii-toc.xml"


@dataclass(frozen=True)
class DecisionEntry:
    """A single entry from the upstream listing."""

    court: str
    date: str
    case_no: str
    ecli: str
    zip_url: str


def fetch_listing(limit: int | None = None) -> list[DecisionEntry]:
    """Return parsed listing entries. Network-bound."""
    raw = get(LISTING_URL).content
    entries = parse_listing_xml(raw)
    if limit is not None:
        entries = entries[:limit]
    return entries


def parse_listing_xml(raw: bytes) -> list[DecisionEntry]:
    """Parse a listing payload. Works on fixtures.

    The upstream schema is small and well-formed. We keep the parser
    tolerant: unknown elements are ignored, partial entries (missing
    ECLI) are skipped rather than raised.
    """
    from lxml import etree

    root = etree.fromstring(raw)
    out: list[DecisionEntry] = []
    ns = {"rii": root.nsmap.get(None, "")} if root.nsmap.get(None) else {}
    items = root.findall(".//item", namespaces=ns or None)
    if not items:
        items = root.findall(".//{*}item")
    for it in items:
        ecli = _text(it, "ecli") or ""
        if not ecli:
            continue
        out.append(
            DecisionEntry(
                court=_text(it, "gericht") or "",
                date=_text(it, "entscheidungsdatum") or "",
                case_no=_text(it, "aktenzeichen") or "",
                ecli=ecli,
                zip_url=_text(it, "link") or "",
            )
        )
    return out


def _text(el, tag: str) -> str | None:
    for child in el.iter():
        if child.tag.split("}", 1)[-1] == tag:
            return (child.text or "").strip() or None
    return None
