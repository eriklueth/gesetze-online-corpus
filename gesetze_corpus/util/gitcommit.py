"""Generic backdated-commit helper for data repos.

Several pipelines (Bund-Gesetze, VwV, Rechtsprechung, EU) need the
same primitive: "commit a set of paths in the data repo with the
author date set to the upstream effective date so `git log` reflects
when the law/decision actually took effect, not when our sync ran".

The Bund pipeline implements this with rich event grouping in
`gesetze_corpus/events/commit.py`. This module exposes the pure
git-plumbing piece that the other pipelines can reuse without taking
on the Bund-specific event schema.

Behaviour:
* Author date AND committer date are both backdated to the supplied
  ISO date at 00:00:00 UTC. If no date is supplied we fall through
  to git's defaults (i.e. now).
* The author/committer identity is configurable but defaults to the
  same `gesetze-corpus-bot` identity the Bund pipeline already uses,
  so the cumulative `git log` looks consistent across sources.
* `commit_paths` is idempotent: if the working tree is clean for the
  given paths, no commit is created and the function returns False.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

DEFAULT_AUTHOR_NAME = "gesetze-corpus-bot"
DEFAULT_AUTHOR_EMAIL = "bot@gesetze-corpus.local"


def _run_git(
    args: list[str],
    cwd: Path,
    *,
    env: dict | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def compose_backdated_env(
    *,
    iso_date: str | None,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_email: str = DEFAULT_AUTHOR_EMAIL,
) -> dict[str, str]:
    """Return an env dict suitable for `git commit` that pins
    author + committer name/email and (optionally) backdates both
    timestamps to the given ISO date at 00:00:00 UTC.
    """
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }
    )
    if iso_date:
        timestamp = f"{iso_date[:10]}T00:00:00Z"
        env["GIT_AUTHOR_DATE"] = timestamp
        env["GIT_COMMITTER_DATE"] = timestamp
    return env


def has_pending_changes(data_repo: Path, *, paths: Iterable[str] | None = None) -> bool:
    """True iff `git status --porcelain` reports any change in the
    repo (optionally restricted to the supplied paths)."""
    args = ["status", "--porcelain"]
    if paths:
        args.append("--")
        args.extend(paths)
    out = _run_git(args, data_repo).stdout
    return bool(out.strip())


def commit_paths(
    data_repo: Path,
    *,
    paths: Iterable[str],
    message: str,
    iso_date: str | None = None,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_email: str = DEFAULT_AUTHOR_EMAIL,
    allow_empty: bool = False,
) -> bool:
    """Stage `paths` and create one commit. Returns True iff a commit
    was actually created.

    The function is idempotent against repeated invocations: if none
    of the paths actually changed, no commit is created and False is
    returned (unless `allow_empty=True`).
    """
    relpaths = list(paths)
    if not relpaths:
        return False

    _run_git(["add", "--", *relpaths], data_repo)
    if not allow_empty and not has_pending_changes(data_repo, paths=relpaths):
        # Nothing actually changed for these paths -- staged set is
        # already in HEAD. Treat as a no-op.
        return False

    env = compose_backdated_env(
        iso_date=iso_date,
        author_name=author_name,
        author_email=author_email,
    )
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    result = _run_git(args, data_repo, env=env, check=False)
    return result.returncode == 0


def commit_all(
    data_repo: Path,
    *,
    message: str,
    iso_date: str | None = None,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_email: str = DEFAULT_AUTHOR_EMAIL,
) -> bool:
    """`git add -A` + commit. Returns True iff a commit was created."""
    if not has_pending_changes(data_repo):
        return False
    _run_git(["add", "-A"], data_repo)
    env = compose_backdated_env(
        iso_date=iso_date,
        author_name=author_name,
        author_email=author_email,
    )
    result = _run_git(["commit", "-m", message], data_repo, env=env, check=False)
    return result.returncode == 0


def init_if_missing(data_repo: Path) -> None:
    """Initialise a repo if `.git` is missing. Useful for fresh data
    repos and CI fixtures so callers don't need to special-case it."""
    if (data_repo / ".git").exists():
        return
    _run_git(["init", "-q", "-b", "main"], data_repo)


__all__ = [
    "DEFAULT_AUTHOR_NAME",
    "DEFAULT_AUTHOR_EMAIL",
    "commit_paths",
    "commit_all",
    "compose_backdated_env",
    "has_pending_changes",
    "init_if_missing",
]
