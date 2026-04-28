"""EU-Recht (EUR-Lex) fetcher.

Target upstream: https://eur-lex.europa.eu (via Cellar SPARQL-Endpoint
+ content-negotiation HTML)
Target data repo: https://github.com/eriklueth/eu-recht-corpus-data

Pipeline pieces:
- `client.probe_celex(celex)` - light-weight metadata probe
- `listing.fetch_listing(since)` - SPARQL delta query against Cellar
- `detail.fetch_detail(celex)` - consolidated HTML -> EuDocument
- `detail.parse_detail_html(raw, celex=...)` - pure-parse for tests
- `writer.write_eu_document(doc, data_repo=...)` - idempotent disk write

CLI:

    eu status
    eu probe <CELEX>
    eu list     --since 2024-01-01 --limit 100
    eu parse    --celex <CELEX> --source <local-html>
    eu sync     --since YYYY-MM-DD [--limit N] [--repo PATH]
    eu backfill --from YYYY-MM-DD [--to YYYY-MM-DD] [--window-days N] \
                [--cursor PATH] [--limit N] [--repo PATH] [--dry-run]

The `parse` subcommand is intended for offline development / CI: it
operates on a local HTML fixture and never touches the network. The
`sync` subcommand uses Cellar SPARQL for delta selection and the
content-negotiation endpoint for the bodies. `backfill` walks the
historical date range in fixed windows with a resumable cursor file
so the initial population of the data repo can survive
rate-limits / VPN flips / overnight crashes without losing progress.

See docs/ROADMAP.md phase 9.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .._base import ScaffoldInfo

_INFO = ScaffoldInfo(
    source="eu",
    data_repo="https://github.com/eriklueth/eu-recht-corpus-data",
    upstream="https://eur-lex.europa.eu",
    phase="9",
)


def cmd_status(args: argparse.Namespace) -> int:  # noqa: ARG001
    print(f"source:        {_INFO.source}")
    print(f"upstream:      {_INFO.upstream}")
    print(f"data repo:     {_INFO.data_repo}")
    print(f"phase:         {_INFO.phase}")
    print("status:        sparql listing + detail parser + writer wired")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    from .client import probe_celex

    try:
        info = probe_celex(args.celex)
    except Exception as exc:
        print(f"probe failed: {exc}")
        return 1
    print(f"celex:         {info['celex']}")
    print(f"title:         {info['title'][:120]}")
    print(f"eli:           {info['eli']}")
    print(f"language:      {info['language']}")
    print(f"doc_type:      {info['doc_type']}")
    print(f"bytes:         {info['bytes']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .listing import fetch_listing

    try:
        entries = fetch_listing(since=args.since, limit=args.limit or 50)
    except Exception as exc:
        print(f"eu list failed: {exc}")
        return 1
    for e in entries:
        print(f"{e.date}  {e.celex:<14} {e.title[:80]}")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """Parse one EUR-Lex consolidated HTML fixture (offline)."""
    from .detail import parse_detail_html

    if not args.source:
        print("eu parse: --source <html-file> required")
        return 2
    raw = Path(args.source).read_bytes()
    doc = parse_detail_html(
        raw,
        celex=args.celex or "UNKNOWN",
        language=args.language or "de",
    )
    print(f"celex:    {doc.celex}")
    print(f"title:    {doc.title[:120]}")
    print(f"eli:      {doc.eli}")
    print(f"doc_type: {doc.doc_type}")
    print(f"language: {doc.language}")
    print(f"articles: {len(doc.articles)}")
    return 0


def _resolve_repo(args: argparse.Namespace, *, command: str) -> Path | None:
    repo_dir = args.repo or os.environ.get("GESETZE_EU_REPO")
    if not repo_dir:
        print(f"eu {command}: pass --repo or set GESETZE_EU_REPO")
        return None
    repo = Path(repo_dir)
    if not repo.exists():
        print(f"eu {command}: data repo {repo} does not exist")
        return None
    return repo


def _materialise_entry(
    entry,
    repo: Path,
    language: str,
    *,
    commit: bool = False,
) -> tuple[bool, str]:
    """Returns (written?, status-line). Used by sync and backfill.

    When `commit=True` is set, each CELEX that produces real changes
    gets its own backdated commit using the upstream entry date so
    `git log` on a single article file reflects when EUR-Lex first
    published it, not when our sync ran.
    """
    from .detail import fetch_detail
    from .writer import write_eu_document
    from ...util.gitcommit import commit_paths

    doc = fetch_detail(entry.celex, language=language)
    result = write_eu_document(doc, data_repo=repo)
    if result.written:
        if commit:
            rel = f"laws/{result.celex}"
            commit_paths(
                repo,
                paths=[rel],
                message=(
                    f"eu({result.celex}): stand {entry.date or 'unknown'}\n\n"
                    f"{(doc.title or '')[:80]}\n\n"
                    f"CELEX:    {result.celex}\n"
                    f"ELI:      {doc.eli or '(unknown)'}\n"
                    f"Articles: {len(doc.articles)}\n"
                ),
                iso_date=entry.date or None,
            )
        return True, f"  + laws/{result.celex} ({len(result.written)} files)"
    return False, f"  = laws/{result.celex} unchanged"


def cmd_sync(args: argparse.Namespace) -> int:
    """Full pipeline: SPARQL listing -> detail fetch -> render -> write."""
    from .listing import fetch_listing

    repo = _resolve_repo(args, command="sync")
    if repo is None:
        return 2

    try:
        entries = fetch_listing(since=args.since, limit=args.limit or 50)
    except Exception as exc:
        print(f"eu sync: listing failed: {exc}")
        return 1

    if not entries:
        print("eu sync: empty listing, nothing to do")
        return 0

    written = unchanged = failed = 0
    for entry in entries:
        try:
            did_write, status = _materialise_entry(
                entry,
                repo,
                args.language or "DE",
                commit=bool(args.commit),
            )
        except Exception as exc:  # noqa: BLE001 - log and continue
            print(f"  ! {entry.celex}: {exc}", file=sys.stderr)
            failed += 1
            continue
        print(status)
        if did_write:
            written += 1
        else:
            unchanged += 1
    print(f"eu sync: written={written} unchanged={unchanged} failed={failed}")
    return 0 if failed == 0 else 1


def cmd_backfill(args: argparse.Namespace) -> int:
    """Resumable historical sweep: walk [--from, --to) in windows.

    Behaviour:
      * Listing windows are fetched ascending from --from to --to;
        each window is small enough to stay below the SPARQL 1000-row
        cap. The default window is 30 days.
      * A flat-file cursor (default `<repo>/.cursors/eu-backfill`)
        records the last completed window so reruns resume cleanly.
      * --dry-run prints the listing only; no detail fetch, no writes.
      * --limit is total CELEX count across all windows (for testing).
      * The downstream writer is idempotent, so re-running a partial
        window is safe.
    """
    from .listing import iter_backfill

    repo = _resolve_repo(args, command="backfill") if not args.dry_run else None
    if not args.dry_run and repo is None:
        return 2

    cursor_path = Path(args.cursor) if args.cursor else (
        (repo or Path(".")) / ".cursors" / "eu-backfill"
    )

    seen: set[str] = set()
    seen_count = written = unchanged = failed = 0
    try:
        iterator = iter_backfill(
            start=args.from_,
            end=args.to,
            window_days=args.window_days or 30,
            cursor_path=cursor_path,
        )
    except ValueError as exc:
        print(f"eu backfill: {exc}")
        return 2

    for entry in iterator:
        if args.limit is not None and seen_count >= args.limit:
            break
        if entry.celex in seen:
            continue
        seen.add(entry.celex)
        seen_count += 1
        if args.dry_run:
            print(f"  ? {entry.date}  {entry.celex:<14} {entry.title[:80]}")
            continue
        try:
            did_write, status = _materialise_entry(
                entry,
                repo,
                args.language or "DE",
                commit=bool(args.commit),
            )
        except Exception as exc:  # noqa: BLE001 - log and continue
            print(f"  ! {entry.celex}: {exc}", file=sys.stderr)
            failed += 1
            continue
        print(status)
        if did_write:
            written += 1
        else:
            unchanged += 1

    print(
        f"eu backfill: scanned={seen_count} written={written} "
        f"unchanged={unchanged} failed={failed} cursor={cursor_path}"
    )
    return 0 if failed == 0 else 1


def register(subparsers) -> None:
    p = subparsers.add_parser("eu", help="EU-Recht via EUR-Lex")
    sub = p.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="scaffold status")
    p_status.set_defaults(func=cmd_status)

    p_probe = sub.add_parser("probe", help="probe a single CELEX identifier")
    p_probe.add_argument("celex", help="e.g. 32016R0679 for GDPR")
    p_probe.set_defaults(func=cmd_probe)

    p_list = sub.add_parser("list", help="SPARQL delta listing for sector 3")
    p_list.add_argument("--since", default="2024-01-01", help="ISO date (YYYY-MM-DD)")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    p_parse = sub.add_parser(
        "parse", help="parse a local consolidated HTML fixture (offline)"
    )
    p_parse.add_argument("--source", help="path to HTML")
    p_parse.add_argument("--celex", help="CELEX number (defaults to UNKNOWN)")
    p_parse.add_argument("--language", default="de")
    p_parse.set_defaults(func=cmd_parse)

    p_sync = sub.add_parser("sync", help="full pipeline (forward delta)")
    p_sync.add_argument("--since", default="2024-01-01")
    p_sync.add_argument("--limit", type=int, default=50)
    p_sync.add_argument("--language", default="DE")
    p_sync.add_argument("--repo", help="data repo path (overrides $GESETZE_EU_REPO)")
    p_sync.add_argument(
        "--commit",
        action="store_true",
        help="emit one backdated git commit per CELEX (author date = entry date)",
    )
    p_sync.set_defaults(func=cmd_sync)

    p_back = sub.add_parser(
        "backfill",
        help="resumable historical sweep over a date range",
        description=(
            "Walk a [--from, --to) date range in fixed windows, "
            "writing every CELEX. Resumable via a flat-file cursor; "
            "safe to interrupt and rerun."
        ),
    )
    # `from` is a Python keyword, hence the trailing underscore on the dest.
    p_back.add_argument("--from", dest="from_", required=True, help="ISO start date")
    p_back.add_argument("--to", dest="to", default=None, help="ISO end date (default: today)")
    p_back.add_argument("--window-days", dest="window_days", type=int, default=30)
    p_back.add_argument(
        "--cursor",
        help="path to the cursor file (default: <repo>/.cursors/eu-backfill)",
    )
    p_back.add_argument("--limit", type=int, default=None, help="total CELEX cap (testing)")
    p_back.add_argument("--language", default="DE")
    p_back.add_argument("--repo", help="data repo path (overrides $GESETZE_EU_REPO)")
    p_back.add_argument(
        "--dry-run",
        action="store_true",
        help="list windows + CELEX but do not download or write",
    )
    p_back.add_argument(
        "--commit",
        action="store_true",
        help="emit one backdated git commit per CELEX (author date = entry date)",
    )
    p_back.set_defaults(func=cmd_backfill)
