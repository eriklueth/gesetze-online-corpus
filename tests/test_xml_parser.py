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
    assert sec.number == "\u00a7 1"
    assert sec.heading == "Begriffsbestimmung"
    assert len(sec.absaetze) == 2

    a1 = sec.absaetze[0]
    assert a1.absatz == "1"
    assert a1.intro == ""
    assert len(a1.saetze) == 1
    assert a1.saetze[0].nummer == 1
    assert a1.saetze[0].text == "Alpha."

    a2 = sec.absaetze[1]
    assert a2.absatz == "2"
    assert a2.saetze[0].text == "Beta."


def test_parses_annex_with_implicit_absatz_id():
    law = parse_law_xml(SAMPLE, bjnr="BJNRTEST001")
    a = [s for s in law.sections if s.kind == "annex"]
    assert len(a) == 1
    sec = a[0]
    assert sec.number == "Anlage 1"
    assert sec.absaetze[0].absatz == "1"
    assert sec.absaetze[0].saetze[0].text == "Ein unnummerierter Absatz."


SUP_TAIL_SAMPLE = dedent(
    """\
    <?xml version="1.0" encoding="utf-8"?>
    <dokumente>
      <norm>
        <metadaten>
          <jurabk>TESTG</jurabk>
          <langue>Testgesetz mit Satznummerierung</langue>
        </metadaten>
        <textdaten/>
      </norm>
      <norm>
        <metadaten>
          <enbez>\u00a7 7g</enbez>
          <titel>Investitionsabzug</titel>
        </metadaten>
        <textdaten>
          <text format="XML">
            <Content>
              <P>(1) <SUP class="Rec">1</SUP>Steuerpflichtige k\u00f6nnen abziehen. <SUP class="Rec">2</SUP>Voraussetzung ist, wenn <DL Type="arabic"><DT>1.</DT><DD>der Gewinn ermittelt wird;</DD><DT>2.</DT><DD>das Wirtschaftsgut genutzt wird.</DD></DL></P>
              <P>(2) <SUP class="Rec">1</SUP>Weiter. <SUP class="Rec">2</SUP>Schluss.</P>
              <P>(3) (weggefallen)</P>
              <P>(4) <SUP class="Rec">1</SUP>Wird das Wirtschaftsgut nicht genutzt, ist der Abzug r\u00fcckg\u00e4ngig zu machen.</P>
            </Content>
          </text>
        </textdaten>
      </norm>
    </dokumente>
    """
).encode("utf-8")


def test_sup_splits_into_structured_saetze():
    law = parse_law_xml(SUP_TAIL_SAMPLE, bjnr="BJNRTEST007")
    sec = [s for s in law.sections if s.kind == "paragraph"][0]
    assert len(sec.absaetze) == 4

    a1 = sec.absaetze[0]
    assert a1.absatz == "1"
    assert len(a1.saetze) == 2
    assert a1.saetze[0].nummer == 1
    assert a1.saetze[0].text.startswith("Steuerpflichtige k\u00f6nnen")
    assert a1.saetze[1].nummer == 2
    assert "Voraussetzung ist" in a1.saetze[1].text
    assert "1. der Gewinn ermittelt wird" in a1.saetze[1].text
    assert "2. das Wirtschaftsgut genutzt wird" in a1.saetze[1].text

    a2 = sec.absaetze[1]
    assert [s.nummer for s in a2.saetze] == [1, 2]
    assert a2.saetze[0].text == "Weiter."
    assert a2.saetze[1].text == "Schluss."

    a3 = sec.absaetze[2]
    assert a3.absatz == "3"
    assert len(a3.saetze) == 1
    assert a3.saetze[0].text == "(weggefallen)"

    a4 = sec.absaetze[3]
    assert a4.absatz == "4"
    assert a4.saetze[0].nummer == 1
    assert a4.saetze[0].text.startswith("Wird das Wirtschaftsgut")


TABLE_SAMPLE = dedent(
    """\
    <?xml version="1.0" encoding="utf-8"?>
    <dokumente>
      <norm>
        <metadaten>
          <jurabk>TSTG</jurabk>
          <langue>Tabellentest</langue>
        </metadaten>
        <textdaten/>
      </norm>
      <norm>
        <metadaten>
          <enbez>\u00a7 2</enbez>
          <titel>Tabelle</titel>
        </metadaten>
        <textdaten>
          <text format="XML">
            <Content>
              <P>(1) Die Werte sind: <table><tbody><row><entry>A</entry><entry>1</entry></row><row><entry>B</entry><entry>2</entry></row></tbody></table></P>
            </Content>
          </text>
        </textdaten>
      </norm>
    </dokumente>
    """
).encode("utf-8")


def test_table_inlined_as_brackets():
    law = parse_law_xml(TABLE_SAMPLE, bjnr="BJNRTEST002")
    sec = [s for s in law.sections if s.kind == "paragraph"][0]
    a = sec.absaetze[0]
    text = a.saetze[0].text
    assert "[A | 1; B | 2]" in text
    assert text.startswith("Die Werte sind:")
