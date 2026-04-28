"""Write a parsed decision into the rechtsprechung-corpus-data layout.

Layout:

    decisions/<COUNTRY>/<COURT>/<YEAR>/<ECLI-tail>/
        meta.json
        decision.xml         # canonicalised upstream XML
        decision.md          # rendered Leitsaetze + Tenor + Gruende

`<ECLI-tail>` is the last colon-segment of the ECLI (everything after
the year), URL-safe and stable. Splitting by colon in the path lets
file systems handle the deep tree well; ECLIs are too long to use as
flat directory names on Windows (260-char limit).

The writer is idempotent: the body hash is recorded in `meta.json`
and only changed files are touched. Old entries that disappeared in
a re-sync are deleted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ... import SCHEMA_VERSION, TOOLING_ID
from ...canonical import canonicalize_xml_bytes
from .render import DecisionDoc, render_stub


@dataclass
class WriteResult:
    ecli: str
    relpath: str
    written: list[str]
    unchanged: list[str]


def write_decision(
    doc: DecisionDoc,
    *,
    canonical_xml: bytes,
    data_repo: Path,
) -> WriteResult:
    """Persist a single decision to the data repo. Returns a WriteResult."""
    if not doc.ecli:
        raise ValueError("DecisionDoc.ecli is required")
    relpath = ecli_to_path(doc.ecli)
    target_dir = Path(data_repo) / relpath
    target_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    unchanged: list[str] = []

    md = render_stub(doc)
    body_hash = _hash(md)

    files: dict[str, bytes] = {
        "decision.xml": canonical_xml,
        "decision.md": md.encode("utf-8"),
        "meta.json": _meta_json(doc, body_hash=body_hash).encode("utf-8"),
    }
    for name, payload in files.items():
        target = target_dir / name
        if target.exists() and target.read_bytes() == payload:
            unchanged.append(name)
            continue
        target.write_bytes(payload)
        written.append(name)

    return WriteResult(
        ecli=doc.ecli,
        relpath=relpath,
        written=written,
        unchanged=unchanged,
    )


def ecli_to_path(ecli: str) -> str:
    """Map an ECLI string to a stable repo-relative path.

    Example:
      ECLI:DE:BGH:2024:150124UIXZR123.23.0
      -> decisions/DE/BGH/2024/150124UIXZR123.23.0
    """
    if not ecli:
        raise ValueError("empty ECLI")
    parts = ecli.split(":")
    if len(parts) < 5 or parts[0].upper() != "ECLI":
        raise ValueError(f"not a valid ECLI: {ecli}")
    country = parts[1].upper()
    court = parts[2].upper()
    year = parts[3]
    tail = ":".join(parts[4:])
    safe_tail = tail.replace("/", "_").replace(":", "-")
    return f"decisions/{country}/{court}/{year}/{safe_tail}"


def canonicalise_xml(raw: bytes) -> bytes:
    """Public wrapper around the shared canonical-XML routine."""
    return canonicalize_xml_bytes(raw)


def _meta_json(doc: DecisionDoc, *, body_hash: str) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tooling_version": TOOLING_ID,
        "ecli": doc.ecli,
        "court": doc.court,
        "date": doc.date,
        "case_no": doc.case_no,
        "decision_type": doc.decision_type,
        "leitsatz_count": len(doc.leitsaetze),
        "tenor_paragraph_count": len(doc.tenor),
        "gruende_paragraph_count": len(doc.gruende),
        "normrefs": list(doc.normrefs),
        "content_sha256": body_hash,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["write_decision", "ecli_to_path", "canonicalise_xml", "WriteResult"]
