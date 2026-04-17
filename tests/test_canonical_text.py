from gesetze_corpus.canonical import (
    canonicalize_text,
    canonicalize_json_dump,
)


def test_nfc_normalization():
    composed = "\u00fc"
    decomposed = "u\u0308"
    assert canonicalize_text(decomposed) == composed


def test_collapse_whitespace_and_nbsp():
    s = "Hallo\u00a0 Welt\t\t  "
    assert canonicalize_text(s) == "Hallo Welt"


def test_removes_zero_width_and_controls():
    s = "A\u200bB\u0007C"
    assert canonicalize_text(s) == "ABC"


def test_json_dump_is_sorted_and_has_trailing_newline():
    out = canonicalize_json_dump({"b": 2, "a": 1})
    assert out.endswith("\n")
    assert out.index('"a"') < out.index('"b"')


def test_idempotent_text_roundtrip():
    s = "  §\u00a014a   ist\u200b wichtig. "
    once = canonicalize_text(s)
    twice = canonicalize_text(once)
    assert once == twice
