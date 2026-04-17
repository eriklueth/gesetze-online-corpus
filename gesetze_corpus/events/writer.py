from __future__ import annotations

from pathlib import Path

from .. import SCHEMA_VERSION, TOOLING_ID
from ..canonical import canonicalize_json_dump


def write_event(
    *,
    data_repo: Path,
    event_id: str,
    effective_date: str,
    payload: dict,
) -> Path:
    """Write an event file to ``events/<year>/<event_id>.json``.

    ``payload`` must already be mostly built by the caller. This helper
    only injects ``schema_version`` and ``tooling_version``, enforces
    canonical JSON dumping and returns the written path.
    """
    year = effective_date[:4]
    target_dir = data_repo / "events" / year
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{event_id}.json"

    body = dict(payload)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("tooling_version", TOOLING_ID)
    body.setdefault("event_id", event_id)
    body.setdefault("effective_date", effective_date)

    target.write_text(canonicalize_json_dump(body), encoding="utf-8")
    return target
