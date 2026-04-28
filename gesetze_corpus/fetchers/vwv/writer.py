"""Markdown renderer and on-disk writer for Bundes-Verwaltungsvorschriften.

The data repo layout mirrors gesetze-corpus-data: each VwV becomes a
folder under `laws/<short_slug>/` with:

  meta.json            -- canonical metadata (short, title, url,
                          promulgation_date, section_count, hash)
  sections/<id>.md     -- one Markdown file per leaf section,
                          frontmatter + body

Sections are ordered by zero-padded decimal: "1.", "1.1", "1.10",
"2." => "01", "01.01", "01.10", "02". This keeps directory listings
in the same order as the upstream document and avoids the "1.10 sorts
before 1.2" trap.

The writer is idempotent: it computes a body hash and rewrites only
when the hash changes. Callers can compose this with the existing
events/writer.py to record promulgation events.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ... import SCHEMA_VERSION, TOOLING_ID
from ...util.slugs import slugify_ascii
from .detail import VwVDocument, VwVSection


@dataclass
class WriteResult:
    short: str
    slug: str
    written: list[str]
    unchanged: list[str]
    deleted: list[str]


def render_section_markdown(short: str, section: VwVSection) -> str:
    """Render a single section to Markdown with YAML frontmatter."""
    fm = {
        "schema_version": SCHEMA_VERSION,
        "source": "vwv",
        "short": short,
        "ordinal": section.ordinal,
        "ordinal_padded": _pad_ordinal(section.ordinal),
        "heading": section.heading or "",
    }
    body_lines = [_yaml_block(fm)]
    if section.heading:
        body_lines.append(f"# {section.ordinal} {section.heading}".strip())
    else:
        body_lines.append(f"# {section.ordinal}")
    body_lines.append("")
    body_lines.append((section.text or "").strip())
    return "\n".join(body_lines).rstrip() + "\n"


def write_vwv(document: VwVDocument, *, data_repo: Path) -> WriteResult:
    """Persist a VwV document to the data repo. Returns a WriteResult."""
    if not document.short:
        raise ValueError("VwVDocument.short is required for writing")

    slug = slugify_ascii(document.short) or slugify_ascii(document.title) or "unnamed"
    base = Path(data_repo) / "laws" / slug
    sections_dir = base / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    unchanged: list[str] = []
    expected: set[str] = set()

    for section in document.sections:
        filename = f"{_pad_ordinal(section.ordinal)}.md"
        expected.add(filename)
        target = sections_dir / filename
        new_body = render_section_markdown(document.short, section)
        if target.exists() and target.read_text(encoding="utf-8") == new_body:
            unchanged.append(filename)
            continue
        target.write_text(new_body, encoding="utf-8")
        written.append(filename)

    deleted: list[str] = []
    for existing in sorted(p.name for p in sections_dir.glob("*.md")):
        if existing not in expected:
            (sections_dir / existing).unlink()
            deleted.append(existing)

    meta_path = base / "meta.json"
    meta_payload = _meta_payload(document, slug=slug)
    meta_text = json.dumps(meta_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if not meta_path.exists() or meta_path.read_text(encoding="utf-8") != meta_text:
        meta_path.write_text(meta_text, encoding="utf-8")
        written.append("meta.json")
    else:
        unchanged.append("meta.json")

    return WriteResult(
        short=document.short,
        slug=slug,
        written=written,
        unchanged=unchanged,
        deleted=deleted,
    )


def _meta_payload(document: VwVDocument, *, slug: str) -> dict:
    digest = hashlib.sha256()
    for s in document.sections:
        digest.update(s.ordinal.encode("utf-8"))
        digest.update(b"\x00")
        digest.update((s.text or "").encode("utf-8"))
        digest.update(b"\x00")
    return {
        "schema_version": SCHEMA_VERSION,
        "tooling_version": TOOLING_ID,
        "source": "vwv",
        "short": document.short,
        "slug": slug,
        "title": document.title,
        "url": document.url,
        "promulgation_date": document.promulgation_date,
        "section_count": len(document.sections),
        "content_sha256": digest.hexdigest(),
        "warnings": list(document.warnings),
    }


def _pad_ordinal(ordinal: str) -> str:
    parts = [p for p in ordinal.split(".") if p]
    return ".".join(f"{int(p):02d}" if p.isdigit() else p for p in parts)


def _yaml_block(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(str(item))}")
        else:
            lines.append(f"{key}: {_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_scalar(text: str) -> str:
    if not text:
        return '""'
    needs = any(c in text for c in ':"\\#') or text[0] in (" ", "-", "?", "[", "{")
    if needs:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


# Re-export for convenience
__all__ = ["render_section_markdown", "write_vwv", "WriteResult", "asdict"]
