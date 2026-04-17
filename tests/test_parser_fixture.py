from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from textwrap import dedent

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/parse/normalize_from_raw.py"
SPEC = spec_from_file_location("normalize_from_raw", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
normalize_xml = MODULE.normalize_xml


def test_normalize_xml_fixture_extracts_norms(tmp_path: Path):
    xml = dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <dokument>
          <norm>
            <metadaten>
              <jurabk>TESTG</jurabk>
              <amtabk>TESTG</amtabk>
              <langue>Testgesetz</langue>
              <enbez>§ 1</enbez>
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
              <enbez>Art 2</enbez>
              <gliederungseinheit>
                <gliederungsbez>Abschnitt I</gliederungsbez>
              </gliederungseinheit>
              <titel>Weitere Regel</titel>
            </metadaten>
            <textdaten>
              <text>
                <Content>
                  <P>Ein unnummerierter Absatz.</P>
                </Content>
              </text>
            </textdaten>
          </norm>
        </dokument>
        """
    ).strip()

    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(xml, encoding="utf-8")

    payload = normalize_xml(xml_path, {
        "law_id": "test-law",
        "title": "Testgesetz",
        "zip_url": "https://example.com/test.zip",
        "xml_stem": "BJNRTEST0001",
    })

    assert payload["canonical_id"] == "TESTG"
    assert payload["title"] == "Testgesetz"
    assert len(payload["sections"]) == 2
    assert payload["sections"][0]["number"] == "§ 1"
    assert payload["sections"][0]["content"][0]["absatz"] == "1"
    assert payload["sections"][1]["number"] == "Abschnitt I Art 2"
    assert payload["sections"][1]["content"][0]["text"] == "Ein unnummerierter Absatz."
