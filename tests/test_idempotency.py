from gesetze_corpus.canonical import canonicalize_json_dump, canonicalize_xml_bytes
from gesetze_corpus.parse import parse_law_xml
from gesetze_corpus.render import render_section_markdown

from .test_xml_parser import SAMPLE


def test_render_is_stable_across_reparsing():
    law = parse_law_xml(SAMPLE, bjnr="BJNRTEST001")
    section = law.sections[0]
    md1 = render_section_markdown(
        schema_version="v1",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2024-01-01",
    )
    md2 = render_section_markdown(
        schema_version="v1",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2024-01-01",
    )
    assert md1 == md2


def test_canonical_xml_is_idempotent_on_law_fixture():
    once = canonicalize_xml_bytes(SAMPLE)
    twice = canonicalize_xml_bytes(once)
    assert once == twice


def test_canonical_json_is_idempotent():
    data = {"z": 1, "a": {"c": 3, "b": 2}}
    once = canonicalize_json_dump(data)
    import json
    twice = canonicalize_json_dump(json.loads(once))
    assert once == twice
