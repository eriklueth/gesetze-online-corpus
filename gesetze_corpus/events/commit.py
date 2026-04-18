"""Backdate-commit detected event groups into the data repo.

For each :class:`DetectedEventGroup`:

1. Write ``events/<year>/<event_id>.json`` describing the group.
2. ``git add`` the event file and all changed paths of the group.
3. ``git commit`` with ``GIT_AUTHOR_DATE`` and ``GIT_COMMITTER_DATE`` set
   to the effective_date at 00:00:00 UTC.

Any remaining changes (typically ``sources/current/gii-index.json``)
are committed last as a bookkeeping commit with today's date.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .. import TOOLING_ID
from .schema import DetectedEventGroup
from .writer import write_event

log = logging.getLogger(__name__)

DEFAULT_AUTHOR_NAME = "gesetze-corpus-bot"
DEFAULT_AUTHOR_EMAIL = "bot@gesetze-corpus.local"


def _run_git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.stdout


def _compose_env(effective_date: str, author_name: str, author_email: str) -> dict:
    iso = f"{effective_date}T00:00:00Z"
    base = dict(os.environ)
    base.update(
        {
            "GIT_AUTHOR_DATE": iso,
            "GIT_COMMITTER_DATE": iso,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }
    )
    return base


def _commit_message(group: DetectedEventGroup) -> str:
    date = group.effective_date
    if len(group.laws) == 1:
        law = group.laws[0]
        handle = law.jurabk or law.bjnr
        short_title = (law.title or "").strip()
        if len(short_title) > 80:
            short_title = short_title[:77] + "..."
        return (
            f"law({handle}): stand {date}\n\n"
            f"{short_title}\n\n"
            f"BJNR: {law.bjnr}\n"
            f"tooling: {TOOLING_ID}\n"
        )
    handles = ", ".join((law.jurabk or law.bjnr) for law in group.laws[:5])
    if len(group.laws) > 5:
        handles += f", +{len(group.laws) - 5} more"
    return (
        f"feat(data): {len(group.laws)} laws - stand {date}\n\n"
        f"{handles}\n\n"
        f"tooling: {TOOLING_ID}\n"
    )


def commit_event_groups(
    data_repo: Path,
    groups: list[DetectedEventGroup],
    *,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_email: str = DEFAULT_AUTHOR_EMAIL,
    bookkeeping_message: str = "chore(sync): update index",
) -> tuple[int, int]:
    """Commit detected event groups. Returns (event_commits, bookkeeping_commits)."""
    committed = 0
    for group in groups:
        payload = {
            "affected": [
                {
                    "bjnr": law.bjnr,
                    "changed_paths": law.changed_paths,
                    "jurabk": law.jurabk,
                    "sections_added": law.sections_added,
                    "sections_modified": law.sections_modified,
                    "sections_removed": law.sections_removed,
                    "source_xml_sha256_after": law.source_xml_sha256_after,
                    "source_xml_sha256_before": law.source_xml_sha256_before,
                    "stand_datum": law.stand_datum,
                    "title": law.title,
                }
                for law in group.laws
            ],
            "source_type": group.source_type,
            "verification": {
                "method": "gii-xml-sha256",
                "notes": (
                    "effective_date derived from meta.json stand_datum; "
                    "per-section A/M/D derived from git working tree"
                ),
            },
        }
        event_path = write_event(
            data_repo=data_repo,
            event_id=group.event_id,
            effective_date=group.effective_date,
            payload=payload,
        )

        rel_event = event_path.relative_to(data_repo).as_posix()
        paths_to_add = [rel_event]
        for law in group.laws:
            paths_to_add.extend(law.changed_paths)

        _run_git(["add", "--", *paths_to_add], data_repo)

        env = _compose_env(group.effective_date, author_name, author_email)
        msg = _commit_message(group)
        try:
            _run_git(["commit", "-m", msg], data_repo, env=env)
            committed += 1
            log.info(
                "committed event %s with %d law(s)",
                group.event_id,
                len(group.laws),
            )
        except subprocess.CalledProcessError as exc:
            log.warning("commit failed for %s: %s", group.event_id, exc.stderr)

    bookkeeping = 0
    status_out = _run_git(["status", "--porcelain"], data_repo)
    if status_out.strip():
        _run_git(["add", "-A"], data_repo)
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": author_name,
                "GIT_AUTHOR_EMAIL": author_email,
                "GIT_COMMITTER_NAME": author_name,
                "GIT_COMMITTER_EMAIL": author_email,
            }
        )
        _run_git(["commit", "-m", bookkeeping_message], data_repo, env=env)
        bookkeeping = 1

    return committed, bookkeeping
