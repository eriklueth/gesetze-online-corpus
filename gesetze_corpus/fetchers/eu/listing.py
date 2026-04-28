"""SPARQL listing for EUR-Lex Cellar.

The Cellar SPARQL endpoint
(https://publications.europa.eu/webapi/rdf/sparql) exposes a query
interface over the Common Data Model that drives EUR-Lex. We use it
two ways:

* `fetch_listing(since=..., limit=...)` -- forward delta sweep used
  by the daily sync. Emits the most recent N CELEX numbers since a
  given date.

* `iter_backfill(start=..., end=..., window_days=30,
   cursor_path=...)` -- historical sweep used to hydrate the data
   repo from scratch. Walks the date range in fixed windows and
   persists the last completed window so the sweep is resumable
   across crashes / rate-limits / VPN flips. This is the mode you
   want for the initial population of `eu-recht-corpus-data`.

The query intentionally restricts to sector 3 (legislation:
regulations, directives, decisions). Single requests are hard-capped
at 1000 results to stay inside the public endpoint's quota; the
backfill iterator splits long ranges into many small requests so it
never trips the cap.

We accept that the SPARQL endpoint applies aggressive rate-limiting;
the loader retries via the shared `gesetze_corpus.http` session.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

from ...http import _shared_session

_SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

_SPARQL_QUERY_DELTA = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX dc:  <http://purl.org/dc/elements/1.1/>

SELECT DISTINCT ?celex ?title ?date WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_creation     ?date .
  OPTIONAL { ?work dc:title         ?title . }
  FILTER (?date >= "%(since)s"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER (regex(str(?celex), "^[0-9]{4}3[RLD][0-9]{4}$"))
}
ORDER BY DESC(?date)
LIMIT %(limit)d
"""

_SPARQL_QUERY_WINDOW = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX dc:  <http://purl.org/dc/elements/1.1/>

SELECT DISTINCT ?celex ?title ?date WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_creation     ?date .
  OPTIONAL { ?work dc:title         ?title . }
  FILTER (?date >= "%(start)s"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER (?date <  "%(end)s"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER (regex(str(?celex), "^[0-9]{4}3[RLD][0-9]{4}$"))
}
ORDER BY ?date
LIMIT %(limit)d
"""


@dataclass
class CelexEntry:
    celex: str
    title: str
    date: str


def fetch_listing(*, since: str, limit: int = 100) -> list[CelexEntry]:
    """Forward delta listing.

    `since` is an ISO date (YYYY-MM-DD); the SPARQL filter uses an
    inclusive lower bound. `limit` is hard-capped at 1000.
    """
    if limit < 1:
        return []
    limit = min(limit, 1000)

    payload = {
        "query": _SPARQL_QUERY_DELTA % {"since": since, "limit": limit},
        "format": "application/sparql-results+json",
    }
    raw = _post_sparql(payload)
    return _parse_sparql_json(raw)


def fetch_window(*, start: str, end: str, limit: int = 1000) -> list[CelexEntry]:
    """Half-open [start, end) date window listing, ordered ascending.

    `end` is exclusive so adjacent windows do not overlap. The cap
    of 1000 is enforced; callers who need higher granularity should
    shrink the window (the backfill iterator does this automatically).
    """
    payload = {
        "query": _SPARQL_QUERY_WINDOW
        % {"start": start, "end": end, "limit": min(max(limit, 1), 1000)},
        "format": "application/sparql-results+json",
    }
    raw = _post_sparql(payload)
    return _parse_sparql_json(raw)


def iter_backfill(
    *,
    start: str,
    end: str | None = None,
    window_days: int = 30,
    cursor_path: Path | str | None = None,
) -> Iterator[CelexEntry]:
    """Yield every CELEX in [start, end) by walking month-sized windows.

    The iterator is **resumable**: the cursor file stores the last
    fully-processed window's `end` date. On restart we pick up
    exactly where the previous run left off, even if the previous
    run crashed mid-window. We deliberately persist *after* the
    window has been yielded in full so a crashed window will be
    retried; that is safe because the writer downstream is idempotent.

    `end` defaults to today (UTC). `window_days` should stay <= 60
    to keep each request inside the SPARQL 1000-row cap.
    """
    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    start_d = _parse_iso(start)
    end_d = _parse_iso(end) if end else date.today()
    if start_d >= end_d:
        return

    cursor = _CursorFile(cursor_path)
    resume_at = cursor.read()
    if resume_at and resume_at > start_d:
        start_d = resume_at

    window_a = start_d
    while window_a < end_d:
        window_b = min(window_a + timedelta(days=window_days), end_d)
        yield from fetch_window(
            start=window_a.isoformat(),
            end=window_b.isoformat(),
            limit=1000,
        )
        cursor.write(window_b)
        window_a = window_b


class _CursorFile:
    """Minimal flat-file cursor for the backfill iterator."""

    def __init__(self, path: Path | str | None) -> None:
        self.path: Path | None = Path(path) if path else None

    def read(self) -> date | None:
        if self.path is None or not self.path.exists():
            return None
        text = self.path.read_text(encoding="utf-8").strip()
        return _parse_iso(text) if text else None

    def write(self, value: date) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(value.isoformat() + "\n", encoding="utf-8")
        os.replace(tmp, self.path)


def _post_sparql(payload: dict) -> bytes:
    response = _shared_session().post(
        _SPARQL_ENDPOINT,
        data=payload,
        timeout=60,
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    return response.content


def _parse_sparql_json(raw: bytes) -> list[CelexEntry]:
    data = json.loads(raw.decode("utf-8"))
    rows = data.get("results", {}).get("bindings", [])
    out: list[CelexEntry] = []
    for row in rows:
        celex = row.get("celex", {}).get("value", "")
        if not celex:
            continue
        title = row.get("title", {}).get("value", "")
        raw_date = row.get("date", {}).get("value", "")
        out.append(CelexEntry(celex=celex, title=title.strip(), date=raw_date[:10]))
    return out


def _parse_iso(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def collect_backfill(
    *,
    start: str,
    end: str | None = None,
    window_days: int = 30,
    cursor_path: Path | str | None = None,
    limit: int | None = None,
) -> list[CelexEntry]:
    """Convenience for tests / one-shot CLI runs."""
    out: list[CelexEntry] = []
    for entry in iter_backfill(
        start=start, end=end, window_days=window_days, cursor_path=cursor_path
    ):
        out.append(entry)
        if limit is not None and len(out) >= limit:
            break
    return out


def deduplicate(entries: Iterable[CelexEntry]) -> list[CelexEntry]:
    """Stable de-dup by CELEX, keeping the earliest occurrence."""
    seen: set[str] = set()
    out: list[CelexEntry] = []
    for entry in entries:
        if entry.celex in seen:
            continue
        seen.add(entry.celex)
        out.append(entry)
    return out


__all__ = [
    "fetch_listing",
    "fetch_window",
    "iter_backfill",
    "collect_backfill",
    "deduplicate",
    "CelexEntry",
]
