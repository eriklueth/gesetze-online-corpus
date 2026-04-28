"""Per-source fetchers for the gesetze-corpus pipeline.

Each submodule implements the same minimal protocol:

    def register(subparsers: argparse._SubParsersAction) -> None

and wires its subcommands into the `gesetze-corpus <source> <subcommand>`
namespace. The `bund` source is the canonical reference implementation;
all others (vwv, rechtsprechung, eu, land) start as scaffolds that
surface an actionable "not yet implemented" message and link to the
roadmap.

See docs/ROADMAP.md for the ordering of source activation.
"""

from . import bund, eu, land, rechtsprechung, vwv

__all__ = ["bund", "vwv", "rechtsprechung", "eu", "land"]
