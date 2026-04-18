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
              <P>(1) <SUP class="Rec">1</SUP>Steuerpflichtige k\u00f6nnen abziehen. <SUP class="Rec">2</SUP>Voraussetzung ist, wenn <DL><DT>1.</DT><DD>der Gewinn ermittelt wird;</DD></DL></P>
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


def test_sup_removal_preserves_tail_text():
    """Regression: lxml's Element.remove() also drops the element's tail.

    The GII XML carries per-Satz markers like ``<SUP>1</SUP>`` inside
    each ``<P>`` Absatz. If we delete SUPs naively, every sentence
    following a SUP is lost - at best we keep text inside trailing
    ``<DL>`` blocks, at worst the entire Absatz goes blank. Before the
    fix, paragraphs like EStG \u00a7 7g (1)-(4) rendered as empty.
    """
    law = parse_law_xml(SUP_TAIL_SAMPLE, bjnr="BJNRTEST007")
    paragraphs = [s for s in law.sections if s.kind == "paragraph"]
    assert len(paragraphs) == 1
    sec = paragraphs[0]
    assert sec.number == "\u00a7 7g"
    assert len(sec.absaetze) == 4

    a1 = sec.absaetze[0]
    assert a1.absatz == "1"
    assert a1.text.startswith("Steuerpflichtige k\u00f6nnen abziehen.")
    assert "Voraussetzung ist" in a1.text
    assert "der Gewinn ermittelt wird" in a1.text

    a2 = sec.absaetze[1]
    assert a2.absatz == "2"
    assert "Weiter." in a2.text and "Schluss." in a2.text

    a3 = sec.absaetze[2]
    assert a3.absatz == "3"
    assert a3.text == "(weggefallen)"

    a4 = sec.absaetze[3]
    assert a4.absatz == "4"
    assert a4.text.startswith("Wird das Wirtschaftsgut")
    assert a4.text.endswith("r\u00fcckg\u00e4ngig zu machen.")
