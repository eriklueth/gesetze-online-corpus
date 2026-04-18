"""Build derived artefacts from the data repo.

Three outputs:

1. ``derived/by-jurabk.json`` — ``{jurabk: bjnr, ...}`` (small, in-repo).
2. ``derived/by-bjnr.json`` — ``{bjnr: {jurabk, title, gii_slug, ...}}``
   (medium, in-repo).
3. ``<out_path>`` (default ``corpus.jsonl``) — one JSON line per rendered
   Markdown section. Large, written outside the repo by default.

The in-repo artefacts are canonicalized so they produce stable diffs; the
jsonl output is sorted by (bjnr, file) and newline-terminated.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..canonical import canonicalize_json_dump

log = logging.getLogger(__name__)


@dataclass
class ExportReport:
    laws: int
    sections: int
    by_jurabk_path: Path
    by_bjnr_path: Path
    corpus_path: Path


def _strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return ``(frontmatter_dict, body)`` parsed from a Markdown file.

    Only string / list-of-string scalars are honoured; that is all our
    renderer emits. Anything unexpected falls back to an empty dict.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    header = text[4:end]
    body = text[end + 5:]
    fm: dict[str, str] = {}
    current_list_key: str | None = None
    for line in header.splitlines():
        if not line:
            continue
        if line.startswith("  - ") and current_list_key is not None:
            fm.setdefault(current_list_key + "_list", [])  # type: ignore[arg-type]
            fm[current_list_key + "_list"].append(_yaml_unquote(line[4:]))  # type: ignore[union-attr]
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                current_list_key = key
                fm[key + "_list"] = []  # type: ignore[assignment]
            else:
                current_list_key = None
                fm[key] = _yaml_unquote(value)
    return fm, body


def _yaml_unquote(value: str) -> str:
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _iter_section_files(law_dir: Path):
    for sub in ("paragraphs", "annexes"):
        d = law_dir / sub
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix == ".md" and f.is_file():
                yield f


def export_all(
    data_repo: Path,
    *,
    corpus_path: Path | None = None,
) -> ExportReport:
    derived_dir = data_repo / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    by_jurabk: dict[str, str] = {}
    by_bjnr: dict[str, dict] = {}

    corpus_out = corpus_path or (data_repo / "derived" / "corpus.jsonl")
    corpus_out.parent.mkdir(parents=True, exist_ok=True)

    section_count = 0
    laws_dir = data_repo / "laws"

    with corpus_out.open("w", encoding="utf-8", newline="\n") as out_fh:
        if not laws_dir.exists():
            report = ExportReport(
                laws=0,
                sections=0,
                by_jurabk_path=derived_dir / "by-jurabk.json",
                by_bjnr_path=derived_dir / "by-bjnr.json",
                corpus_path=corpus_out,
            )
            (derived_dir / "by-jurabk.json").write_bytes(
                canonicalize_json_dump({}).encode("utf-8")
            )
            (derived_dir / "by-bjnr.json").write_bytes(
                canonicalize_json_dump({}).encode("utf-8")
            )
            return report

        for law_dir in sorted(laws_dir.iterdir()):
            if not law_dir.is_dir():
                continue
            bjnr = law_dir.name
            meta_path = law_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("bad meta.json for %s", bjnr)
                continue

            jurabk = meta.get("jurabk") or ""
            title = meta.get("title") or bjnr
            if jurabk:
                by_jurabk.setdefault(jurabk, bjnr)
            by_bjnr[bjnr] = {
                "gii_slug": meta.get("gii_slug"),
                "jurabk": jurabk or None,
                "section_counts": meta.get("section_counts") or {},
                "stand_datum": meta.get("stand_datum"),
                "title": title,
            }

            for section_file in _iter_section_files(law_dir):
                try:
                    text = section_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                fm, body = _strip_frontmatter(text)
                rel = section_file.relative_to(data_repo).as_posix()
                body = body.strip()
                record = {
                    "bjnr": bjnr,
                    "breadcrumb": fm.get("breadcrumb_list") or [],
                    "heading": fm.get("heading", ""),
                    "jurabk": jurabk or None,
                    "number": fm.get("number", ""),
                    "path": rel,
                    "stand_datum": meta.get("stand_datum"),
                    "text": body,
                    "title": title,
                    "type": fm.get("type", ""),
                }
                out_fh.write(
                    json.dumps(record, ensure_ascii=False, sort_keys=True)
                    + "\n"
                )
                section_count += 1

    (derived_dir / "by-jurabk.json").write_bytes(
        canonicalize_json_dump(dict(sorted(by_jurabk.items()))).encode("utf-8")
    )
    (derived_dir / "by-bjnr.json").write_bytes(
        canonicalize_json_dump(dict(sorted(by_bjnr.items()))).encode("utf-8")
    )

    readme_path = data_repo / "README.md"
    readme_path.write_bytes(
        _render_readme(
            laws=len(by_bjnr),
            sections=section_count,
            corpus_out=corpus_out,
            data_repo=data_repo,
        ).encode("utf-8")
    )

    return ExportReport(
        laws=len(by_bjnr),
        sections=section_count,
        by_jurabk_path=derived_dir / "by-jurabk.json",
        by_bjnr_path=derived_dir / "by-bjnr.json",
        corpus_path=corpus_out,
    )


def _render_readme(
    *, laws: int, sections: int, corpus_out: Path, data_repo: Path
) -> str:
    corpus_size_mb: str
    try:
        corpus_size_mb = f"{corpus_out.stat().st_size / (1024 * 1024):.1f}"
    except OSError:
        corpus_size_mb = "?"
    in_repo = (
        corpus_out.is_relative_to(data_repo)
        if hasattr(corpus_out, "is_relative_to")
        else False
    )
    corpus_rel = (
        corpus_out.relative_to(data_repo).as_posix() if in_repo else str(corpus_out)
    )
    updated = datetime.now(UTC).date().isoformat()

    return f"""# gesetze-corpus-data

