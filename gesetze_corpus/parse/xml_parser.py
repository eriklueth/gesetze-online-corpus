"""Parse a canonicalized GII law XML into a structured representation.

The GII XML is sequential: one ``<norm>`` element per unit. A unit is
either the Stammgesetz head (holding law-level metadata), a gliederung
header (Teil, Abschnitt, Titel, ...) which only contributes to the
current breadcrumb stack, a paragraph (``§`` / ``Art``) or an annex
(``Anlage``). Norms without textdaten are treated as headers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from lxml import etree

from ..canonical import canonicalize_paragraph, canonicalize_text
from ..util.slugs import classify_enbez

_ABSATZ_PREFIX_RE = re.compile(r"^\s*\(\s*(\d+[a-zA-Z]?)\s*\)\s*")


@dataclass
class ParsedAbsatz:
    absatz: str
    text: str


@dataclass
class ParsedSection:
    kind: str
    number: str
    heading: str
    breadcrumb: list[str]
    absaetze: list[ParsedAbsatz] = field(default_factory=list)


@dataclass
class ParsedLaw:
    bjnr: str
    jurabk: Optional[str]
    amtabk: Optional[str]
    title: str
    ausfertigung_datum: Optional[str]
    stand_datum: Optional[str]
    standangabe: list[dict]
    sections: list[ParsedSection]


def _first_text(elem: etree._Element | None, xpath: str) -> str | None:
    if elem is None:
        return None
    nodes = elem.xpath(xpath)
    if not nodes:
        return None
    node = nodes[0]
    if isinstance(node, etree._Element):
        raw = "".join(node.itertext())
    else:
        raw = str(node)
    return canonicalize_text(raw) or None


def _extract_standangabe(metadaten: etree._Element) -> list[dict]:
    result: list[dict] = []
    for st in metadaten.findall("standangabe"):
        typ = _first_text(st, "standtyp/text()")
        kommentar = _first_text(st, "standkommentar/text()")
        if typ or kommentar:
            result.append({"typ": typ, "kommentar": kommentar})
    return result


def _collect_paragraph_text(text_elem: etree._Element) -> list[ParsedAbsatz]:
    """Extract per-Absatz text out of a ``<text><Content>...</Content></text>`` block.

    Rule: every top-level ``<P>`` under ``<Content>`` is a candidate
    paragraph. If it starts with ``(n)`` we treat that as an explicit
    Absatz id and strip the prefix from the text. Otherwise we number
    implicitly ``1``, ``2``, ... in sequence. Follow-up ``<P>`` without
    a leading ``(n)`` within numbered mode are appended to the previous
    Absatz with a space separator.
    """
    content = text_elem.find("Content")
    if content is None:
        content = text_elem
    absaetze: list[ParsedAbsatz] = []
    seq = 0
    numbered_mode = False

    for p in content.findall("P"):
        for sup in p.findall(".//SUP"):
            parent = sup.getparent()
            if parent is not None:
                parent.remove(sup)
        raw = canonicalize_paragraph("".join(p.itertext()))
        if not raw:
            continue
        seq += 1
        m = _ABSATZ_PREFIX_RE.match(raw)
        if m:
            numbered_mode = True
            body = canonicalize_paragraph(raw[m.end():])
            absaetze.append(ParsedAbsatz(absatz=m.group(1), text=body))
        elif numbered_mode and absaetze:
            absaetze[-1].text = canonicalize_paragraph(absaetze[-1].text + " " + raw)
        else:
            absaetze.append(ParsedAbsatz(absatz=str(seq), text=raw))

    return absaetze


def parse_law_xml(xml_bytes: bytes, bjnr: str) -> ParsedLaw:
    root = etree.fromstring(xml_bytes)

    norms = root.findall(".//norm")
    if not norms:
        raise ValueError("no <norm> elements found")

    head_meta = norms[0].find("metadaten")
    if head_meta is None:
        raise ValueError("first <norm> has no <metadaten>")

    jurabk = _first_text(head_meta, "jurabk/text()")
    amtabk = _first_text(head_meta, "amtabk/text()")
    title = (
        _first_text(head_meta, "langue/text()")
        or _first_text(head_meta, "titel/text()")
        or jurabk
        or bjnr
    )
    ausfertigung = _first_text(head_meta, "ausfertigung-datum/text()")
    standangabe = _extract_standangabe(head_meta)

    stand_datum: str | None = None
    for st in standangabe:
        k = (st.get("kommentar") or "")
        m = re.search(r"(\d{1,2}\.\d{1,2}\.(\d{2,4}))", k)
        if m:
            stand_datum = _normalize_german_date(m.group(1))
            break

    breadcrumb: list[str] = []
    sections: list[ParsedSection] = []

    for norm in norms:
        meta = norm.find("metadaten")
        if meta is None:
            continue
        enbez = _first_text(meta, "enbez/text()")
        titel = _first_text(meta, "titel/text()") or ""
        text_elem = norm.find("textdaten/text[@format='XML']")
        if text_elem is None:
            text_elem = norm.find("textdaten/text")

        gliederung = meta.find("gliederungseinheit")
        if gliederung is not None:
            bez = _first_text(gliederung, "gliederungsbez/text()")
            titel_gl = _first_text(gliederung, "gliederungstitel/text()")
            label_parts = [p for p in [bez, titel_gl] if p]
            if label_parts:
                depth_raw = _first_text(gliederung, "gliederungskennzahl/text()")
                depth = _depth_from_kennzahl(depth_raw)
                if depth is not None:
                    breadcrumb = breadcrumb[:depth]
                breadcrumb.append(" ".join(label_parts))
                if text_elem is None and not enbez:
                    continue

        classified = classify_enbez(enbez or "")
        if not classified:
            continue
        kind, _padded = classified

        if text_elem is None:
            absaetze: list[ParsedAbsatz] = []
        else:
            absaetze = _collect_paragraph_text(text_elem)

        sections.append(
            ParsedSection(
                kind=kind,
                number=canonicalize_text(enbez or ""),
                heading=titel,
                breadcrumb=list(breadcrumb),
                absaetze=absaetze,
            )
        )

    return ParsedLaw(
        bjnr=bjnr,
        jurabk=jurabk,
        amtabk=amtabk,
        title=title or bjnr,
        ausfertigung_datum=ausfertigung,
        stand_datum=stand_datum,
        standangabe=standangabe,
        sections=sections,
    )


def _depth_from_kennzahl(kennzahl: str | None) -> int | None:
    if not kennzahl:
        return None
    digits = re.sub(r"\D", "", kennzahl)
    if not digits:
        return None
    return max(1, len(digits) // 3)


def _normalize_german_date(value: str) -> str | None:
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", value)
    if not m:
        return None
    day, month, year = m.group(1), m.group(2), m.group(3)
    if len(year) == 2:
        year = "19" + year if int(year) >= 50 else "20" + year
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None
