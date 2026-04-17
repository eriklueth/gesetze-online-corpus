from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

from . import SCHEMA_VERSION
from .canonical import canonicalize_json_dump, canonicalize_xml_bytes
from .ingest.snapshot import snapshot, iter_laws
from .util.paths import resolve_data_repo, ensure_dir

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


DATA_README = """# gesetze-corpus-data

Versionierter Korpus deutscher Bundesgesetze. **Nur Daten**, kein Code.

Jeder Commit in diesem Repo repraesentiert entweder

- den initialen Snapshot aus dem amtlichen GII-XML, oder
- ein Inkrafttretensereignis (spaeter, via Events-Pipeline), oder
- einen explizit markierten `chore(canonical)`-Reformat-Lauf.

## Quellen

- Primaertext: gesetze-im-internet.de (GII), amtliches XML.
- Geplante Ergaenzung: recht.bund.de / NeuRIS (Verkuendungen, ELI).
- Geplante Ergaenzung: buzer.de (Aenderungs-Metadaten, niemals Text).

## Layout

Siehe `SCHEMA.md`.

## Lizenz

Die amtlichen Normtexte sind gemeinfrei nach § 5 UrhG. Die Struktur
und Metadaten dieses Repos werden unter CC0-1.0 veroeffentlicht
(siehe `LICENSE`).

## Erzeugt von

Das Tools-Repo `gesetze-online-corpus` betreibt die Pipeline.
Schema-Version: v1.
"""

DATA_GITATTRIBUTES = """* text=auto eol=lf
*.xml text eol=lf
*.json text eol=lf
*.md text eol=lf
"""

DATA_GITIGNORE = """# data repo must stay clean of build artefacts
.DS_Store
Thumbs.db
"""

LICENSE_CC0 = """Creative Commons Legal Code

CC0 1.0 Universal

The person who associated a work with this deed has dedicated the work
to the public domain by waiving all of his or her rights to the work
worldwide under copyright law, including all related and neighboring
rights, to the extent allowed by law.

You can copy, modify, distribute and perform the work, even for
commercial purposes, all without asking permission.

See https://creativecommons.org/publicdomain/zero/1.0/ for the full
legal text.
"""


def _copy_schema_doc(data_repo: Path) -> None:
    src = Path(__file__).resolve().parent.parent / "docs" / "SCHEMA.md"
    if src.exists():
        raw = src.read_bytes().replace(b"\r\n", b"\n")
        (data_repo / "SCHEMA.md").write_bytes(raw)


def cmd_init_data(args: argparse.Namespace) -> int:
    data_repo = resolve_data_repo(args.data_repo)
    ensure_dir(data_repo)
    ensure_dir(data_repo / "laws")
    ensure_dir(data_repo / "events")
    ensure_dir(data_repo / "sources" / "current")

    readme = data_repo / "README.md"
    if not readme.exists():
        readme.write_bytes(DATA_README.encode("utf-8"))
    (data_repo / ".gitattributes").write_bytes(DATA_GITATTRIBUTES.encode("utf-8"))
    (data_repo / ".gitignore").write_bytes(DATA_GITIGNORE.encode("utf-8"))
    (data_repo / "LICENSE").write_bytes(LICENSE_CC0.encode("utf-8"))
    _copy_schema_doc(data_repo)

    empty_index = {
        "laws": {},
        "schema_version": SCHEMA_VERSION,
        "toc_source_url": "https://www.gesetze-im-internet.de/gii-toc.xml",
        "updated_at": "1970-01-01T00:00:00Z",
    }
    (data_repo / "sources" / "current" / "gii-index.json").write_bytes(
        canonicalize_json_dump(empty_index).encode("utf-8")
    )

    git_dir = data_repo / ".git"
    if not git_dir.exists() and not args.no_git:
        try:
            subprocess.run(
                ["git", "init", "--initial-branch=main", str(data_repo)],
                check=True,
                capture_output=True,
            )
            print(f"git initialized in {data_repo}")
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(f"warning: could not git init: {exc}", file=sys.stderr)

    print(f"data repo ready: {data_repo}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    data_repo = resolve_data_repo(args.data_repo)
    if not (data_repo / "sources").exists():
        print(
            "data repo not initialized. run: python -m gesetze_corpus init-data",
            file=sys.stderr,
        )
        return 2
    report = snapshot(
        data_repo,
        limit=args.limit,
        only_slug=args.slug,
        workers=args.workers,
    )
    print(
        f"snapshot: total={report.total} fetched={report.fetched} "
        f"written={report.written} unchanged={report.unchanged} failed={report.failed}"
    )
    if report.failures:
        for slug, err in report.failures[:20]:
            print(f"  FAIL {slug}: {err}", file=sys.stderr)
    return 0 if report.failed == 0 else 1


def cmd_verify(args: argparse.Namespace) -> int:
    data_repo = resolve_data_repo(args.data_repo)
    issues = 0
    for law_dir in iter_laws(data_repo):
        xml_path = law_dir / "source.xml"
        meta_path = law_dir / "meta.json"
        if not xml_path.exists() or not meta_path.exists():
            continue
        raw = xml_path.read_bytes()
        canon = canonicalize_xml_bytes(raw)
        if canon != raw:
            issues += 1
            print(f"NON-CANONICAL XML: {xml_path}", file=sys.stderr)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        sha = hashlib.sha256(raw).hexdigest()
        recorded = (meta.get("source_hashes") or {}).get("source_xml_sha256")
        if recorded != sha:
            issues += 1
            print(f"HASH MISMATCH: {xml_path}", file=sys.stderr)
    if issues:
        print(f"{issues} issue(s) found", file=sys.stderr)
        return 1
    print("verify: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gesetze-corpus")
    parser.add_argument(
        "--data-repo",
        help="path to gesetze-corpus-data (defaults to ../gesetze-corpus-data)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-data", help="scaffold the data repo")
    p_init.add_argument("--no-git", action="store_true")
    p_init.set_defaults(func=cmd_init_data)

    p_snap = sub.add_parser("snapshot", help="fetch + canonicalize + render")
    p_snap.add_argument("--limit", type=int, default=None)
    p_snap.add_argument("--slug", default=None, help="only one law by GII slug")
    p_snap.add_argument("--workers", type=int, default=4)
    p_snap.set_defaults(func=cmd_snapshot)

    p_verify = sub.add_parser("verify", help="check canonical form and hashes")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=_LOG_FORMAT,
    )
    return args.func(args)
