"""CLI entry point.

New command shape: `gesetze-corpus <source> <subcommand> [opts]`

Sources:
  bund            — Bundesrecht (GII), production-ready
  vwv             — Bundes-Verwaltungsvorschriften (scaffold, phase 1)
  rechtsprechung  — Bundesgerichte (scaffold, phase 2)
  eu              — EU-Recht (EUR-Lex) (scaffold, phase 9)
  land <iso>      — Landesrecht (scaffold, phase 8)

Legacy command shape is preserved as aliases so the existing Windows
Scheduled Task and any shell history keep working unchanged:

  gesetze-corpus snapshot        == gesetze-corpus bund snapshot
  gesetze-corpus sync            == gesetze-corpus bund sync
  gesetze-corpus commit-events   == gesetze-corpus bund commit-events
  gesetze-corpus export          == gesetze-corpus bund export
  gesetze-corpus rerender        == gesetze-corpus bund rerender
  gesetze-corpus verify          == gesetze-corpus bund verify
  gesetze-corpus init-data       == gesetze-corpus bund init-data

Deprecation: the legacy shape stays indefinitely. Scripts can migrate
at their own pace.
"""

from __future__ import annotations

import argparse
import logging

from .fetchers import bund, eu, land, rechtsprechung, vwv

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_LEGACY_COMMANDS = {
    "snapshot": "cmd_snapshot",
    "sync": "cmd_sync",
    "commit-events": "cmd_commit_events",
    "export": "cmd_export",
    "rerender": "cmd_rerender",
    "verify": "cmd_verify",
    "init-data": "cmd_init_data",
}


def _add_legacy_aliases(subparsers) -> None:
    """Register the old flat commands as thin wrappers around bund.cmd_*.

    Each legacy parser shares argument surface with the corresponding
    `bund <subcommand>` parser by calling into `bund.register`-like
    logic inline. Keeping the argument parsing in one place avoids
    drift between the legacy and new shapes.
    """
    p_init = subparsers.add_parser("init-data", help="alias of: bund init-data")
    p_init.add_argument("--no-git", action="store_true")
    p_init.set_defaults(func=bund.cmd_init_data)

    p_snap = subparsers.add_parser("snapshot", help="alias of: bund snapshot")
    p_snap.add_argument("--limit", type=int, default=None)
    p_snap.add_argument("--slug", default=None)
    p_snap.add_argument("--workers", type=int, default=4)
    p_snap.add_argument("--force-rerender", action="store_true")
    p_snap.set_defaults(func=bund.cmd_snapshot)

    p_verify = subparsers.add_parser("verify", help="alias of: bund verify")
    p_verify.set_defaults(func=bund.cmd_verify)

    p_commit = subparsers.add_parser("commit-events", help="alias of: bund commit-events")
    p_commit.add_argument("--author-name", default="gesetze-corpus-bot")
    p_commit.add_argument("--author-email", default="bot@gesetze-corpus.local")
    p_commit.add_argument("--bookkeeping-message", default="chore(sync): update index")
    p_commit.add_argument("--skip-bookkeeping", action="store_true")
    p_commit.set_defaults(func=bund.cmd_commit_events)

    p_sync = subparsers.add_parser("sync", help="alias of: bund sync")
    p_sync.add_argument("--limit", type=int, default=None)
    p_sync.add_argument("--slug", default=None)
    p_sync.add_argument("--workers", type=int, default=4)
    p_sync.add_argument("--author-name", default="gesetze-corpus-bot")
    p_sync.add_argument("--author-email", default="bot@gesetze-corpus.local")
    p_sync.add_argument("--ignore-errors", action="store_true")
    p_sync.add_argument("--force-rerender", action="store_true")
    p_sync.add_argument("--rerender-message", default=None)
    p_sync.set_defaults(func=bund.cmd_sync)

    p_rerender = subparsers.add_parser("rerender", help="alias of: bund rerender")
    p_rerender.add_argument("--workers", type=int, default=8)
    p_rerender.set_defaults(func=bund.cmd_rerender)

    p_export = subparsers.add_parser("export", help="alias of: bund export")
    p_export.add_argument("--out", default=None)
    p_export.set_defaults(func=bund.cmd_export)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gesetze-corpus")
    parser.add_argument(
        "--data-repo",
        help="path to a data repo (default depends on source)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    bund.register(sub)
    vwv.register(sub)
    rechtsprechung.register(sub)
    eu.register(sub)
    land.register(sub)

    _add_legacy_aliases(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=_LOG_FORMAT,
    )
    return args.func(args)
