from __future__ import annotations

from ..canonical import canonicalize_text
from ..parse import ParsedSection

_FRONTMATTER_ORDER = [
    "schema_version",
    "bjnr",
    "jurabk",
    "type",
    "number",
    "heading",
    "breadcrumb",
    "stand_datum",
    "source_xml",
]

_NEEDS_QUOTE = set('":{}[],&*#?|-<>=!%@`')


def _yaml_scalar(value: str) -> str:
    if value == "":
        return '""'
    if any(ch in _NEEDS_QUOTE for ch in value) or value[0] == "§" or value[0].isspace():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _render_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _FRONTMATTER_ORDER:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(str(item))}")
        elif value is None:
            lines.append(f"{key}: null")
        else:
            lines.append(f"{key}: {_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def render_section_markdown(
    *,
    schema_version: str,
    bjnr: str,
    jurabk: str | None,
    section: ParsedSection,
    stand_datum: str | None,
) -> str:
    frontmatter = {
        "schema_version": schema_version,
        "bjnr": bjnr,
        "jurabk": jurabk or "",
        "type": section.kind,
        "number": section.number,
        "heading": canonicalize_text(section.heading),
        "breadcrumb": [canonicalize_text(b) for b in section.breadcrumb],
        "stand_datum": stand_datum or "",
        "source_xml": "source.xml",
    }

    header_heading = canonicalize_text(section.heading)
    header_line = f"# {section.number}"
    if header_heading:
        header_line = f"# {section.number} {header_heading}"

    body_parts = [_render_frontmatter(frontmatter), "", header_line, ""]
    if section.absaetze:
        for a in section.absaetze:
            body_parts.append(f"({a.absatz}) {a.text}")
            body_parts.append("")
    else:
        body_parts.append("")
    body = "\n".join(body_parts).rstrip() + "\n"
    return body
