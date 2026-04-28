"""Tests for the generic backdated-commit helper.

These run against a tmp git repo so we exercise the real git plumbing
(env var handling for backdating, idempotent staging, etc.).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gesetze_corpus.util.gitcommit import (
    commit_all,
    commit_paths,
    compose_backdated_env,
    has_pending_changes,
    init_if_missing,
)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    init_if_missing(tmp_path)
    # init_if_missing is itself idempotent.
    init_if_missing(tmp_path)
    # Seed a commit so HEAD exists.
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git("add", "README.md", cwd=tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=test@x", "-c", "user.name=Test", "commit", "-q", "-m", "seed"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def test_compose_backdated_env_sets_author_and_committer():
    env = compose_backdated_env(iso_date="2016-04-27")
    assert env["GIT_AUTHOR_DATE"] == "2016-04-27T00:00:00Z"
    assert env["GIT_COMMITTER_DATE"] == "2016-04-27T00:00:00Z"
    assert env["GIT_AUTHOR_NAME"] == "gesetze-corpus-bot"
    assert env["GIT_COMMITTER_EMAIL"] == "bot@gesetze-corpus.local"


def test_compose_backdated_env_no_date_omits_timestamp_keys():
    env = compose_backdated_env(iso_date=None, author_name="x", author_email="x@x")
    assert "GIT_AUTHOR_DATE" not in env
    assert env["GIT_AUTHOR_NAME"] == "x"


def test_commit_paths_creates_one_backdated_commit(repo: Path):
    target = repo / "laws" / "32016R0679" / "meta.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")

    created = commit_paths(
        repo,
        paths=["laws/32016R0679"],
        message="eu(32016R0679): stand 2016-04-27\n\nDSGVO\n",
        iso_date="2016-04-27",
    )
    assert created is True

    log = _git("log", "-1", "--format=%H %ad %s", "--date=short", cwd=repo).strip()
    h, date, *subject = log.split(maxsplit=2)
    assert date == "2016-04-27"
    assert subject[0].startswith("eu(32016R0679)")


def test_commit_paths_is_idempotent_when_nothing_changed(repo: Path):
    target = repo / "laws" / "X" / "meta.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    assert commit_paths(repo, paths=["laws/X"], message="x", iso_date="2020-01-01")
    # Second call: nothing changed -> no new commit.
    assert (
        commit_paths(repo, paths=["laws/X"], message="x", iso_date="2020-01-01")
        is False
    )
    history = _git("log", "--format=%s", cwd=repo).splitlines()
    assert history.count("x") == 1


def test_commit_all_returns_false_for_clean_tree(repo: Path):
    assert has_pending_changes(repo) is False
    assert commit_all(repo, message="noop") is False


def test_eu_writer_plus_commit_integration(repo: Path):
    """End-to-end: render an EU article, commit with backdated author."""
    from gesetze_corpus.fetchers.eu.detail import parse_detail_html
    from gesetze_corpus.fetchers.eu.writer import write_eu_document

    sample = (
        "<html><body>"
        "<p class='ti-art'>Artikel 1</p>"
        "<p class='sti-art'>Gegenstand</p>"
        "<p class='oj-normal'>(1) Diese Verordnung gilt.</p>"
        "</body></html>"
    )
    doc = parse_detail_html(sample.encode("utf-8"), celex="32016R0679")
    write_eu_document(doc, data_repo=repo)
    created = commit_paths(
        repo,
        paths=["laws/32016R0679"],
        message="eu(32016R0679): stand 2016-04-27\n",
        iso_date="2016-04-27",
    )
    assert created is True
    log = _git("log", "-1", "--format=%ad %s", "--date=short", cwd=repo).strip()
    assert log.startswith("2016-04-27 ")
    assert "32016R0679" in log


def test_commit_all_picks_up_every_change(repo: Path):
    (repo / "a.txt").write_text("A\n", encoding="utf-8")
    (repo / "b.txt").write_text("B\n", encoding="utf-8")
    assert has_pending_changes(repo) is True
    assert commit_all(repo, message="both", iso_date="2024-06-01") is True
    log = _git("log", "-1", "--format=%ad", "--date=short", cwd=repo).strip()
    assert log == "2024-06-01"
