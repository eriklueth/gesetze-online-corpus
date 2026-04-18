"""Re-render all laws from the locally cached ``source.xml`` files.

This does not talk to the network. It is the fast path after a parser /
renderer fix: every ``laws/<BJNR>/source.xml`` is re-parsed and the
Markdown tree + ``meta.json`` + ``toc.json`` are rewritten, while the
canonical XML and the sha256 stay exactly the same.

``sources/current/gii-index.json`` is left untouched - the per-law
index entries only depend on fields that don't change on a pure
re-render (zip_url, title, source_xml_sha256).
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .. import SCHEMA_VERSION
from ..canonical import canonicalize_json_dump
from ..parse import parse_law_xml
from ..render import build_meta_json, build_toc_json, render_section_markdown
from ..util.paths import ensure_dir
from ..util.slugs import classify_enbez

log = logging.getLogger(__name__)


@dataclass
class RerenderReport:
    total: int
    rewritten: int
    skipped: int
    failed: int
    failures: list[tuple[str, str]]


def _load_existing_meta(law_dir: Path) -> dict:
    mp = law_dir / "meta.json"
    if not mp.exists():
        return {}
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _rewrite_gii_index(data_repo: Path) -> None:
    """Regenerate sources/current/gii-index.json from local meta.json files.

    Needed after a schema bump that removes fields from the index
    (e.g. fetched_at). We key by gii_slug from each law's meta.json so
    the mapping stays stable with respect to the canonical XML.
    """
    index_path = data_repo / "sources" / "current" / "gii-index.json"
    existing_titles: dict[str, str] = {}
    existing_urls: dict[str, str] = {}
    if index_path.exists():
        try:
            prev = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
        for slug, entry in (prev.get("laws") or {}).items():
            if entry.get("title"):
                existing_titles[slug] = entry["title"]
            if entry.get("zip_url"):
                existing_urls[slug] = entry["zip_url"]

    laws_dir = data_repo / "laws"
    new_laws: dict[str, dict] = {}
    for law_dir in sorted(laws_dir.iterdir()):
        if not law_dir.is_dir():
            continue
        meta = _load_existing_meta(law_dir)
        if not meta:
            continue
        slug = meta.get("gii_slug") or ""
        if not slug:
            continue
        new_laws[slug] = {
            "bjnr": meta.get("bjnr") or law_dir.name,
            "source_xml_sha256": (meta.get("source_hashes") or {}).get(
                "source_xml_sha256"
            ),
            "title": existing_titles.get(slug) or meta.get("title"),
            "zip_url": existing_urls.get(slug, ""),
        }

    payload = {
        "laws": dict(sorted(new_laws.items())),
        "schema_version": SCHEMA_VERSION,
        "toc_source_url": "https://www.gesetze-im-internet.de/gii-toc.xml",
        "updated_at": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(canonicalize_json_dump(payload).encode("utf-8"))


def _rerender_one(law_dir: Path) -> tuple[str, bool, str | None]:
    bjnr = law_dir.name
    xml_path = law_dir / "source.xml"
    if not xml_path.exists():
        return bjnr, False, "no source.xml"
    xml_bytes = xml_path.read_bytes()
    sha = hashlib.sha256(xml_bytes).hexdigest()

    existing = _load_existing_meta(law_dir)
    gii_slug = existing.get("gii_slug") or ""
    zip_url = (existing.get("source_urls") or {}).get("gii_xml_zip") or ""
    html_url = (existing.get("source_urls") or {}).get("gii_html") or ""

    try:
        law = parse_law_xml(xml_bytes, bjnr=bjnr)
    except Exception as exc:
        return bjnr, False, f"parse error: {exc}"

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
        fname = f"{base}__{count}" if count else base
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

    keep_sections = [(s, f) for s, f in zip(law.sections, file_paths, strict=False) if f]
    law.sections = [s for s, _ in keep_sections]
    files_only = [f for _, f in keep_sections]

    toc = build_toc_json(law, files_only)
    (law_dir / "toc.json").write_bytes(
        canonicalize_json_dump(toc).encode("utf-8")
    )

    meta = build_meta_json(
        law,
        gii_slug=gii_slug,
        zip_url=zip_url,
        html_url=html_url,
        source_xml_sha256=sha,
    )
    (law_dir / "meta.json").write_bytes(
        canonicalize_json_dump(meta).encode("utf-8")
    )

    return bjnr, True, None


def rerender_all(data_repo: Path, *, workers: int = 4) -> RerenderReport:
    laws_dir = data_repo / "laws"
    if not laws_dir.exists():
        return RerenderReport(
            total=0, rewritten=0, skipped=0, failed=0, failures=[]
        )

    law_dirs = [p for p in sorted(laws_dir.iterdir()) if p.is_dir()]

    rewritten = 0
    skipped = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_rerender_one, d): d for d in law_dirs}
        total = len(law_dirs)
        for i, fut in enumerate(as_completed(futures), start=1):
            bjnr, wrote, err = fut.result()
            if err:
                if err == "no source.xml":
                    skipped += 1
                else:
                    failed += 1
                    failures.append((bjnr, err))
            elif wrote:
                rewritten += 1
            if i % 500 == 0:
                log.info("rerender progress: %d / %d", i, total)

    _rewrite_gii_index(data_repo)

    return RerenderReport(
        total=len(law_dirs),
        rewritten=rewritten,
        skipped=skipped,
        failed=failed,
        failures=failures,
    )
