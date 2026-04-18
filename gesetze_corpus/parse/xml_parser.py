"""Parse a canonicalized GII law XML into a structured representation.

The GII XML is sequential: one ``<norm>`` element per unit. A unit is
either the Stammgesetz head (holding law-level metadata), a gliederung
header (Teil, Abschnitt, Titel, ...) which only contributes to the
current breadcrumb stack, a paragraph (``§`` / ``Art``) or an annex
(``Anlage``). Norms without textdaten are treated as headers.

Paragraph body handling (schema v2)
-----------------------------------

Each ``<P>`` element is one *Absatz* and can contain:

- a leading ``(N) `` prefix in ``p.text`` that identifies the Absatz,
- ``<SUP class="Rec">N</SUP>`` markers that split the Absatz into
  numbered *Saetze*,
- inline ``<DL>``/``<table>`` block-like structures that belong to
  the currently active Satz.

We preserve the Satz segmentation in the parsed model so downstream
tooling can index per-Satz and the Markdown renderer can emit
``<sup>N</sup>`` markers for readability. When no SUP markers are
present, the whole Absatz becomes a single Satz with ``nummer=1``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from ..canonical import canonicalize_paragraph, canonicalize_text
from ..util.slugs import classify_enbez

_ABSATZ_PREFIX_RE = re.compile(r"^\s*\(\s*(\d+[a-zA-Z]?)\s*\)\s*")


@dataclass
class ParsedSatz:
    nummer: int
    text: str


@dataclass
class ParsedAbsatz:
    absatz: str
    intro: str = ""
    saetze: list[ParsedSatz] = field(default_factory=list)


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
    jurabk: str | None
    amtabk: str | None
    title: str
    ausfertigung_datum: str | None
    stand_datum: str | None
    standangabe: list[dict]
    sections: list[ParsedSection]


def _all_text(elem: etree._Element) -> str:
    """Concatenate all descendant text. Casts to str to satisfy lxml-stubs."""
    return "".join(str(t) for t in elem.itertext())


def _first_text(elem: etree._Element | None, xpath: str) -> str | None:
    if elem is None:
        return None
    nodes = elem.xpath(xpath)
    if not isinstance(nodes, list) or not nodes:
        return None
    node = nodes[0]
    if isinstance(node, etree._Element):
        raw = _all_text(node)
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


# ---------------------------------------------------------------------------
# Inline rendering of GII markup to Markdown
# ---------------------------------------------------------------------------


def _render_element(elem: etree._Element) -> str:
    """Render one XML subtree to a Markdown-ish string.

    The output goes through :func:`canonicalize_paragraph` afterwards, so
    all internal whitespace is collapsed. That means block structures have
    to be encoded with visible punctuation rather than newlines.
    """
    tag = elem.tag
    if tag == "BR":
        return " "
    if tag == "DL":
        return _render_dl(elem)
    if tag == "table":
        return _render_table(elem)
    if tag in ("I", "IN"):
        return "*" + _all_text(elem) + "*"
    if tag in ("B", "F"):
        return "**" + _all_text(elem) + "**"
    if tag == "SUP" and elem.get("class") == "Rec":
        return ""
    return _render_element_content(elem)


def _render_element_content(elem: etree._Element) -> str:
    """Recurse over the children of ``elem`` keeping inline text flow."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_render_element(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _render_dl(dl_elem: etree._Element) -> str:
    """Render ``<DL><DT>m</DT><DD>body</DD>...</DL>`` as an inline list.

    Since the containing Absatz is rendered as a single Markdown line,
    we cannot emit real list items. Instead we keep the original DT
    markers (``1.``, ``a)``, ...) with a space before the body so the
    result reads close to the amtliche Fassung:

        "wenn 1. der Gewinn a) nach § 4 ermittelt wird, b) ..."
    """
    pairs: list[tuple[str, etree._Element]] = []
    current_dt: str | None = None
    for child in dl_elem:
        if child.tag == "DT":
            current_dt = canonicalize_text(_all_text(child)).strip()
        elif child.tag == "DD":
            pairs.append((current_dt or "", child))
            current_dt = None
    rendered_items: list[str] = []
    for marker, dd in pairs:
        body = _render_element_content(dd).strip()
        if marker and body:
            rendered_items.append(f"{marker} {body}")
        elif body:
            rendered_items.append(body)
        elif marker:
            rendered_items.append(marker)
    if not rendered_items:
        return " "
    return " " + " ".join(rendered_items) + " "


def _render_table(table_elem: etree._Element) -> str:
    """Render a ``<table>`` compactly inside an Absatz.

    Real Markdown tables require newlines which our single-line Absatz
    format does not allow. The compromise: ``[c1 | c2 | ...; c1 | c2 ...]``.
    Enough for grep-style search; full-blown tables need a future block
    renderer.
    """
    rows_out: list[str] = []
    for row in table_elem.iter("row"):
        cells: list[str] = []
        for entry in row.findall("entry"):
            txt = canonicalize_text(_all_text(entry)).strip()
            cells.append(txt)
        if any(cells):
            rows_out.append(" | ".join(cells))
    if not rows_out:
        return " "
    return " [" + "; ".join(rows_out) + "] "


