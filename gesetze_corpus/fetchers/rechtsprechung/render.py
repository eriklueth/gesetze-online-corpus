"""Markdown renderer for court decisions (scaffold).

Produces the shape used by `rechtsprechung-corpus-data`:

    decisions/<ECLI>/
        meta.json     # court, date, case_no, decision_type, normrefs, sha256
        decision.xml  # canonicalized upstream XML
        decision.md   # rendered leitsatz + gruende + tenor

Not yet wired into a writer. The XML parser for the upstream decision
schema is the next step; until then, only `render_stub` exists so the
repo scaffold and unit tests can be exercised.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DecisionDoc:
    ecli: str
    court: str
    date: str
    case_no: str
    decision_type: str  # "Urteil" | "Beschluss" | "Versaeumnisurteil" | ...
    leitsaetze: list[str] = field(default_factory=list)
    tenor: list[str] = field(default_factory=list)
    gruende: list[str] = field(default_factory=list)
    normrefs: list[str] = field(default_factory=list)  # e.g. ["§ 823 BGB", "Art. 2 GG"]


def render_stub(doc: DecisionDoc) -> str:
    """Very small reference renderer used by tests.

    Production renderer will be substantially more opinionated about
    canonicalization (no trailing whitespace, consistent quote marks,
    stable footnote handling, etc.).
    """
    lines: list[str] = []
    lines.append("---")
    lines.append("schema_version: v1")
    lines.append(f"ecli: {doc.ecli}")
    lines.append(f"court: {doc.court}")
    lines.append(f"date: {doc.date}")
    lines.append(f'case_no: "{doc.case_no}"')
    lines.append(f"decision_type: {doc.decision_type}")
    if doc.normrefs:
        lines.append("normrefs:")
        for ref in doc.normrefs:
            lines.append(f'  - "{ref}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# {doc.court} {doc.case_no} — {doc.decision_type}")
    lines.append("")
    if doc.leitsaetze:
        lines.append("## Leitsätze")
        lines.append("")
        for i, ls in enumerate(doc.leitsaetze, 1):
            lines.append(f"{i}. {ls}")
        lines.append("")
    if doc.tenor:
        lines.append("## Tenor")
        lines.append("")
        for t in doc.tenor:
            lines.append(t)
        lines.append("")
    if doc.gruende:
        lines.append("## Gründe")
        lines.append("")
        for g in doc.gruende:
            lines.append(g)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
