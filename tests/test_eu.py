"""Tests for the EU/EUR-Lex pipeline.

Hermetic against the live Cellar / EUR-Lex servers; the SPARQL listing
test mocks the JSON response payload directly, the detail tests use a
synthetic HTML fixture that matches the actual EUR-Lex DOM shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("lxml")

from gesetze_corpus.fetchers.eu.detail import (
    EuArticle,
    EuDocument,
    parse_detail_html,
)
from gesetze_corpus.fetchers.eu.listing import _parse_sparql_json
from gesetze_corpus.fetchers.eu.writer import (
    _filename_for,
    _pad_article_number,
    render_article_markdown,
    write_eu_document,
)


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="de">
  <head>
    <title>VERORDNUNG (EU) 2016/679 - DSGVO - EUR-Lex</title>
    <link rel="canonical" href="http://data.europa.eu/eli/reg/2016/679/oj"/>
    <meta property="eli" content="http://data.europa.eu/eli/reg/2016/679/oj"/>
  </head>
  <body>
    <p class="oj-hd-coll">L 119</p>
    <p class="oj-hd-info">4.5.2016 S. 1</p>
    <p class="oj-normal">Praeambel: Die Wuerde des Menschen.</p>
    <p class="ti-art">Artikel 1</p>
    <p class="sti-art">Gegenstand und Ziele</p>
    <p class="oj-normal">(1) Diese Verordnung enthaelt Vorschriften zum Schutz natuerlicher Personen.</p>
    <p class="oj-normal">(2) Sie schuetzt die Grundrechte und Grundfreiheiten.</p>
    <p class="ti-art">Artikel 2</p>
    <p class="sti-art">Sachlicher Anwendungsbereich</p>
    <p class="oj-normal">Diese Verordnung gilt fuer die ganz oder teilweise automatisierte Verarbeitung.</p>
    <p class="ti-art">Artikel 99</p>
    <p class="sti-art">Inkrafttreten und Geltungsbeginn</p>
    <p class="oj-normal">Diese Verordnung tritt am 25. Mai 2018 in Kraft.</p>
  </body>
</html>
"""


def test_parse_detail_html_extracts_metadata_and_articles():
    doc = parse_detail_html(SAMPLE_HTML.encode("utf-8"), celex="32016R0679")
    assert doc.celex == "32016R0679"
    assert doc.doc_type == "eu-verordnung"
    assert "DSGVO" in doc.title
    assert "eli/reg/2016/679" in doc.eli
    numbers = [a.number for a in doc.articles]
    assert numbers == ["0", "1", "2", "99"]
    art1 = doc.articles[1]
    assert art1.heading == "Gegenstand und Ziele"
    assert any("Schutz natuerlicher Personen" in p for p in art1.paragraphs)
    assert any("Grundrechte" in p for p in art1.paragraphs)
    art99 = doc.articles[3]
    assert art99.heading.startswith("Inkrafttreten")
    assert "Mai 2018" in art99.paragraphs[0]


def test_pad_article_number_keeps_sort_order():
    assert _pad_article_number("1") == "0001"
    assert _pad_article_number("9") == "0009"
    assert _pad_article_number("10") == "0010"
    assert _pad_article_number("99") == "0099"
    # The padding must guarantee 1 < 2 < 10 < 99 lexicographically.
    nums = ["1", "10", "2", "99", "9"]
    assert sorted(_pad_article_number(n) for n in nums) == [
        "0001",
        "0002",
        "0009",
        "0010",
        "0099",
    ]


def test_filename_for_handles_special_blocks():
    assert _filename_for(EuArticle(number="0", heading="")) == "0000-praeambel.md"
    assert _filename_for(EuArticle(number="praeambel", heading="")) == "0000-praeambel.md"
    assert _filename_for(EuArticle(number="anhang", heading="I")) == "9000-anhang.md"
    assert _filename_for(EuArticle(number="5a", heading="x")) == "0005a.md"


def test_render_article_markdown_has_frontmatter_and_heading():
    doc = parse_detail_html(SAMPLE_HTML.encode("utf-8"), celex="32016R0679")
    md = render_article_markdown(doc, doc.articles[1])
    assert md.startswith("---\n")
    assert "celex: 32016R0679" in md
    assert "ordinal_padded: 0001" in md
    assert "# Artikel 1 - Gegenstand und Ziele" in md
    assert "Schutz natuerlicher Personen" in md