# ---------------------------------------------------------------------------
# Absatz / Satz extraction
# ---------------------------------------------------------------------------


def _split_p_into_saetze(
    p_elem: etree._Element,
) -> tuple[str, list[ParsedSatz]]:
    """Walk a <P> in document order and split at SUP[@class='Rec'] markers.

    Returns ``(intro, saetze)``. ``intro`` is the text before the first
    SUP marker (usually only the ``(N) `` Absatz prefix, stripped later
    by the caller). ``saetze`` lists numbered Saetze.
    """
    saetze: list[ParsedSatz] = []
    intro_parts: list[str] = []
    current_nr: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current_nr is not None:
            text = canonicalize_paragraph("".join(buffer))
            if text:
                saetze.append(ParsedSatz(nummer=current_nr, text=text))
        buffer = []

    if p_elem.text:
        intro_parts.append(p_elem.text)

    for child in p_elem:
        is_satz_marker = child.tag == "SUP" and child.get("class") == "Rec"
        if is_satz_marker:
            if current_nr is not None:
                flush()
            try:
                current_nr = int((child.text or "").strip())
            except ValueError:
                current_nr = (current_nr or 0) + 1
            if child.tail:
                buffer.append(child.tail)
        else:
            rendered = _render_element(child)
            if current_nr is None:
                intro_parts.append(rendered)
                if child.tail:
                    intro_parts.append(child.tail)
            else:
                buffer.append(rendered)
                if child.tail:
                    buffer.append(child.tail)

    flush()
    intro = canonicalize_paragraph("".join(intro_parts))
    return intro, saetze


def _render_whole_p(p_elem: etree._Element) -> str:
    """Render the full <P> content as a single canonicalized line."""
    return canonicalize_paragraph(_render_element_content(p_elem))


def _collect_paragraph_absaetze(
    text_elem: etree._Element,
) -> list[ParsedAbsatz]:
    """Extract structured Absaetze out of a <text><Content>...</Content>.

    Rule:
    - Each top-level ``<P>`` is a candidate Absatz.
    - Absatz id is detected from the leading ``(N) `` prefix; otherwise
      we number implicitly ``1``, ``2``, ...
    - Inside a ``<P>`` with SUP[@class='Rec'] markers, the Absatz is
      split into Saetze. Otherwise the whole Absatz is one Satz with
      ``nummer=1``.
    - An unnumbered follow-up ``<P>`` in numbered mode appends its
      Saetze to the previous Absatz (continuing the Satz numbering).
    """
    content = text_elem.find("Content")
    if content is None:
        content = text_elem
    absaetze: list[ParsedAbsatz] = []
    implicit_seq = 0
    numbered_mode = False

    for p in content.findall("P"):
        has_markers = any(
            (s.tag == "SUP" and s.get("class") == "Rec") for s in p.iter("SUP")
        )

        if has_markers:
            intro, saetze = _split_p_into_saetze(p)
        else:
            whole = _render_whole_p(p)
            intro = ""
            saetze = [ParsedSatz(nummer=1, text=whole)] if whole else []

        if not intro and not saetze:
            continue

        full_head = intro or (saetze[0].text if saetze else "")
        m = _ABSATZ_PREFIX_RE.match(full_head)
        if m:
            numbered_mode = True
            absatz_id = m.group(1)
            prefix_len = m.end()
            if intro:
                intro = intro[prefix_len:].lstrip()
            elif saetze:
                stripped = saetze[0].text[prefix_len:].lstrip()
                saetze[0] = ParsedSatz(nummer=saetze[0].nummer, text=stripped)
            absaetze.append(
                ParsedAbsatz(absatz=absatz_id, intro=intro, saetze=saetze)
            )
        elif numbered_mode and absaetze:
            prev = absaetze[-1]
            last_nr = prev.saetze[-1].nummer if prev.saetze else 0
            if intro:
                if prev.saetze:
                    prev.saetze[-1] = ParsedSatz(
                        nummer=prev.saetze[-1].nummer,
                        text=canonicalize_paragraph(
                            prev.saetze[-1].text + " " + intro
                        ),
                    )
                else:
                    prev.intro = canonicalize_paragraph(
                        (prev.intro + " " + intro).strip()
                    )
            for s in saetze:
                last_nr = max(last_nr + 1, s.nummer)
                prev.saetze.append(ParsedSatz(nummer=last_nr, text=s.text))
        else:
            implicit_seq += 1
            absaetze.append(
                ParsedAbsatz(
                    absatz=str(implicit_seq), intro=intro, saetze=saetze
                )
            )

    return absaetze


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


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
        k = st.get("kommentar") or ""
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
                depth_raw = _first_text(
                    gliederung, "gliederungskennzahl/text()"
                )
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
            absaetze = _collect_paragraph_absaetze(text_elem)

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
