"""Bundes-Verwaltungsvorschriften (VwV) fetcher.

Target upstream: http://www.verwaltungsvorschriften-im-internet.de
Target data repo: https://github.com/eriklueth/vwv-corpus-data

Pipeline pieces:
- `listing.fetch_listing()` parses the HTML index into `VwVEntry`s.
- `detail.fetch_detail()` parses one VwV detail page into a `VwVDocument`.
- `writer.write_vwv()` persists a document to the data repo.

The CLI exposes:
  vwv status       -- print scaffold status
  vwv list         -- probe the upstream listing (read-only)
  vwv parse        -- parse one HTML file (local fixture or URL) and print
                      the section count + first heading
  vwv sync         -- full pipeline: list -> fetch detail -> write to
                      $GESETZE_VWV_REPO. No git ops here; commit
                      grouping happens in a separate worker.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .._base import ScaffoldInfo

_INFO = ScaffoldInfo(
    source="vwv",
    data_repo="https://github.com/eriklueth/vwv-corpus-data",
    upstream="http://www.verwaltungsvorschriften-im-internet.de",
    phase="1",
)


def cmd_status(args: argparse.Namespace) -> int:  # noqa: ARG001
    print(f"source:        {_INFO.source}")
    print(f"upstream:      {_INFO.upstream}")
    print(f"data repo:     {_INFO.data_repo}")
    print(f"phase:         {_INFO.phase}")
    print("status:        listing + detail parser + writer wired")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .listing import fetch_listing

    try:
        entries = fetch_listing(limit=args.limit or 20)
    except Exception as exc:
        print(f"listing failed: {exc}")
        return 1
    for e in entries:
        print(f"{e.short:<12} {e.title[:80]}")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """Parse a single VwV detail page (local file path or remote URL)."""
    from .detail import fetch_detail, parse_detail_html

    src = args.source
    if not src:
        print("vwv parse: --source <file-or-url> required")
        return 2
    if src.startswith("http://") or src.startswith("https://"):
        doc = fetch_detail(src)
    else:
        raw = Path(src).read_bytes()
        doc = parse_detail_html(raw, url=src)

    print(f"short:   {doc.short or '?'}")
    print(f"title:   {doc.title}")
    print(f"date:    {doc.promulgation_date or '?'}")
    print(f"sections: {len(doc.sections)}")
    if doc.sections:
        first = doc.sections[0]
        print(f"first:   {first.ordinal} {first.heading[:60]}")
    if doc.warnings:
        print(f"warnings: {len(doc.warnings)} (first: {doc.warnings[0]})")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """End-to-end sync: list -> fetch -> render -> write.

    Output layout follows the data repo schema (laws/<slug>/...). Git
    ops are intentionally separated out so this command remains a pure
    file-system writer suitable for unit tests.
    """
    from .detail import fetch_detail
    from .listing import fetch_listing
    from .writer import write_vwv

    repo_dir = args.repo or os.environ.get("GESETZE_VWV_REPO")
    if not repo_dir:
        print(
            "vwv sync: pass --repo or set GESETZE_VWV_REPO to a checkout of the data repo",
        )
        return 2
    repo = Path(repo_dir)
    if not repo.exists():
        print(f"vwv sync: data repo {repo} does not exist")
        return 2

    try:
        entries = fetch_listing(limit=args.limit)
    except Exception as exc:
        print(f"vwv sync: listing failed: {exc}")
        return 1

    if not entries:
        print("vwv sync: empty listing -- nothing to do")
        return 0

    from ...util.gitcommit import commit_paths

    written = unchanged = failed = 0
    for entry in entries:
        try:
            doc = fetch_detail(entry.url)
            if not doc.short:
                # Fallback: if the detail page does not expose a short,
                # take it from the listing entry.
                doc.short = entry.short
            result = write_vwv(doc, data_repo=repo)
        except Exception as exc:
            print(f"  ! {entry.short or entry.url}: {exc}", file=sys.stderr)
            failed += 1
            continue
        if result.written:
            written += 1
            print(f"  + {result.slug}: {len(result.written)} files")
            if args.commit:
                commit_paths(
                    repo,
                    paths=[f"laws/{result.slug}"],
                    message=(
                        f"vwv({result.short}): stand "
                        f"{doc.promulgation_date or 'unknown'}\n\n"
                        f"{(doc.title or '')[:80]}\n\n"
                        f"slug:     {result.slug}\n"
                        f"sections: {len(doc.sections)}\n"
                    ),
                    iso_date=doc.promulgation_date or None,
                )
        else:
            unchanged += 1
            print(f"  = {result.slug}: unchanged")

    print(f"vwv sync: written={written} unchanged={unchanged} failed={failed}")
    return 0 if failed == 0 else 1


def register(subparsers) -> None:
    p = subparsers.add_parser("vwv", help="Bundes-Verwaltungsvorschriften")
    sub = p.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="scaffold status")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="probe the upstream listing (read-only)")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_parse = sub.add_parser("parse", help="parse one detail page (local file or URL)")
    p_parse.add_argument("--source", help="local HTML file path or http(s) URL")
    p_parse.set_defaults(func=cmd_parse)

    p_sync = sub.add_parser("sync", help="full pipeline: list -> fetch -> write")
    p_sync.add_argument("--limit", type=int, default=None)
    p_sync.add_argument("--repo", help="data repo path (overrides $GESETZE_VWV_REPO)")
    p_sync.add_argument(
        "--commit",
        action="store_true",
        help="emit one backdated git commit per VwV (author date = promulgation date)",
    )
    p_sync.set_defaults(func=cmd_sync)
