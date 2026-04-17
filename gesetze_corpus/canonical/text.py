from __future__ import annotations

import json
import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, ["\u200b", "\u200c", "\u200d", "\ufeff"]), None)
_WHITESPACE_RUN = re.compile(r"\s+")


def canonicalize_text(text: str | None) -> str:
    """Normalize a short text field (title, heading, etc.).

    Steps follow docs/CANONICAL.md:
    NFC, strip control chars except \\n and \\t, nbsp -> space,
    zero-width removal, collapse whitespace runs, strip.
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_ZERO_WIDTH)
    text = text.replace("\u00a0", " ")
    out: list[str] = []
    for ch in text:
        if ch in ("\n", "\t"):
            out.append(ch)
            continue
        if unicodedata.category(ch) == "Cc":
            continue
        out.append(ch)
    text = "".join(out)
    text = _WHITESPACE_RUN.sub(" ", text)
    return text.strip()


def canonicalize_paragraph(text: str | None) -> str:
    """Canonicalize a paragraph body.

    Same rules as canonicalize_text, kept on one line. Paragraphs never
    contain internal hard line breaks in our model; multi-paragraph
    content is always emitted as separate absatz entries.
    """
    return canonicalize_text(text)


def canonicalize_json_dump(payload: object) -> str:
    """Return a canonical JSON string ending with exactly one newline."""
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    )
