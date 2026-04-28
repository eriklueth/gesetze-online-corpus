"""Landesrecht fetcher — scaffold, driven by a per-Land registry.

Each Bundesland has its own portal, its own HTML/XML schema, and its
own release cadence. Rather than hard-coding 16 sibling packages, we
keep a single scaffold here with a per-ISO registry. When a Land is
actually activated (phase 8), it grows into its own subpackage
(`gesetze_corpus.fetchers.land.by`, `…nw`, etc.) behind the same CLI
facade.

Dispatch:

    gesetze-corpus land <iso> status
    gesetze-corpus land <iso> sync [--limit N]

Priority order (per roadmap): by > nw > bw > he > ni > sn > rp >
sl > sh > th > st > mv > bb > be > hh > hb.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from .._base import not_implemented_command


@dataclass(frozen=True)
class LandInfo:
    iso: str
    name: str
    upstream: str
    data_repo: str


_REGISTRY: dict[str, LandInfo] = {
    "bw": LandInfo("bw", "Baden-Württemberg", "https://www.landesrecht-bw.de", "https://github.com/eriklueth/landesrecht-bw-corpus-data"),
    "by": LandInfo("by", "Bayern", "https://www.gesetze-bayern.de", "https://github.com/eriklueth/landesrecht-by-corpus-data"),
    "be": LandInfo("be", "Berlin", "https://gesetze.berlin.de", "https://github.com/eriklueth/landesrecht-be-corpus-data"),
    "bb": LandInfo("bb", "Brandenburg", "https://bravors.brandenburg.de", "https://github.com/eriklueth/landesrecht-bb-corpus-data"),
    "hb": LandInfo("hb", "Bremen", "https://www.transparenz.bremen.de", "https://github.com/eriklueth/landesrecht-hb-corpus-data"),
    "hh": LandInfo("hh", "Hamburg", "https://www.landesrecht-hamburg.de", "https://github.com/eriklueth/landesrecht-hh-corpus-data"),
    "he": LandInfo("he", "Hessen", "https://www.rv.hessenrecht.hessen.de", "https://github.com/eriklueth/landesrecht-he-corpus-data"),
    "mv": LandInfo("mv", "Mecklenburg-Vorpommern", "https://www.landesrecht-mv.de", "https://github.com/eriklueth/landesrecht-mv-corpus-data"),
    "ni": LandInfo("ni", "Niedersachsen", "https://www.voris.niedersachsen.de", "https://github.com/eriklueth/landesrecht-ni-corpus-data"),
    "nw": LandInfo("nw", "Nordrhein-Westfalen", "https://recht.nrw.de", "https://github.com/eriklueth/landesrecht-nw-corpus-data"),
    "rp": LandInfo("rp", "Rheinland-Pfalz", "https://landesrecht.rlp.de", "https://github.com/eriklueth/landesrecht-rp-corpus-data"),
    "sl": LandInfo("sl", "Saarland", "https://www.saarland.de/recht", "https://github.com/eriklueth/landesrecht-sl-corpus-data"),
    "sn": LandInfo("sn", "Sachsen", "https://www.revosax.sachsen.de", "https://github.com/eriklueth/landesrecht-sn-corpus-data"),
    "st": LandInfo("st", "Sachsen-Anhalt", "https://www.landesrecht.sachsen-anhalt.de", "https://github.com/eriklueth/landesrecht-st-corpus-data"),
    "sh": LandInfo("sh", "Schleswig-Holstein", "https://www.gesetze-rechtsprechung.sh.juris.de", "https://github.com/eriklueth/landesrecht-sh-corpus-data"),
    "th": LandInfo("th", "Thüringen", "https://landesrecht.thueringen.de", "https://github.com/eriklueth/landesrecht-th-corpus-data"),
}


_ADAPTER_MODULES = {"by": "by", "nw": "nw", "bw": "bw"}


def _adapter_status(iso: str) -> str:
    mod_name = _ADAPTER_MODULES.get(iso)
    if not mod_name:
        return "no adapter class"
    try:
        import importlib

        mod = importlib.import_module(f".{mod_name}", __package__)
        adapter_cls = next(
            (
                getattr(mod, n)
                for n in dir(mod)
                if n.endswith("Adapter") and not n.startswith("_")
            ),
            None,
        )
        if adapter_cls is None:
            return "adapter module present, no class"
        return f"adapter class present ({adapter_cls.__name__})"
    except Exception as exc:
        return f"adapter import failed: {exc}"


def cmd_status(args: argparse.Namespace) -> int:
    info = _REGISTRY.get(args.iso)
    if info is None:
        print(f"unknown Land ISO: {args.iso!r}. Known: {', '.join(sorted(_REGISTRY))}")
        return 2
    print(f"source:        land-{info.iso} ({info.name})")
    print(f"upstream:      {info.upstream}")
    print(f"data repo:     {info.data_repo}")
    print("phase:         8")
    print(f"adapter:       {_adapter_status(info.iso)}")
    print("status:        scaffold only, awaiting activation")
    return 0


def cmd_list(args: argparse.Namespace) -> int:  # noqa: ARG001
    for iso, info in sorted(_REGISTRY.items()):
        print(f"{iso}  {info.name:<22}  {info.upstream}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    info = _REGISTRY.get(args.iso)
    if info is None:
        print(f"unknown Land ISO: {args.iso!r}")
        return 2
    from .._base import ScaffoldInfo

    return not_implemented_command(
        ScaffoldInfo(
            source=f"land-{info.iso}",
            data_repo=info.data_repo,
            upstream=info.upstream,
            phase="8",
        )
    )(args)


def register(subparsers) -> None:
    p = subparsers.add_parser("land", help="Landesrecht (scaffold, 16 Bundeslaender)")
    sub = p.add_subparsers(dest="subcommand", required=True)

    p_list = sub.add_parser("list", help="list all known Laender")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="scaffold status for one Land")
    p_status.add_argument("iso", choices=sorted(_REGISTRY))
    p_status.set_defaults(func=cmd_status)

    p_sync = sub.add_parser("sync", help="run pipeline for one Land (not yet wired)")
    p_sync.add_argument("iso", choices=sorted(_REGISTRY))
    p_sync.add_argument("--limit", type=int, default=None)
    p_sync.set_defaults(func=cmd_sync)
