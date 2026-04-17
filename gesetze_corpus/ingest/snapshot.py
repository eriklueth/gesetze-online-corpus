from __future__ import annotations

import hashlib
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .. import SCHEMA_VERSION
from ..canonical import canonicalize_json_dump, canonicalize_xml_bytes
from ..fetch import fetch_law_xml, fetch_toc, TocEntry
from ..http import build_session
from ..parse import parse_law_xml
from ..render import build_meta_json, build_toc_json, render_section_markdown
from ..util.paths import ensure_dir
from ..util.slugs import classify_enbez

log = logging.getLogger(__name__)


@dataclass
class SnapshotReport:
    total: int
    fetched: int
    unchanged: int
    written: int
    failed: int
    failures: list[tuple[str, str]]


def _html_url_from_zip(zip_url: str) -> str:
    if zip_url.endswith("/xml.zip"):
        return zip_url[: -len("xml.zip")]
    return zip_url


def _process_one(
    entry: TocEntry,
    data_repo: Path,
    previous_index: dict,
) -> tuple[str, dict, bool, bool]:
    """Fetch, canonicalize, parse and render one law.

    Returns (slug, index_entry, fetched_new, wrote_files).
    """
    session = build_session()
    asset = fetch_law_xml(session, entry.link)
    canonical_xml = canonicalize_xml_bytes(asset.xml_bytes)
    sha = hashlib.sha256(canonical_xml).hexdigest()

    prev = previous_index.get(entry.slug) or {}
    unchanged = prev.get("source_xml_sha256") == sha
    bjnr = asset.bjnr

    now_iso = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    fetched_at = prev.get("fetched_at") if unchanged else now_iso
    if not fetched_at:
        fetched_at = now_iso
    index_entry = {
        "bjnr": bjnr,
        "fetched_at": fetched_at,
        "source_xml_sha256": sha,
        "title": entry.title,
        "zip_url": entry.link,
    }

    if unchanged and (data_repo / "laws" / bjnr / "source.xml").exists():
        return entry.slug, index_entry, True, False

    law_dir = ensure_dir(data_repo / "laws" / bjnr)
    (law_dir / "source.xml").write_bytes(canonical_xml)

    law = parse_law_xml(canonical_xml, bjnr=bjnr)

    paragraphs_dir = law_dir / "paragraphs"
    annexes_dir = law_dir / "annexes"
    if paragraphs_dir.exists():
        shutil.rmtree(paragraphs_dir)
    if annexes_dir.exists():
        shutil.rmtree(annexes_dir)

    file_paths: list[str] = []
    filename_seen: dict[str, int] = {}
    for section in law.sections:
        classified = classify_enbez(section.number)
        if not classified:
            file_paths.append("")
            continue
        kind, padded = classified
        sub = "annexes" if kind == "annex" else "paragraphs"
        base = padded
        count = filename_seen.get(f"{sub}/{base}", 0)
        if count:
            fname = f"{base}__{count}"
        else:
            fname = base
        filename_seen[f"{sub}/{base}"] = count + 1
        target_dir = ensure_dir(law_dir / sub)
        rel = f"{sub}/{fname}.md"
        text = render_section_markdown(
            schema_version=SCHEMA_VERSION,
            bjnr=bjnr,
            jurabk=law.jurabk,
            section=section,
            stand_datum=law.stand_datum,
        )
        (target_dir / f"{fname}.md").write_bytes(text.encode("utf-8"))
        file_paths.append(rel)

    keep_sections = [(s, f) for s, f in zip(law.sections, file_paths) if f]
    law.sections = [s for s, _ in keep_sections]
    files_only = [f for _, f in keep_sections]

    toc = build_toc_json(law, files_only)
    (law_dir / "toc.json").write_bytes(
        canonicalize_json_dump(toc).encode("utf-8")
    )

    meta = build_meta_json(
        law,
        gii_slug=entry.slug,
        zip_url=entry.link,
        html_url=_html_url_from_zip(entry.link),
        source_xml_sha256=sha,
    )
    (law_dir / "meta.json").write_bytes(
        canonicalize_json_dump(meta).encode("utf-8")
    )

    return entry.slug, index_entry, True, True


def _load_previous_index(path: Path) -> dict:
    if not path.exists():
        return {}
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get("laws") or {}


def snapshot(
    data_repo: Path,
    *,
    limit: int | None = None,
    only_slug: str | None = None,
    workers: int = 4,
) -> SnapshotReport:
    session = build_session()
    entries = fetch_toc(session)
    if only_slug:
        entries = [e for e in entries if e.slug == only_slug]
    if limit is not None:
        entries = entries[:limit]

    ensure_dir(data_repo / "laws")
    ensure_dir(data_repo / "events")
    ensure_dir(data_repo / "sources" / "current")

    index_path = data_repo / "sources" / "current" / "gii-index.json"
    previous = _load_previous_index(index_path)
    current: dict[str, dict] = {}

    fetched = 0
    unchanged_count = 0
    written = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    def work(entry: TocEntry) -> tuple[str, dict, bool, bool] | None:
        try:
            return _process_one(entry, data_repo, previous)
        except Exception as exc:
            log.warning("failed %s: %s", entry.slug, exc)
            return (entry.slug, {}, False, False, str(exc))  # type: ignore[return-value]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, e) for e in entries]
        for fut in as_completed(futures):
            result = fut.result()
            if result is None:
                continue
            if len(result) == 5:
                slug, _, _, _, err = result  # type: ignore[misc]
                failed += 1
                failures.append((slug, err))
                continue
            slug, idx_entry, did_fetch, did_write = result
            current[slug] = idx_entry
            if did_fetch:
                fetched += 1
            if did_write:
                written += 1
            else:
                unchanged_count += 1

    merged = dict(previous)
    merged.update(current)
    sorted_index = {
        "laws": {k: merged[k] for k in sorted(merged.keys())},
        "schema_version": SCHEMA_VERSION,
        "toc_source_url": "https://www.gesetze-im-internet.de/gii-toc.xml",
        "updated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    index_path.write_bytes(canonicalize_json_dump(sorted_index).encode("utf-8"))

    return SnapshotReport(
        total=len(entries),
        fetched=fetched,
        unchanged=unchanged_count,
        written=written,
        failed=failed,
        failures=failures,
    )


def iter_laws(data_repo: Path) -> Iterable[Path]:
    laws_dir = data_repo / "laws"
    if not laws_dir.exists():
        return
    for child in sorted(laws_dir.iterdir()):
        if child.is_dir():
            yield child
