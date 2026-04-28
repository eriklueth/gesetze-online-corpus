"""Markdown renderer + on-disk writer for EUR-Lex documents.

Default layout (mirrors gesetze-corpus-data, single-language DE):

    laws/<celex>/
        meta.json
        articles/<padded>.md   -- one Markdown file per article

Multi-language layout (opt-in via ``multi_lang=True``), keeps each
language self-contained while sharing the CELEX folder:

    laws/<celex>/<lang>/
        meta.json
        articles/<padded>.md

Padded ordinal: every Cellar-emitted article number is normalised to
zero-padded 4-digit form so directory listings sort the same way the
EU document itself does. The fallback "Praeambel"/"Anhang" articles
get fixed prefixes (`0000-praeambel.md`, `9000-anhang.md`).

`meta.json` carries the `oj_reference` (Official Journal short
citation, e.g. `"L 119/1"`) when EUR-Lex exposes it, and `null`
otherwise. Older consolidated-only documents are not always paginated
in OJ so callers must treat it as best-effort metadata.

The writer is idempotent: file content is rewritten only when its
sha256 changes, and articles that disappear in a re-sync are deleted.
Switching `multi_lang` writes into a new folder; we deliberately do
**not** migrate existing files between layouts so a half-done sync
never deletes data on a flag flip.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ... import SCHEMA_VERSION, TOOLING_ID
from .detail import EuArticle, EuDocument


@dataclass
class WriteResult:
    celex: str
    written: list[str]
    unchanged: list[str]
    deleted: list[str]


def render_article_markdown(doc: EuDocument, article: EuArticle) -> str:
    fm = {
        "schema_version": SCHEMA_VERSION,
        "source": "eu",
        "celex": doc.celex,
        "doc_type": doc.doc_type,
        "language": doc.language,
        "article_number": article.number or "",
        "ordinal_padded": _pad_article_number(article.number),
        "heading": article.heading or "",
    }
    lines = [_yaml_block(fm)]
    label = article.number or "0"
    title = article.heading or doc.title or doc.celex
    lines.append(f"# Artikel {label} - {title}".rstrip(" -"))
    lines.append("")
    for paragraph in article.paragraphs:
        text = paragraph.strip()
        if text:
            lines.append(text)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_eu_document(
    document: EuDocument,
    *,
    data_repo: Path,
    multi_lang: bool = False,
) -> WriteResult:
    if not document.celex:
        raise ValueError("EuDocument.celex is required")
    base = Path(data_repo) / "laws" / document.celex
    if multi_lang:
        if not document.language:
            raise ValueError("EuDocument.language is required for multi_lang layout")
        base = base / document.language.lower()
    articles_dir = base / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    unchanged: list[str] = []
    expected: set[str] = set()

    for article in document.articles:
        filename = _filename_for(article)
        expected.add(filename)
        target = articles_dir / filename
        body = render_article_markdown(document, article)
        if target.exists() and target.read_text(encoding="utf-8") == body:
            unchanged.append(filename)
            continue
        target.write_text(body, encoding="utf-8")
        written.append(filename)

    deleted: list[str] = []
    for existing in sorted(p.name for p in articles_dir.glob("*.md")):
        if existing not in expected:
            (articles_dir / existing).unlink()
            deleted.append(existing)

    meta_path = base / "meta.json"
    meta_text = json.dumps(
        _meta_payload(document), indent=2, ensure_ascii=False, sort_keys=True
    ) + "\n"
    if not meta_path.exists() or meta_path.read_text(encoding="utf-8") != meta_text:
        meta_path.write_text(meta_text, encoding="utf-8")
        written.append("meta.json")
    else:
        unchanged.append("meta.json")

    return WriteResult(
        celex=document.celex,
        written=written,
        unchanged=unchanged,
        deleted=deleted,
    )


def _filename_for(article: EuArticle) -> str:
    label = (article.number or "").strip().lower()
    if not label or label == "0" or label == "praeambel":
        return "0000-praeambel.md"
    if label == "anhang":
        return "9000-anhang.md"
    return f"{_pad_article_number(article.number)}.md"


def _pad_article_number(num: str) -> str:
    if not num:
        return "0000"
    m = re.match(r"^(\d+)([a-zA-Z]?)$", num.strip())
    if m:
        return f"{int(m.group(1)):04d}{m.group(2).lower()}"
    return re.sub(r"[^A-Za-z0-9]+", "-", num.strip().lower()) or "0000"


def _meta_payload(document: EuDocument) -> dict:
    digest = hashlib.sha256()
    for article in document.articles:
        digest.update((article.number or "").encode("utf-8"))
        digest.update(b"\x00")
        digest.update((article.heading or "").encode("utf-8"))
        digest.update(b"\x00")
        for p in article.paragraphs:
            digest.update(p.encode("utf-8"))
            digest.update(b"\x01")
        digest.update(b"\x02")
    return {
        "schema_version": SCHEMA_VERSION,
        "tooling_version": TOOLING_ID,
        "source": "eu",
        "celex": document.celex,
        "title": document.title,
        "eli": document.eli,
        "oj_reference": document.oj_reference or None,
        "doc_type": document.doc_type,
        "language": document.language,
        "article_count": len(document.articles),
        "content_sha256": digest.hexdigest(),
    }


def _yaml_block(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_scalar(text: str) -> str:
    if not text:
        return '""'
    needs = any(c in text for c in ':"\\#') or text[0] in (" ", "-", "?", "[", "{")
    if needs:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


__all__ = ["render_article_markdown", "write_eu_document", "WriteResult"]
