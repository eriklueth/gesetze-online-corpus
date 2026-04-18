from __future__ import annotations

from .. import SCHEMA_VERSION, TOOLING_ID
from ..canonical import canonicalize_text
from ..parse import ParsedLaw


def build_meta_json(
    law: ParsedLaw,
    *,
    gii_slug: str,
    zip_url: str,
    html_url: str,
    source_xml_sha256: str,
) -> dict:
    section_kinds: dict[str, int] = {}
    for s in law.sections:
        section_kinds[s.kind] = section_kinds.get(s.kind, 0) + 1

    return {
        "ausfertigung_datum": law.ausfertigung_datum,
        "amtabk": law.amtabk,
        "bjnr": law.bjnr,
        "eli": None,
        "gii_slug": gii_slug,
        "jurabk": law.jurabk,
        "schema_version": SCHEMA_VERSION,
        "section_counts": section_kinds,
        "source_hashes": {"source_xml_sha256": source_xml_sha256},
        "source_urls": {"gii_html": html_url, "gii_xml_zip": zip_url},
        "stand_datum": law.stand_datum,
        "standangabe": law.standangabe,
        "title": canonicalize_text(law.title),
        "tooling_version": TOOLING_ID,
    }


def build_toc_json(law: ParsedLaw, files_by_index: list[str]) -> dict:
    sections: list[dict] = []
    for idx, section in enumerate(law.sections):
        sections.append(
            {
                "absatz_count": len(section.absaetze),
                "breadcrumb": [canonicalize_text(b) for b in section.breadcrumb],
                "file": files_by_index[idx],
                "heading": canonicalize_text(section.heading),
                "number": canonicalize_text(section.number),
                "type": section.kind,
            }
        )
    return {
        "bjnr": law.bjnr,
        "schema_version": SCHEMA_VERSION,
        "sections": sections,
    }