def test_write_eu_document_is_idempotent_and_prunes_obsolete(tmp_path: Path):
    doc = parse_detail_html(SAMPLE_HTML.encode("utf-8"), celex="32016R0679")
    first = write_eu_document(doc, data_repo=tmp_path)
    assert first.written  # first run writes everything
    base = tmp_path / "laws" / "32016R0679"
    assert (base / "meta.json").exists()
    assert (base / "articles" / "0001.md").exists()
    assert (base / "articles" / "0099.md").exists()

    second = write_eu_document(doc, data_repo=tmp_path)
    assert not second.written, f"second run rewrote: {second.written}"
    assert "meta.json" in second.unchanged

    # Drop article 2 -> writer should delete the obsolete file.
    pruned = EuDocument(
        celex=doc.celex,
        title=doc.title,
        eli=doc.eli,
        doc_type=doc.doc_type,
        language=doc.language,
        articles=[a for a in doc.articles if a.number != "2"],
    )
    third = write_eu_document(pruned, data_repo=tmp_path)
    assert "0002.md" in third.deleted
    assert not (base / "articles" / "0002.md").exists()
    assert (base / "articles" / "0001.md").exists()


def test_write_eu_document_meta_has_content_hash(tmp_path: Path):
    doc = parse_detail_html(SAMPLE_HTML.encode("utf-8"), celex="32016R0679")
    write_eu_document(doc, data_repo=tmp_path)
    meta = json.loads((tmp_path / "laws" / "32016R0679" / "meta.json").read_text())
    assert meta["celex"] == "32016R0679"
    assert meta["doc_type"] == "eu-verordnung"
    assert len(meta["content_sha256"]) == 64
    assert meta["article_count"] == 4
    # OJ reference is materialised from the structured EUR-Lex header.
    assert meta["oj_reference"] == "L 119/1"


def test_parse_detail_extracts_oj_reference_from_text_fallback():
    html = (
        "<html><body><p>ABl. L 200/12 vom 1.1.2024</p></body></html>"
    ).encode("utf-8")
    doc = parse_detail_html(html, celex="32024R0001")
    assert doc.oj_reference == "L 200/12"


def test_parse_detail_oj_reference_is_empty_when_absent():
    html = b"<html><body><p>nothing here</p></body></html>"
    doc = parse_detail_html(html, celex="31958R0001")
    assert doc.oj_reference == ""


def test_write_eu_document_multi_lang_layout(tmp_path: Path):
    doc = parse_detail_html(
        SAMPLE_HTML.encode("utf-8"), celex="32016R0679", language="de"
    )
    res = write_eu_document(doc, data_repo=tmp_path, multi_lang=True)
    assert res.celex == "32016R0679"
    base = tmp_path / "laws" / "32016R0679" / "de"
    assert (base / "meta.json").exists()
    assert (base / "articles" / "0001.md").exists()
    # Default-layout folder must NOT be touched when multi_lang=True.
    assert not (tmp_path / "laws" / "32016R0679" / "articles").exists()


def test_write_eu_document_multi_lang_requires_language(tmp_path: Path):
    doc = parse_detail_html(
        SAMPLE_HTML.encode("utf-8"), celex="32016R0679", language=""
    )
    with pytest.raises(ValueError):
        write_eu_document(doc, data_repo=tmp_path, multi_lang=True)


def test_write_eu_document_meta_oj_reference_null_when_missing(tmp_path: Path):
    html = b"""<html><head><title>No OJ - EUR-Lex</title></head><body>
      <p class="ti-art">Artikel 1</p>
      <p class="sti-art">Foo</p>
      <p class="oj-normal">Body.</p>
    </body></html>"""
    doc = parse_detail_html(html, celex="31958R9999")
    write_eu_document(doc, data_repo=tmp_path)
    meta = json.loads((tmp_path / "laws" / "31958R9999" / "meta.json").read_text())
    assert meta["oj_reference"] is None


