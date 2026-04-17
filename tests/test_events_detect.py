from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gesetze_corpus.canonical import canonicalize_json_dump
from gesetze_corpus.events import detect_event_groups, commit_event_groups


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "HOME": str(repo),
    }
    import os

    full_env = dict(os.environ)
    full_env.update(env)
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=full_env,
    ).stdout


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonicalize_json_dump(payload).encode("utf-8"))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


@pytest.fixture
def data_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "data"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    (repo / "laws").mkdir()
    (repo / "events").mkdir()
    (repo / "sources" / "current").mkdir(parents=True)
    _write_json(
        repo / "sources" / "current" / "gii-index.json",
        {"laws": {}, "schema_version": "v1"},
    )
    _write_text(repo / "README.md", "# test\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def _seed_law(
    repo: Path,
    bjnr: str,
    stand_datum: str | None,
    sha: str,
    jurabk: str = "TEST",
) -> None:
    law_dir = repo / "laws" / bjnr
    _write_json(
        law_dir / "meta.json",
        {
            "bjnr": bjnr,
            "jurabk": jurabk,
            "schema_version": "v1",
            "source_hashes": {"source_xml_sha256": sha},
            "stand_datum": stand_datum,
            "title": f"Gesetz {bjnr}",
        },
    )
    _write_text(law_dir / "source.xml", "<x/>\n")
    _write_text(law_dir / "paragraphs" / "0001.md", "# para\n")


def test_detect_groups_by_stand_datum(data_repo: Path) -> None:
    _seed_law(data_repo, "BJNR000000001", "2026-01-15", "aaa", jurabk="A")
    _seed_law(data_repo, "BJNR000000002", "2026-01-15", "bbb", jurabk="B")
    _seed_law(data_repo, "BJNR000000003", "2026-03-01", "ccc", jurabk="C")

    groups = detect_event_groups(data_repo)
    assert [g.effective_date for g in groups] == ["2026-01-15", "2026-03-01"]
    assert [law.bjnr for law in groups[0].laws] == [
        "BJNR000000001",
        "BJNR000000002",
    ]
    assert groups[1].laws[0].bjnr == "BJNR000000003"


def test_detect_uses_today_as_fallback(data_repo: Path) -> None:
    _seed_law(data_repo, "BJNR000000009", None, "zzz")
    groups = detect_event_groups(data_repo)
    assert len(groups) == 1
    assert groups[0].laws[0].stand_datum is None


def test_commit_event_groups_creates_backdated_commit(data_repo: Path) -> None:
    _seed_law(data_repo, "BJNR000000010", "2024-06-30", "hhh", jurabk="X")
    groups = detect_event_groups(data_repo)
    events, bookkeeping = commit_event_groups(
        data_repo,
        groups,
        author_name="gesetze-corpus-bot",
        author_email="bot@gesetze-corpus.local",
    )
    assert events == 1
    log = _git(data_repo, "log", "--pretty=format:%ad|%s", "--date=iso-strict")
    head_line = log.splitlines()[0]
    date_part, subject = head_line.split("|", 1)
    assert date_part.startswith("2024-06-30")
    assert "law(X): stand 2024-06-30" in subject

    event_files = list((data_repo / "events").rglob("*.json"))
    assert len(event_files) == 1
    payload = json.loads(event_files[0].read_text(encoding="utf-8"))
    assert payload["effective_date"] == "2024-06-30"
    assert payload["affected"][0]["bjnr"] == "BJNR000000010"
