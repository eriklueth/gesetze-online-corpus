from gesetze_corpus.parse import ParsedAbsatz, ParsedSatz, ParsedSection
from gesetze_corpus.render import render_section_markdown


def _absatz(absatz: str, text: str) -> ParsedAbsatz:
    return ParsedAbsatz(
        absatz=absatz, intro="", saetze=[ParsedSatz(nummer=1, text=text)]
    )


def _sample_section() -> ParsedSection:
    return ParsedSection(
        kind="paragraph",
        number="\u00a7 14a",
        heading="Begriffsbestimmung",
        breadcrumb=["Buch 1", "Abschnitt 3"],
        absaetze=[
            _absatz("1", "Erster Absatz."),
            _absatz("2", "Zweiter Absatz."),
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


def test_numbered_saetze_render_with_sup_markers():
    section = ParsedSection(
        kind="paragraph",
        number="\u00a7 1",
        heading="",
        breadcrumb=[],
        absaetze=[
            ParsedAbsatz(
                absatz="1",
                intro="",
                saetze=[
                    ParsedSatz(nummer=1, text="Erster Satz."),
                    ParsedSatz(nummer=2, text="Zweiter Satz."),
                ],
            )
        ],
    )
    md = render_section_markdown(
        schema_version="v2",
        bjnr="BJNRTEST001",
        jurabk="TESTG",
        section=section,
        stand_datum="2026-01-01",
    )
    assert "(1) <sup>1</sup>Erster Satz. <sup>2</sup>Zweiter Satz." in md
    assert "<sup>1</sup><sup>2</sup>" not in md
