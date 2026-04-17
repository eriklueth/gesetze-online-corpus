from gesetze_corpus.canonical import canonicalize_xml_bytes


def test_xml_is_idempotent():
    raw = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<!-- some comment -->
<root b="2" a="1">
  <child>Text</child>
</root>
"""
    once = canonicalize_xml_bytes(raw)
    twice = canonicalize_xml_bytes(once)
    assert once == twice


def test_xml_removes_comments_and_sorts_attrs():
    raw = b"""<?xml version="1.0"?>
<!-- ignore me -->
<r z="1" a="2"><c/></r>
"""
    out = canonicalize_xml_bytes(raw).decode("utf-8")
    assert "ignore me" not in out
    assert out.index('a="2"') < out.index('z="1"')
    assert out.endswith("\n")