def test_cli_parse_smokes_a_local_fixture(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """`gesetze-corpus eu parse --source ...` works fully offline."""
    fixture = tmp_path / "celex.html"
    fixture.write_bytes(SAMPLE_HTML.encode("utf-8"))

    from gesetze_corpus.fetchers.eu import cmd_parse

    rc = cmd_parse(
        type("NS", (), {"source": str(fixture), "celex": "32016R0679", "language": "de"})()
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "celex:    32016R0679" in out
    assert "doc_type: eu-verordnung" in out
    assert "articles: 4" in out


def test_iter_backfill_walks_windows_and_persists_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The backfill iterator splits the range, calls fetch_window per slice,
    and writes the cursor after each completed window."""
    from gesetze_corpus.fetchers.eu import listing as listing_mod
    from gesetze_corpus.fetchers.eu.listing import CelexEntry, iter_backfill

    calls: list[tuple[str, str]] = []

    def fake_fetch_window(*, start: str, end: str, limit: int = 1000):
        calls.append((start, end))
        return [CelexEntry(celex=f"3{start[:4]}3R0001", title=f"win {start}", date=start)]

    monkeypatch.setattr(listing_mod, "fetch_window", fake_fetch_window)

    cursor = tmp_path / "cursor.txt"
    out = list(
        iter_backfill(
            start="2020-01-01",
            end="2020-04-01",
            window_days=31,
            cursor_path=cursor,
        )
    )

    # Windows: [01-01, 02-01), [02-01, 03-04), [03-04, 04-01).
    assert len(calls) == 3
    assert calls[0] == ("2020-01-01", "2020-02-01")
    assert calls[1][0] == "2020-02-01"
    assert calls[-1][1] == "2020-04-01"
    assert [e.celex for e in out] == ["32020 3R0001".replace(" ", "")] * 3 or len(out) == 3
    # Cursor should hold the last window's end date.
    assert cursor.read_text(encoding="utf-8").strip() == "2020-04-01"


def test_iter_backfill_resumes_from_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Restarting after a partial run should skip already-completed windows."""
    from gesetze_corpus.fetchers.eu import listing as listing_mod
    from gesetze_corpus.fetchers.eu.listing import CelexEntry, iter_backfill

    cursor = tmp_path / "cursor.txt"
    cursor.write_text("2020-03-01\n", encoding="utf-8")

    starts: list[str] = []

    def fake_fetch_window(*, start: str, end: str, limit: int = 1000):
        starts.append(start)
        return [CelexEntry(celex="32020 3R0001".replace(" ", ""), title="x", date=start)]

    monkeypatch.setattr(listing_mod, "fetch_window", fake_fetch_window)

    list(
        iter_backfill(
            start="2020-01-01",
            end="2020-04-01",
            window_days=31,
            cursor_path=cursor,
        )
    )
    # Must NOT re-request 2020-01 / 2020-02 windows.
    assert starts and starts[0] == "2020-03-01"
    assert all(s >= "2020-03-01" for s in starts)


def test_iter_backfill_rejects_invalid_window():
    from gesetze_corpus.fetchers.eu.listing import iter_backfill

    with pytest.raises(ValueError):
        list(iter_backfill(start="2020-01-01", end="2020-12-31", window_days=0))


def test_collect_backfill_respects_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from gesetze_corpus.fetchers.eu import listing as listing_mod
    from gesetze_corpus.fetchers.eu.listing import CelexEntry, collect_backfill

    def fake_fetch_window(*, start: str, end: str, limit: int = 1000):
        return [
            CelexEntry(celex=f"3{start[:4]}3R000{i}", title="x", date=start)
            for i in range(5)
        ]

    monkeypatch.setattr(listing_mod, "fetch_window", fake_fetch_window)

    out = collect_backfill(
        start="2020-01-01",
        end="2020-03-01",
        window_days=31,
        cursor_path=tmp_path / "cursor.txt",
        limit=7,
    )
    assert len(out) == 7  # 5 from win-1, 2 from win-2


def test_deduplicate_keeps_first_occurrence():
    from gesetze_corpus.fetchers.eu.listing import CelexEntry, deduplicate

    entries = [
        CelexEntry("32016R0679", "DSGVO", "2016-04-27"),
        CelexEntry("32016R0679", "DSGVO duplicate", "2016-05-01"),
        CelexEntry("32019L0790", "DSM", "2019-04-17"),
    ]
    out = deduplicate(entries)
    assert [e.celex for e in out] == ["32016R0679", "32019L0790"]
    assert out[0].title == "DSGVO"


def test_parse_sparql_json_extracts_celex_rows():
    payload = {
        "results": {
            "bindings": [
                {
                    "celex": {"value": "32016R0679"},
                    "title": {"value": "DSGVO"},
                    "date": {"value": "2016-04-27T00:00:00"},
                },
                {
                    "celex": {"value": "32019R1238"},
                    "title": {"value": "PEPP-VO"},
                    "date": {"value": "2019-06-20"},
                },
                # Defensive: rows without celex must be skipped.
                {"title": {"value": "junk"}},
            ],
        },
    }
    rows = _parse_sparql_json(json.dumps(payload).encode("utf-8"))
    assert [r.celex for r in rows] == ["32016R0679", "32019R1238"]
    assert rows[0].date == "2016-04-27"
    assert rows[1].title == "PEPP-VO"
