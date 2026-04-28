"""Rechtsprechung-Fetcher (Bundesgerichte).

Target upstream: https://www.rechtsprechung-im-internet.de
Target data repo: https://github.com/eriklueth/rechtsprechung-corpus-data

Supports all federal courts that publish on the joint portal:
BVerfG, BGH, BFH, BAG, BSG, BVerwG, plus the Gemeinsamer Senat.

Pipeline pieces:
- `listing.fetch_listing()` parses the upstream rii-toc.xml.
- `download.fetch_archive()` resolves a per-decision ZIP archive.
- `parse.parse_decision_xml()` turns rii XML into a `DecisionDoc`.
- `writer.write_decision()` persists the canonical layout to disk.

Decision layout in the data repo (see SCHEMA in the data repo README):

    decisions/<COUNTRY>/<COURT>/<YEAR>/<ECLI-tail>/
        meta.json
        decision.xml
        decision.md

CLI:

    rechtsprechung status
    rechtsprechung list --limit N
    rechtsprechung sync --repo PATH [--limit N] [--court BGH]
    rechtsprechung parse --source <local-zip-or-xml>

The `parse` subcommand is intended for offline development and CI: it
operates on local fixtures (a single XML or ZIP) without any network
access, which is required because the rii portal applies GeoIP
filters to non-DE cloud runners.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .._base import ScaffoldInfo

_INFO = ScaffoldInfo(
    source="rechtsprechung",
    data_repo="https://github.com/eriklueth/rechtsprechung-corpus-data",
    upstream="https://www.rechtsprechung-im-internet.de",
    phase="2",
)


def cmd_status(args: argparse.Namespace) -> int:  # noqa: ARG001
    print(f"source:        {_INFO.source}")
    print(f"upstream:      {_INFO.upstream}")
    print(f"data repo:     {_INFO.data_repo}")
    print(f"phase:         {_INFO.phase}")
    print("status:        listing + download + parse + writer wired")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .listing import fetch_listing

    try:
        entries = fetch_listing(limit=args.limit or 20)
    except Exception as exc:
        print(f"listing failed: {exc}")
        return 1
    for e in entries:
        print(f"{e.court:<8} {e.date} {e.case_no:<20} {e.ecli}")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """Parse a single decision archive (local file)."""
    from .download import open_local
    from .parse import parse_decision_xml

    src = args.source
    if not src:
        print("rechtsprechung parse: --source <file> required")
        return 2
    p = Path(src)
    if p.suffix.lower() == ".zip":
        archive = open_local(p)
        xml = archive.xml
    else:
        xml = p.read_bytes()
    doc = parse_decision_xml(xml)
    print(f"ecli:    {doc.ecli or '?'}")
    print(f"court:   {doc.court}")
    print(f"date:    {doc.date}")
    print(f"case_no: {doc.case_no}")
    print(f"type:    {doc.decision_type}")
    print(f"leitsaetze: {len(doc.leitsaetze)}")
    print(f"tenor paragraphs: {len(doc.tenor)}")
    print(f"gruende paragraphs: {len(doc.gruende)}")
    print(f"normrefs: {len(doc.normrefs)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Full sync: listing -> download -> parse -> render -> write.

    Filters:
      --court    restrict to a single court (BGH, BVerfG, ...)
      --limit    cap on number of entries to process

    Writes to `$GESETZE_RECHTSPRECHUNG_REPO` (or --repo). Skips entries
    whose target dir already contains an unchanged decision.md (the
    writer is idempotent so a second run is essentially a no-op).
    """
    from .download import fetch_archive
    from .listing import fetch_listing
    from .parse import parse_decision_xml
    from .writer import canonicalise_xml, write_decision

    repo_dir = args.repo or os.environ.get("GESETZE_RECHTSPRECHUNG_REPO")
    if not repo_dir:
        print(
            "rechtsprechung sync: pass --repo or set GESETZE_RECHTSPRECHUNG_REPO",
        )
        return 2
    repo = Path(repo_dir)
    if not repo.exists():
        print(f"rechtsprechung sync: data repo {repo} does not exist")
        return 2

    try:
        entries = fetch_listing(limit=args.limit)
    except Exception as exc:
        print(f"rechtsprechung sync: listing failed: {exc}")
        return 1

    if args.court:
        wanted = args.court.upper()
        entries = [e for e in entries if (e.court or "").upper() == wanted]

    if not entries:
        print("rechtsprechung sync: empty listing -- nothing to do")
        return 0

    from ...util.gitcommit import commit_paths

    written = unchanged = failed = 0
    for entry in entries:
        try:
            archive = fetch_archive(entry.zip_url, ecli=entry.ecli)
            doc = parse_decision_xml(archive.xml)
            if not doc.ecli:
                doc.ecli = entry.ecli
            canonical = canonicalise_xml(archive.xml)
            result = write_decision(doc, canonical_xml=canonical, data_repo=repo)
        except Exception as exc:  # noqa: BLE001 - log and continue
            print(f"  ! {entry.ecli or entry.zip_url}: {exc}", file=sys.stderr)
            failed += 1
            continue
        if result.written:
            written += 1
            print(f"  + {result.relpath} ({len(result.written)} files)")
            if args.commit:
                commit_paths(
                    repo,
                    paths=[result.relpath],
                    message=(
                        f"decision({doc.court or 'court'} "
                        f"{doc.case_no or 'case'}): {doc.date or 'undated'}\n\n"
                        f"ECLI:  {doc.ecli or '(unknown)'}\n"
                        f"Type:  {doc.decision_type or '(unknown)'}\n"
                    ),
                    iso_date=doc.date or None,
                )
        else:
            unchanged += 1
            print(f"  = {result.relpath} unchanged")

    print(
        f"rechtsprechung sync: written={written} unchanged={unchanged} failed={failed}",
    )
    return 0 if failed == 0 else 1


def register(subparsers) -> None:
    p = subparsers.add_parser("rechtsprechung", help="Bundesgerichte")
    sub = p.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="scaffold status")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="probe the upstream listing (read-only)")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_parse = sub.add_parser(
        "parse", help="parse one decision file (local XML or ZIP fixture)"
    )
    p_parse.add_argument("--source", help="path to a local XML or ZIP archive")
    p_parse.set_defaults(func=cmd_parse)

    p_sync = sub.add_parser("sync", help="full pipeline")
    p_sync.add_argument("--limit", type=int, default=None)
    p_sync.add_argument("--court", help="restrict to a single court (e.g. BGH)")
    p_sync.add_argument(
        "--repo", help="data repo path (overrides $GESETZE_RECHTSPRECHUNG_REPO)"
    )
    p_sync.add_argument(
        "--commit",
        action="store_true",
        help="emit one backdated git commit per decision (author date = decision date)",
    )
    p_sync.set_defaults(func=cmd_sync)
