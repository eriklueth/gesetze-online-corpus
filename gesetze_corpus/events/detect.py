"""Detect event groups from the current git working tree of the data repo.

Algorithm:

1. Read ``git status --porcelain`` to get the set of modified, added or
   deleted paths in the data repo.
2. Collect paths that sit under ``laws/<BJNR>/...`` and group them by
   BJNR, preserving the git status code for each path.
3. For each BJNR, read the currently rendered ``meta.json`` to obtain
   ``stand_datum``, ``jurabk``, ``title`` and ``source_xml_sha256``.
   If ``stand_datum`` is missing, fall back to today in UTC.
4. Optionally load the previous ``sources/current/gii-index.json`` (from
   the ``HEAD`` tree) to record the prior sha256 per law.
5. Produce one :class:`DetectedEventGroup` per distinct effective_date.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .schema import AffectedLaw, DetectedEventGroup

# Map git status codes to semantic change buckets. We look at either the
# index ('X') or working tree ('Y') column being non-space.
_ADDED_CODES = {"A", "?"}
_DELETED_CODES = {"D"}


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def _changed_paths_with_status(data_repo: Path) -> list[tuple[str, str]]:
    """Return ``[(status, path), ...]``.

    ``status`` is a single-letter code: ``A`` for added/untracked, ``M``
    for modified, ``D`` for deleted, ``R`` for rename target. Rename
    sources are emitted separately with ``D``.
    """
    out = _run_git(
        ["status", "--porcelain", "--untracked-files=all"], data_repo
    )
    result: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line:
            continue
        xy = line[:2]
        rest = line[3:].strip()
        x, y = xy[0], xy[1]
        if xy.startswith("R"):
            before, _, after = rest.partition(" -> ")
            before = before.strip().strip('"').replace("\\", "/")
            after = after.strip().strip('"').replace("\\", "/")
            result.append(("D", before))
            result.append(("A", after))
            continue
        path = rest.strip('"').replace("\\", "/")
        if x in _DELETED_CODES or y in _DELETED_CODES:
            code = "D"
        elif x in _ADDED_CODES or y in _ADDED_CODES:
            code = "A"
        else:
            code = "M"
        result.append((code, path))
    return result


def _load_head_index(data_repo: Path) -> dict:
    try:
        out = _run_git(
            ["show", "HEAD:sources/current/gii-index.json"], data_repo
        )
    except subprocess.CalledProcessError:
        return {}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    return data.get("laws") or {}


def _file_path_to_label(rel_path: str) -> str:
    """Convert ``laws/<BJNR>/paragraphs/0007g.md`` -> ``§ 7g`` (and siblings)."""
    parts = rel_path.split("/")
    if len(parts) < 4 or not parts[-1].endswith(".md"):
        return rel_path
    sub = parts[2]
    stem = parts[-1][:-3]
    stem = stem.split("__", 1)[0]
    if sub == "paragraphs":
        if stem.startswith("art-"):
            core = stem[4:]
            num = core[:4].lstrip("0") or "0"
            suf = core[4:]
            return f"Artikel {num}{suf}".rstrip()
        num = stem[:4].lstrip("0") or "0"
        suf = stem[4:]
        return f"§ {num}{suf}".rstrip()
    if sub == "annexes":
        num = stem[:4].lstrip("0") or "0"
        suf = stem[4:]
        if num == "0" and not suf:
            return "Anlage"
        return f"Anlage {num}{suf}".rstrip()
    return rel_path


def detect_event_groups(data_repo: Path) -> list[DetectedEventGroup]:
    status_entries = _changed_paths_with_status(data_repo)

    # {bjnr -> {"A": [paths], "M": [paths], "D": [paths]}}
    law_paths: dict[str, dict[str, list[str]]] = {}
    for status, p in status_entries:
        if not p.startswith("laws/"):
            continue
        parts = p.split("/")
        if len(parts) < 2:
            continue
        bjnr = parts[1]
        bucket = law_paths.setdefault(bjnr, {"A": [], "M": [], "D": []})
        bucket[status].append(p)

    if not law_paths:
        return []

    previous_index = _load_head_index(data_repo)
    prev_sha_by_bjnr = {
        entry["bjnr"]: entry.get("source_xml_sha256")
        for entry in previous_index.values()
        if "bjnr" in entry
    }

    today = datetime.now(UTC).date().isoformat()
    groups: dict[str, DetectedEventGroup] = {}

    for bjnr, buckets in sorted(law_paths.items()):
        meta_path = data_repo / "laws" / bjnr / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        stand_datum = meta.get("stand_datum") or today
        sha_after = (meta.get("source_hashes") or {}).get(
            "source_xml_sha256"
        ) or ""

        section_paths_added = [
            p
            for p in buckets["A"]
            if p.endswith(".md")
            and ("/paragraphs/" in p or "/annexes/" in p)
        ]
        section_paths_modified = [
            p
            for p in buckets["M"]
            if p.endswith(".md")
            and ("/paragraphs/" in p or "/annexes/" in p)
        ]
        section_paths_removed = [
            p
            for p in buckets["D"]
            if p.endswith(".md")
            and ("/paragraphs/" in p or "/annexes/" in p)
        ]

        all_changed = sorted(buckets["A"] + buckets["M"] + buckets["D"])

        affected = AffectedLaw(
            bjnr=bjnr,
            jurabk=meta.get("jurabk"),
            title=meta.get("title") or bjnr,
            stand_datum=meta.get("stand_datum"),
            source_xml_sha256_before=prev_sha_by_bjnr.get(bjnr),
            source_xml_sha256_after=sha_after,
            changed_paths=all_changed,
            sections_added=sorted(
                _file_path_to_label(p) for p in section_paths_added
            ),
            sections_modified=sorted(
                _file_path_to_label(p) for p in section_paths_modified
            ),
            sections_removed=sorted(
                _file_path_to_label(p) for p in section_paths_removed
            ),
        )

        group = groups.setdefault(
            stand_datum, DetectedEventGroup(effective_date=stand_datum)
        )
        group.laws.append(affected)

    return [groups[d] for d in sorted(groups.keys())]
