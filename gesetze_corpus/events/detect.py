"""Detect event groups from the current git working tree of the data repo.

Algorithm:

1. Read ``git status --porcelain`` to get the set of modified or new
   paths in the data repo.
2. Collect paths that sit under ``laws/<BJNR>/...`` and group them by
   BJNR.
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
from datetime import datetime, timezone
from pathlib import Path

from .schema import AffectedLaw, DetectedEventGroup


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


def _changed_paths(data_repo: Path) -> list[str]:
    out = _run_git(
        ["status", "--porcelain", "--untracked-files=all"], data_repo
    )
    paths: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        status = line[:2]
        rest = line[3:].strip()
        if "->" in rest:
            rest = rest.split("->", 1)[1].strip()
        rest = rest.strip('"')
        if status.strip() in {"D"}:
            continue
        paths.append(rest.replace("\\", "/"))
    return paths


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


def detect_event_groups(data_repo: Path) -> list[DetectedEventGroup]:
    paths = _changed_paths(data_repo)

    law_paths: dict[str, list[str]] = {}
    for p in paths:
        if not p.startswith("laws/"):
            continue
        parts = p.split("/")
        if len(parts) < 2:
            continue
        bjnr = parts[1]
        law_paths.setdefault(bjnr, []).append(p)

    if not law_paths:
        return []

    previous_index = _load_head_index(data_repo)
    prev_sha_by_bjnr = {
        entry["bjnr"]: entry.get("source_xml_sha256")
        for entry in previous_index.values()
        if "bjnr" in entry
    }

    today = datetime.now(timezone.utc).date().isoformat()
    groups: dict[str, DetectedEventGroup] = {}

    for bjnr, changed in sorted(law_paths.items()):
        meta_path = data_repo / "laws" / bjnr / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        stand_datum = meta.get("stand_datum") or today
        sha_after = (meta.get("source_hashes") or {}).get("source_xml_sha256") or ""

        affected = AffectedLaw(
            bjnr=bjnr,
            jurabk=meta.get("jurabk"),
            title=meta.get("title") or bjnr,
            stand_datum=meta.get("stand_datum"),
            source_xml_sha256_before=prev_sha_by_bjnr.get(bjnr),
            source_xml_sha256_after=sha_after,
            changed_paths=sorted(changed),
        )

        group = groups.setdefault(
            stand_datum, DetectedEventGroup(effective_date=stand_datum)
        )
        group.laws.append(affected)

    return [groups[d] for d in sorted(groups.keys())]
