"""recht.bund.de / NeuRIS client scaffold.

NeuRIS publishes official promulgation events (Verkuendungsereignisse)
with BGBl-Fundstelle and ELI. This is the primary source we want for
Phase C v2 — it replaces the `stand_datum` approximation in
`events/detect.py` with real events and per-section effective dates
when the upstream metadata allows it.

Stability notes as of April 2026:

- The public API surface is still stabilizing. We deliberately keep
  the adapter small and document the shape we expect, so changes
  upstream are localized to this file.
- The canonical ID is the ELI (European Legislation Identifier). NeuRIS
  exposes both ELI and a NeuRIS-internal docId; we pin to ELI.
- The endpoint URLs below are placeholders that need to be verified
  against the live portal at activation time (`GESETZE_NEURIS_ENABLED=1`).

When this module is activated:

1. `resolve_events(bjnr, sha256_change_range)` returns a list of
   `PromulgationEvent` that overlap the observed snapshot delta.
2. `events/detect.py` prefers NeuRIS events over the `stand_datum`
   heuristic when available, falls back gracefully otherwise.
3. `meta.json` grows an `eli` field sourced here.

See docs/ROADMAP.md phase 1 for rollout.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_ENABLED = os.environ.get("GESETZE_NEURIS_ENABLED") == "1"
_BASE_URL = os.environ.get(
    "GESETZE_NEURIS_BASE",
    "https://api.recht.bund.de/v1",  # verify at activation time
)


@dataclass(frozen=True)
class PromulgationEvent:
    """A single Verkuendungsereignis as reported by NeuRIS."""

    eli: str
    effective_date: str  # ISO-8601
    promulgation_date: str | None
    bgbl_citation: str | None  # e.g. "BGBl. 2026 I Nr. 3"
    amending_act_title: str | None
    affected_law_ids: list[str] = field(default_factory=list)
    affected_sections: list[str] = field(default_factory=list)
    raw: dict | None = None


def is_enabled() -> bool:
    """True when NeuRIS lookups should be attempted."""
    return _ENABLED


def resolve_events(
    bjnr: str,
    around_date: str | None = None,
) -> list[PromulgationEvent]:
    """Return promulgation events for a law.

    Scaffold: returns an empty list when NeuRIS is disabled (the
    default). When enabled, makes an HTTP call and decodes into
    `PromulgationEvent`s. The decoder is intentionally forgiving —
    unknown fields are preserved in `raw` for later analysis.
    """
    if not _ENABLED:
        return []

    # Deliberately avoid implementing the real call until the upstream
    # schema is stable. The activation PR adds:
    #   r = http.get(f"{_BASE_URL}/laws/{bjnr}/events", params={"around": around_date})
    #   return [_decode_event(e) for e in r.json().get("items", [])]
    return []


def _decode_event(payload: dict) -> PromulgationEvent:
    """Robust NeuRIS -> PromulgationEvent decoder.

    Kept separate so it can be unit-tested against recorded fixtures
    without touching the network.
    """
    return PromulgationEvent(
        eli=payload.get("eli") or "",
        effective_date=payload.get("effectiveDate") or payload.get("stand_datum") or "",
        promulgation_date=payload.get("promulgationDate"),
        bgbl_citation=payload.get("bgblCitation"),
        amending_act_title=(payload.get("amendingAct") or {}).get("title"),
        affected_law_ids=list(payload.get("affectedLaws") or []),
        affected_sections=list(payload.get("affectedSections") or []),
        raw=payload,
    )
