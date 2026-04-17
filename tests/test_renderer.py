from gesetze_corpus.parse import ParsedAbsatz, ParsedSection
from gesetze_corpus.render import render_section_markdown


def _sample_section() -> ParsedSection:
    return ParsedSection(
        kind="paragraph",
        number="§ 14a",
        heading="Begriffsbestimmung",
        breadcrumb=["Buch 1", "Abschnitt 3"],
        absaetze=[
            ParsedAbsatz(absatz="1", text="Erster Absatz."),
            ParsedAbsatz(absatz="2", text="Zweiter Absatz."),
        ],
    )


def test_heading_no_double_paragraph_sign():
    section = _sample_section()
    md = render_section_markdown(
        schema_version="v1",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2024-01-01",
    )
    assert "# § 14a Begriffsbestimmung" in md
    assert "# § §" not in md


def test_frontmatter_stable_and_trailing_newline():
    section = _sample_section()
    md = render_section_markdown(
        schema_version="v1",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2024-01-01",
    )
    assert md.startswith("---\nschema_version: v1\n")
    assert md.endswith("\n")
    assert not md.endswith("\n\n")


def test_absatz_prefix_not_duplicated():
    section = _sample_section()
    md = render_section_markdown(
        schema_version="v1",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2024-01-01",
    )
    assert "(1) Erster Absatz." in md
    assert "(1) (1)" not in md
