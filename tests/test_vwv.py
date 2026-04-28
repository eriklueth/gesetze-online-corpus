"""Tests for the Bundes-Verwaltungsvorschriften (VwV) detail parser
and writer. These run on synthetic HTML fixtures so they stay
hermetic -- the live portal is not reachable from many CI runners.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("lxml")

from gesetze_corpus.fetchers.vwv.detail import parse_detail_html
from gesetze_corpus.fetchers.vwv.listing import parse_listing_html
from gesetze_corpus.fetchers.vwv.writer import (
    _pad_ordinal,
    render_section_markdown,
    write_vwv,
)


SAMPLE_HTML = b"""\
<html>
  <body>
    <h1 class="jnoverview">Allgemeine Verwaltungsvorschrift Beispiel</h1>
    <p class="jnsmall">AVwVBsp</p>
    <p class="jnsmall">Vom 12. Maerz 2020</p>

    <p class="jnenbez">1. Anwendungsbereich</p>
    <div class="jnhtml">
      <p>Diese Verwaltungsvorschrift regelt die Ausfuehrung des Beispielgesetzes.</p>
    </div>

    <p class="jnenbez">2. Begriffsbestimmungen</p>

    <p class="jnenbez">2.1 Behoerden</p>
    <div class="jnhtml">
      <p>Behoerden im Sinne dieser Vorschrift sind die zustaendigen Stellen.</p>
      <p>Auch bevollmaechtigte Dritte gelten als Behoerden.</p>
    </div>

    <p class="jnenbez">2.10 Anwendungsausnahmen</p>
    <div class="jnhtml">
      <p>Ausnahmen von der Anwendung sind moeglich.</p>
    </div>
  </body>
</html>
"""


def test_parse_detail_extracts_sections():
    doc = parse_detail_html(SAMPLE_HTML, url="http://example.org/avwvbsp.htm")
    assert doc.title.startswith("Allgemeine Verwaltungsvorschrift")
    assert doc.short == "AVwVBsp"
    assert doc.promulgation_date == "2020-03-12"
    ordinals = [s.ordinal for s in doc.sections]
    assert ordinals == ["1", "2", "2.1", "2.10"]
    leaf = next(s for s in doc.sections if s.ordinal == "2.1")
    assert "Behoerden im Sinne" in leaf.text
    assert "bevollmaechtigte" in leaf.text


def test_parse_detail_keeps_empty_grouping_section():
    doc = parse_detail_html(SAMPLE_HTML)
    grouping = next(s for s in doc.sections if s.ordinal == "2")
    assert grouping.heading == "Begriffsbestimmungen"
    # No body content, but the section still exists for navigation.
    assert grouping.text == ""


def test_pad_ordinal_sorts_decimal_correctly():
    assert _pad_ordinal("1") == "01"
    assert _pad_ordinal("1.10") == "01.10"
    assert _pad_ordinal("1.2") == "01.02"
    # Padded decimals sort the way humans expect.
    padded = sorted([_pad_ordinal(x) for x in ["1.10", "1.2", "1.1", "2"]])
    assert padded == ["01.01", "01.02", "01.10", "02"]


def test_render_section_markdown_includes_frontmatter_and_heading():
    doc = parse_detail_html(SAMPLE_HTML)
    section = next(s for s in doc.sections if s.ordinal == "1")
    md = render_section_markdown("AVwVBsp", section)
    assert md.startswith("---\n")
    assert "ordinal: 1" in md
    assert "ordinal_padded: 01" in md
    assert "# 1 Anwendungsbereich" in md


def test_write_vwv_is_idempotent(tmp_path: Path):
    doc = parse_detail_html(SAMPLE_HTML, url="http://example.org/avwvbsp.htm")
    first = write_vwv(doc, data_repo=tmp_path)
    assert first.written, "first write must produce files"
    second = write_vwv(doc, data_repo=tmp_path)
    assert not second.written, f"second write touched {second.written}"
    assert second.unchanged
    # Section files exist with expected names.
    sections = sorted((tmp_path / "laws" / first.slug / "sections").glob("*.md"))
    assert {p.name for p in sections} >= {"01.md", "02.md", "02.01.md", "02.10.md"}


LISTING_HTML = b"""\
<html>
  <body>
    <h2>Bundesministerium des Innern</h2>
    <h3>Auslaenderrecht</h3>
    <ul>
      <li><a href="auslg.html">AuslG Allgemeine Verwaltungsvorschrift</a></li>
      <li><a href="aufenthg.html">AufenthG-VwV Aufenthaltsgesetz</a></li>
    </ul>
    <h3>Pass- und Personalausweisrecht</h3>
    <ul>
      <li><a href="passg.html">PassG-VwV Passgesetz</a></li>
    </ul>
    <h2>Bundesministerium der Finanzen</h2>
    <h3>Steuerrecht</h3>
    <p class="jncategory">Einkommensteuer</p>
    <ul>
      <li><a href="estr.html">EStR Einkommensteuer-Richtlinien</a></li>
    </ul>
    <ul>
      <li><a href="ohne-kontext.html">Orphan ohne Heading-Kontext</a></li>
    </ul>
  </body>
</html>
"""


def test_parse_listing_assigns_breadcrumbs():
    entries = parse_listing_html(LISTING_HTML)
    by_short = {e.short: e for e in entries}

    assert by_short["AuslG"].breadcrumb == (
        "Bundesministerium des Innern",
        "Auslaenderrecht",
    )
    assert by_short["AufenthG-VwV"].breadcrumb == (
        "Bundesministerium des Innern",
        "Auslaenderrecht",
    )
    # Resetting h3 inside the same h2 must drop the old h3.
    assert by_short["PassG-VwV"].breadcrumb == (
        "Bundesministerium des Innern",
        "Pass- und Personalausweisrecht",
    )
    # Switching h2 must clear stale h3.
    assert by_short["EStR"].breadcrumb == (
        "Bundesministerium der Finanzen",
        "Steuerrecht",
        "Einkommensteuer",
    )


def test_parse_listing_skips_links_without_html_target():
    html = b"""<html><body>
      <h2>Bundesministerium des Innern</h2>
      <ul>
        <li><a href="https://example.org/external">External (kein .html)</a></li>
        <li><a href="auslg.html">AuslG Foo</a></li>
      </ul>
    </body></html>"""
    entries = parse_listing_html(html)
    assert [e.short for e in entries] == ["AuslG"]


def test_write_vwv_removes_obsolete_sections(tmp_path: Path):
    doc = parse_detail_html(SAMPLE_HTML)
    write_vwv(doc, data_repo=tmp_path)

    # Drop a section and write again -> the obsolete file must vanish.
    doc.sections = [s for s in doc.sections if s.ordinal != "2.10"]
    result = write_vwv(doc, data_repo=tmp_path)
    assert "02.10.md" in result.deleted
    assert not (tmp_path / "laws" / result.slug / "sections" / "02.10.md").exists()
