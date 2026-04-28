"""Per-VwV detail page parser.

verwaltungsvorschriften-im-internet.de serves each Verwaltungsvorschrift
as a single HTML document (or a small set of linked HTML pages -- the
"Inhaltsuebersicht" plus per-section pages). The structure on every
page follows the template:

  <p class="jnenbez">1.</p>
  <p class="jnenbez">1.1</p>
  ...
  <div class="jnhtml">...body text...</div>

Section identifiers are decimal-numbered ("1", "1.1", "1.2.3") and
encode hierarchy directly. We treat each leaf decimal as a renderable
section; intermediate nodes that only group children carry an empty
body and serve as table-of-contents entries.

The parser is tolerant: it skips fragments it cannot classify and
returns whatever it managed to extract. We log the unmatched fragments
in `VwVDocument.warnings` so callers can spot regressions quickly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...http import get


@dataclass
class VwVSection:
    ordinal: str  # "1", "1.1", "2.3.4"
    heading: str  # short title, may be empty
    text: str  # plain-text body (paragraphs joined with \n\n)
    html: str = ""  # raw HTML of the body, useful for round-tripping


@dataclass
class VwVDocument:
    short: str
    title: str
    url: str
    promulgation_date: str | None = None  # ISO yyyy-mm-dd if known
    sections: list[VwVSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_ORDINAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s*(.*)$")
_DATE_RE = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+|\d{1,2})\.?\s*(\d{4})\b")
_MONTHS = {
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}


def fetch_detail(url: str) -> VwVDocument:
    """Fetch and parse a per-VwV detail page."""
    raw = get(url).content
    return parse_detail_html(raw, url=url)


def parse_detail_html(raw: bytes, *, url: str = "") -> VwVDocument:
    try:
        from lxml import html as lxml_html
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("lxml required for VwV detail parser") from exc

    doc = lxml_html.fromstring(raw)

    # Title and short tag live in the page header. The portal's template
    # puts the title in <h1 class="jnoverview"> or as the first <h1>;
    # fall back to <title> if neither is present.
    title = ""
    short = ""
    title_xpaths = (
        "//h1[contains(@class,'jnoverview')]",
        "//h1",
        "//title",
    )
    for xp in title_xpaths:
        nodes = doc.xpath(xp)
        if nodes:
            title = (nodes[0].text_content() or "").strip()
            break
    # Short identifier is usually right next to the title in <p class="jnsmall">.
    for node in doc.xpath("//*[contains(@class,'jnsmall')]"):
        text = (node.text_content() or "").strip()
        if text and len(text) < 32:
            short = text
            break

    # Promulgation date, if discoverable in the metadata block.
    promulgation: str | None = None
    for node in doc.xpath("//*[contains(@class,'jnsmall') or contains(@class,'jnnorm')]"):
        m = _DATE_RE.search(node.text_content() or "")
        if m:
            iso = _to_iso(m.group(1), m.group(2), m.group(3))
            if iso:
                promulgation = iso
                break

    sections: list[VwVSection] = []
    warnings: list[str] = []

    # Walk the document body in document order. The portal alternates
    # between "<p class='jnenbez'>NUM</p>" and a following content block
    # (paragraphs, tables, lists). We collect runs of content per
    # ordinal until the next ordinal marker appears.
    current: VwVSection | None = None
    body_html: list[str] = []

    body = doc.body if doc.body is not None else doc

    def _flush() -> None:
        nonlocal current, body_html
        if current is None:
            return
        html_blob = "\n".join(body_html).strip()
        text_blob = _html_to_text(html_blob)
        current.html = html_blob
        current.text = text_blob
        sections.append(current)
        current = None
        body_html = []

    for el in body.iter():
        cls = (el.get("class") or "")
        text = (el.text_content() or "").strip()
        if "jnenbez" in cls and text:
            m = _ORDINAL_RE.match(text)
            if not m:
                warnings.append(f"unparsed ordinal: {text!r}")
                continue
            _flush()
            ordinal, heading = m.group(1), m.group(2).strip()
            current = VwVSection(ordinal=ordinal, heading=heading, text="")
        elif "jnhtml" in cls and current is not None:
            try:
                from lxml import etree
                body_html.append(etree.tostring(el, encoding="unicode"))
            except Exception:
                body_html.append(text)
    _flush()

    return VwVDocument(
        short=short,
        title=title,
        url=url,
        promulgation_date=promulgation,
        sections=sections,
        warnings=warnings,
    )


def _to_iso(day: str, month: str, year: str) -> str | None:
    try:
        d = int(day)
        if month.isdigit():
            m = int(month)
        else:
            m = _MONTHS.get(month.lower())
            if not m:
                return None
        y = int(year)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (TypeError, ValueError):
        return None


def _html_to_text(html_blob: str) -> str:
    if not html_blob:
        return ""
    try:
        from lxml import html as lxml_html
    except ImportError:  # pragma: no cover
        return html_blob
    fragment = lxml_html.fragment_fromstring(html_blob, create_parent=True)
    paragraphs: list[str] = []
    for node in fragment.iter():
        tag = node.tag if isinstance(node.tag, str) else ""
        if tag in {"p", "li", "td", "th"}:
            text = (node.text_content() or "").strip()
            if text:
                paragraphs.append(text)
    if paragraphs:
        return "\n\n".join(paragraphs)
    return (fragment.text_content() or "").strip()
