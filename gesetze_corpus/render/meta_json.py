from __future__ import annotations

from datetime import datetime, timezone

from ..canonical import canonicalize_text
from ..parse import ParsedLaw
from .. import SCHEMA_VERSION, TOOLING_ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def build_meta_json(
    law: ParsedLaw,
    *,
    gii_slug: str,
    zip_url: str,
    html_url: str,
    source_xml_sha256: str,
) -> dict:
    return {
        "ausfertigung_datum": law.ausfertigung_datum,
        "amtabk": law.amtabk,
        "bjnr": law.bjnr,
        "eli": None,
        "gii_slug": gii_slug,
        "ingested_at": _now_iso(),
        "jurabk": law.jurabk,
        "schema_version": SCHEMA_VERSION,
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
