from textwrap import dedent

from gesetze_corpus.parse import parse_law_xml


SAMPLE = dedent(
    """\
    <?xml version="1.0" encoding="utf-8"?>
    <dokumente>
      <norm>
        <metadaten>
          <jurabk>TESTG</jurabk>
          <amtabk>TESTG</amtabk>
          <langue>Testgesetz</langue>
          <ausfertigung-datum>2020-01-01</ausfertigung-datum>
          <standangabe>
            <standtyp>Neuf</standtyp>
            <standkommentar>Neugefasst durch Bek. v. 1.3.2022</standkommentar>
          </standangabe>
        </metadaten>
        <textdaten/>
      </norm>
      <norm>
        <metadaten>
          <enbez>\u00a7 1</enbez>
          <titel>Begriffsbestimmung</titel>
        </metadaten>
        <textdaten>
          <text>
            <Content>
              <P>(1) Alpha.</P>
              <P>(2) Beta.</P>
            </Content>
          </text>
        </textdaten>
      </norm>
      <norm>
        <metadaten>
          <enbez>Anlage 1</enbez>
          <titel>Tabelle</titel>
        </metadaten>
        <textdaten>
          <text>
            <Content>
              <P>Ein unnummerierter Absatz.</P>
            </Content>
          </text>
        </textdaten>
      </norm>
    </dokumente>
    """
).encode("utf-8")


def test_parses_head_meta():
    law = parse_law_xml(SAMPLE, bjnr="BJNRTEST001")
    assert law.jurabk == "TESTG"
    assert law.title == "Testgesetz"
    assert law.ausfertigung_datum == "2020-01-01"
    assert law.stand_datum == "2022-03-01"


def test_parses_paragraph_and_strips_absatz_prefix():
    law = parse_law_xml(SAMPLE, bjnr="BJNRTEST001")
    p = [s for s in law.sections if s.kind == "paragraph"]
    assert len(p) == 1
    sec = p[0]
    assert sec.number == "§ 1"
    assert sec.heading == "Begriffsbestimmung"
    assert len(sec.absaetze) == 2
    assert sec.absaetze[0].absatz == "1"
    assert sec.absaetze[0].text == "Alpha."
    assert sec.absaetze[1].absatz == "2"
    assert sec.absaetze[1].text == "Beta."


def test_parses_annex_with_implicit_absatz_id():
    law = parse_law_xml(SAMPLE, bjnr="BJNRTEST001")
    a = [s for s in law.sections if s.kind == "annex"]
    assert len(a) == 1
    sec = a[0]
    assert sec.number == "Anlage 1"
    assert sec.absaetze[0].absatz == "1"
    assert sec.absaetze[0].text == "Ein unnummerierter Absatz."
