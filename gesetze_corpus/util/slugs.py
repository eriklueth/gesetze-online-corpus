from __future__ import annotations

import re
import unicodedata

_PARAGRAPH_RE = re.compile(r"^§+\s*(\d+)([a-zA-Z]?)\b")
_ARTICLE_RE = re.compile(r"^(?:Art\.?|Artikel)\s*(\d+)([a-zA-Z]?)\b")
_ANNEX_RE = re.compile(r"^Anlage\s*(\d+)?([a-zA-Z]?)\b")


def classify_enbez(enbez: str) -> tuple[str, str] | None:
    """Classify an enbez string.

    Returns (kind, padded_name) where kind is one of
    ``paragraph``, ``article``, ``annex`` or None if the enbez does not
    describe a file-worthy unit (e.g. pure gliederungseinheit).
    """
    if not enbez:
        return None
    text = enbez.strip()

    m = _PARAGRAPH_RE.match(text)
    if m:
        num, suffix = m.group(1), m.group(2).lower()
        return "paragraph", f"{int(num):04d}{suffix}"

    m = _ARTICLE_RE.match(text)
    if m:
        num, suffix = m.group(1), m.group(2).lower()
        return "article", f"art-{int(num):04d}{suffix}"

    m = _ANNEX_RE.match(text)
    if m:
        num = m.group(1)
        suffix = (m.group(2) or "").lower()
        base = f"{int(num):04d}" if num else "0000"
        return "annex", f"{base}{suffix}"

    return None


_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


def slugify_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text
