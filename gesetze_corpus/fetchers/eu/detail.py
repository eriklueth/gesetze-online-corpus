"""Detail fetcher + parser for one consolidated EUR-Lex document.

EUR-Lex serves consolidated German-language HTML at a stable
content-negotiation URL. The HTML is enormous (single document,
sometimes 30k lines) and uses a small, consistent subset of class
names per article. We extract:

  - title (`<title>` tag, then trimmed)
  - ELI (from `<link rel="canonical">` or `<meta property="eli">`)
  - articles (each anchored by `<p class="ti-art">` followed by
    a heading `<p class="sti-art">` and one or more body paragraphs)

The parser is deliberately tolerant: EUR-Lex tweaks class names
periodically and older CELEX numbers fall back to `<p class="normal">`
without an `Artikel`-anchor. We surface those as a single un-numbered
"Praeambel" / "Anhang" article rather than failing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .client import _celex_doc_type
from ...http import get


@dataclass
class EuArticle:
    number: str
    heading: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class EuDocument:
    celex: str
    title: str
    eli: str
    doc_type: str
    language: str
    articles: list[EuArticle] = field(default_factory=list)
    raw_html_bytes: int = 0
    # Official Journal short reference, e.g. "L 119/1" (series + page).
    # Empty string when the upstream HTML does not carry the marker --
    # older CELEX numbers and consolidated-only documents often don't.
    oj_reference: str = ""


_CONTENT_NEG = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX:{celex}"


def fetch_detail(celex: str, *, language: str = "DE") -> EuDocument:
    """Network-bound: fetch + parse a single consolidated CELEX."""
    response = get(_CONTENT_NEG.format(lang=language.upper(), celex=celex))
    return parse_detail_html(
        response.content,
        celex=celex,
        language=language.lower(),
    )


def parse_detail_html(
    raw: bytes,
    *,
    celex: str,
    language: str = "de",
) -> EuDocument:
    """Pure-parse: decode, extract metadata, materialise articles."""
    from lxml import html as lxml_html

    doc = lxml_html.fromstring(raw)

    title = ""
    title_el = doc.find(".//title")
    if title_el is not None and title_el.text:
        title = title_el.text.strip()
    title = re.sub(r"\s*-\s*EUR-Lex\s*$", "", title)

    eli = ""
    for el in doc.xpath(
        ".//link[@rel='canonical'] | .//meta[@property='eli'] | .//meta[@property='ELI']"
    ):
        href = el.get("href") or el.get("content") or ""
        if href and ("eli/" in href or "/eli/" in href):
            eli = href
            break

    articles = list(_extract_articles(doc))
    oj_reference = _extract_oj_reference(doc)
    return EuDocument(
        celex=celex,
        title=title,
        eli=eli,
        doc_type=_celex_doc_type(celex),
        language=language,
        articles=articles,
        raw_html_bytes=len(raw),
        oj_reference=oj_reference,
    )


# Matches "ABl. L 119/1", "ABl. L 119, 4.5.2016, S. 1", "OJ L 119/1",
# "OJ L 119, p. 1". Captures series (L|C|M), issue number, and page.
_OJ_REF_RE = re.compile(
    r"(?:ABl\.|OJ|JO|GU|DOUE)\s*([LCM])\s*(\d{1,4})"
    r"(?:\s*[/,]\s*(?:S\.|p\.|pag\.|S\.|str\.)?\s*(\d{1,4})"
    r"|(?:[^/,]{0,40}?\s+(?:S\.|p\.|pag\.)\s*(\d{1,4})))?",
    re.IGNORECASE,
)


def _extract_oj_reference(doc) -> str:
    """Extract the OJ short reference (e.g. ``L 119/1``).

    Looks first at the structured EUR-Lex header paragraphs
    (``oj-hd-coll`` + ``oj-hd-info``) and falls back to a regex over
    the document text. Returns ``""`` when nothing matches; callers
    should treat it as "not available", not as "definitely not in OJ".
    """
    coll = doc.xpath(".//p[contains(@class,'oj-hd-coll')]/text()")
    if coll:
        m = re.search(r"([LCM])\s*(\d{1,4})", " ".join(coll), re.IGNORECASE)
        if m:
            series = m.group(1).upper()
            issue = m.group(2)
            # The page often sits in a sibling paragraph; try to find it.
            page = ""
            for sib in doc.xpath(".//p[contains(@class,'oj-hd-info')]/text()"):
                pm = re.search(r"S\.\s*(\d{1,4})|p\.\s*(\d{1,4})", sib)
                if pm:
                    page = pm.group(1) or pm.group(2)
                    break
            return f"{series} {issue}/{page}" if page else f"{series} {issue}"

    text = " ".join(doc.xpath(".//body//text()"))
    m = _OJ_REF_RE.search(text)
    if not m:
        return ""
    series = (m.group(1) or "").upper()
    issue = m.group(2) or ""
    page = m.group(3) or m.group(4) or ""
    if not (series and issue):
        return ""
    return f"{series} {issue}/{page}" if page else f"{series} {issue}"


_RE_ARTICLE_HEAD = re.compile(r"^\s*Artikel\s+([0-9A-Za-z\-]+)\s*$", re.IGNORECASE)


def _extract_articles(doc) -> list[EuArticle]:
    """Walk the document collecting (number, heading, paragraphs)."""
    articles: list[EuArticle] = []
    current: EuArticle | None = None

    body_paragraphs = doc.xpath(
        ".//p[contains(@class,'ti-art') or contains(@class,'sti-art') or "
        "contains(@class,'oj-normal')] | "
        ".//div[contains(@class,'oj-doc-ti')]/p"
    )
    if not body_paragraphs:
        # Fallback: every <p> directly under <body>.
        body_paragraphs = doc.xpath(".//body//p")

    for el in body_paragraphs:
        classes = _class_tokens(el)
        text = _normalise(_inner_text(el))
        if not text:
            continue
        is_article_head = "ti-art" in classes or (
            "sti-art" not in classes and _RE_ARTICLE_HEAD.match(text)
        )
        is_article_subhead = "sti-art" in classes
        if is_article_head:
            number = _extract_article_number(text)
            current = EuArticle(number=number, heading="")
            articles.append(current)
            continue
        if is_article_subhead and current is not None and not current.heading:
            current.heading = text
            continue
        if current is None:
            current = EuArticle(number="0", heading="Praeambel")
            articles.append(current)
        current.paragraphs.append(text)

    return articles


def _class_tokens(el) -> set[str]:
    """Return the element's class attribute as a token set.

    Substring matching (`'ti-art' in cls`) is wrong for HTML class
    attributes because it matches `'sti-art'` too. Tokenising on
    whitespace gives the correct CSS-class semantics.
    """
    raw = (el.get("class") or "").lower()
    return {tok for tok in raw.split() if tok}


def _extract_article_number(heading: str) -> str:
    m = _RE_ARTICLE_HEAD.match(heading)
    if m:
        return m.group(1)
    digits = re.search(r"\d+[a-zA-Z]?", heading)
    return digits.group(0) if digits else ""


def _inner_text(el) -> str:
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(_inner_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _normalise(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


__all__ = ["fetch_detail", "parse_detail_html", "EuDocument", "EuArticle"]
