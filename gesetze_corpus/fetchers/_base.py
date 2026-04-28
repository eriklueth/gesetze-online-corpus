"""Shared helpers for fetcher scaffolds.

Sources that are not yet implemented use `not_implemented_command` to
produce a uniform, actionable error message instead of silently doing
nothing. This keeps the CLI surface honest about what works today.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ScaffoldInfo:
    source: str
    data_repo: str
    upstream: str
    phase: str


def not_implemented_command(info: ScaffoldInfo):
    """Return an argparse-compatible handler that reports scaffold status."""

    def handler(args: argparse.Namespace) -> int:  # noqa: ARG001
        print(
            f"source '{info.source}' is a scaffold (phase {info.phase}).\n"
            f"  upstream: {info.upstream}\n"
            f"  target data repo: {info.data_repo}\n"
            f"see docs/ROADMAP.md in gesetze-online-corpus for activation order.",
            file=sys.stderr,
        )
        return 2

    return handler


def attach_status(parser: argparse.ArgumentParser, info: ScaffoldInfo) -> None:
    """Add a `status` subcommand that always works and prints scaffold info."""

    sub = parser.add_subparsers(dest="subcommand", required=True)
    p_status = sub.add_parser(
        "status",
        help=f"print scaffold status for {info.source}",
    )
    p_status.set_defaults(func=_make_status_handler(info))

    p_sync = sub.add_parser(
        "sync",
        help=f"run the {info.source} pipeline (not yet implemented)",
    )
    p_sync.add_argument("--limit", type=int, default=None)
    p_sync.set_defaults(func=not_implemented_command(info))


def _make_status_handler(info: ScaffoldInfo):
    def handler(args: argparse.Namespace) -> int:  # noqa: ARG001
        print(f"source:        {info.source}")
        print(f"upstream:      {info.upstream}")
        print(f"data repo:     {info.data_repo}")
        print(f"phase:         {info.phase}")
        print("status:        scaffold only, awaiting activation")
        return 0

    return handler