Versioned Markdown corpus of German federal law, derived from
[gesetze-im-internet.de](https://www.gesetze-im-internet.de). One
commit per effective date, backdated to the juristische Inkrafttretens-
reihenfolge wherever the upstream metadata allows it.

## Stats

- Laws: **{laws}**
- Sections (§ / Art. / Anlage): **{sections}**
- corpus.jsonl: **{corpus_size_mb} MB** (`{corpus_rel}`)
- Last export: **{updated}** UTC
- Schema version: **v2**

## Layout

```
laws/<BJNR>/
    meta.json           # law-level metadata, sha256 of source.xml
    toc.json            # ordered section list with file pointers
    source.xml          # canonicalized GII XML (c14n2)
    paragraphs/<NNNN[x]>.md
    annexes/<NNNN[x]>.md

events/<YYYY>/<event_id>.json
    # one file per event group, with per-section A/M/D deltas

sources/current/gii-index.json
    # sha256 per law slug, for diffing between snapshots

derived/                # regenerated by `gesetze-corpus export`
    by-jurabk.json      # {{jurabk: bjnr}}
    by-bjnr.json        # {{bjnr: {{jurabk, title, stand_datum, section_counts}}}}
    corpus.jsonl        # one JSON line per rendered section
```

## Queries

Find a law's BJNR by its jurabk:

```bash
jq -r '."EStG"' derived/by-jurabk.json
```

Get the git history of § 7g EStG:

```bash
git log --follow --oneline -- laws/BJNR010050934/paragraphs/0007g.md
```

List every commit on a given effective date:

```bash
git log --since=2026-04-01 --until=2026-04-10 --oneline
```

Grep the full corpus:

```bash
jq -r 'select(.text | test("Investitionsabzug")) | [.jurabk, .number] | @tsv' \\
    derived/corpus.jsonl
```

## Licence

The statutory text is in the public domain (§ 5 UrhG). Structure and
metadata in this repo are released under CC0-1.0 — see `LICENSE`.

## Tooling

Pipeline lives at
[gesetze-online-corpus](https://github.com/) — this data repo contains
**only data**, never code.
"""

