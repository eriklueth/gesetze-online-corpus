"""Parse `rii` decision XML into the canonical `DecisionDoc` shape.

The portal's XML schema is a flat element list per decision, with
German-language element names and no XML namespace declarations
(despite the docs claiming otherwise). The schema is documented at
http://www.rechtsprechung-im-internet.de/dokumente.dtd; in practice
the parser is more useful when tolerant:

- Element order is unstable across courts.
- Some courts (BVerfG in particular) inline HTML in <gruende>.
- ECLI may be missing from older snapshots; reconstruct from
  court + date + case_no when possible.

We keep the parser dependency-light: lxml only for robust HTML
unwrapping, falling back to ElementTree if lxml is absent.
"""

from __future__ import annotations

import re
from dataclasses import field
from typing import Iterable
from xml.etree import ElementTree as ET

from .render import DecisionDoc

_PARAGRAPH_TAGS = {"p", "rd", "absatz", "absatzgruppe"}
_BLOCK_TAGS = {"leitsatz", "tenor", "gruende", "tatbestand", "entscheidungsgruende"}
_NORM_TAGS = {"norm", "normen"}


def parse_decision_xml(raw: bytes) -> DecisionDoc:
    """Parse decision XML bytes. Returns a populated DecisionDoc."""
    text = _decode(raw)
    root = ET.fromstring(text)

    ecli = _first_text(root, ("ecli",)) or _build_ecli(root)
    court = _first_text(root, ("gericht",)) or ""
    date = _normalise_date(_first_text(root, ("entscheidungsdatum",)) or "")
    case_no = _first_text(root, ("aktenzeichen",)) or ""
    decision_type = _first_text(root, ("doktyp", "entscheidungsart")) or ""

    doc = DecisionDoc(
        ecli=ecli,
        court=court,
        date=date,
        case_no=case_no,
        decision_type=decision_type,
    )

    doc.leitsaetze = _block_paragraphs(root, "leitsatz")
    doc.tenor = _block_paragraphs(root, "tenor")
    gruende = _block_paragraphs(root, "gruende")
    if not gruende:
        # Older XMLs split into <tatbestand>+<entscheidungsgruende>.
        gruende = _block_paragraphs(root, "tatbestand") + _block_paragraphs(
            root, "entscheidungsgruende"
        )
    doc.gruende = gruende
    doc.normrefs = _collect_normrefs(root)
    return doc


def _decode(raw: bytes) -> str:
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8")
    # Sniff the XML declaration for an explicit encoding.
    head = raw[:200].decode("ascii", errors="replace")
    m = re.search(r'encoding=["\']([\w-]+)["\']', head)
    enc = (m.group(1) if m else "utf-8").lower()
    if enc in {"utf-8", "utf8"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")
    return raw.decode(enc, errors="replace")


def _first_text(root: ET.Element, names: Iterable[str]) -> str | None:
    needles = {n.lower() for n in names}
    for el in root.iter():
        tag = _localname(el.tag).lower()
        if tag in needles:
            text = (el.text or "").strip()
            if text:
                return text
    return None


def _block_paragraphs(root: ET.Element, name: str) -> list[str]:
    """Return one paragraph per <p>-equivalent inside a top-level block."""
    out: list[str] = []
    for el in root.iter():
        if _localname(el.tag).lower() != name.lower():
            continue
        out.extend(_extract_paragraphs(el))
    return [p for p in (s.strip() for s in out) if p]


def _extract_paragraphs(el: ET.Element) -> list[str]:
    paragraphs: list[str] = []
    # If the block has explicit paragraph children, prefer those.
    children = [c for c in el if _localname(c.tag).lower() in _PARAGRAPH_TAGS]
    if children:
        for c in children:
            text = _flatten_text(c)
            if text:
                paragraphs.append(text)
        return paragraphs
    # Otherwise fall back to the block's full text content split on
    # blank lines (BVerfG inline-HTML case).
    flat = _flatten_text(el)
    if not flat:
        return []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", flat) if c.strip()]
    return chunks or [flat]


def _flatten_text(el: ET.Element) -> str:
    """Collapse mixed-content XML/HTML into plain text with paragraphs."""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = _localname(child.tag).lower()
        if tag in _BLOCK_TAGS:
            continue  # do not re-include nested blocks
        parts.append(_flatten_text(child))
        if child.tail:
            parts.append(child.tail)
        # Inject paragraph breaks for HTML-style line breaks.
        if tag in {"br"}:
            parts.append("\n")
        elif tag in _PARAGRAPH_TAGS:
            parts.append("\n\n")
    text = "".join(parts)
    # Normalise whitespace; preserve paragraph breaks.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _collect_normrefs(root: ET.Element) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for el in root.iter():
        tag = _localname(el.tag).lower()
        if tag in _NORM_TAGS:
            text = (el.text or "").strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return out


def _build_ecli(root: ET.Element) -> str:
    """Synthesise an ECLI when the upstream omits it.

    Pattern: ECLI:DE:<COURT>:<YEAR>:<DATE_DIGITS><CASENO_NORMALISED>
    Both date and case_no are aggressively normalised to ASCII.
    """
    court = _first_text(root, ("gericht",)) or ""
    date = _first_text(root, ("entscheidungsdatum",)) or ""
    case_no = _first_text(root, ("aktenzeichen",)) or ""
    if not (court and date and case_no):
        return ""
    iso = _normalise_date(date)
    digits = iso.replace("-", "")[2:]  # YYMMDD
    no = re.sub(r"[^A-Za-z0-9]", "", case_no)
    return f"ECLI:DE:{court.upper()}:{iso[:4]}:{digits}{no}"


def _normalise_date(text: str) -> str:
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return text


def _localname(tag: str) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


__all__ = ["parse_decision_xml", "DecisionDoc"]
