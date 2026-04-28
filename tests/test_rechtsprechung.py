"""Tests for the Rechtsprechung pipeline (rii XML).

These run on synthetic XML fixtures so they stay hermetic; the live
portal applies GeoIP filters that make CI runs unreliable.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

pytest.importorskip("lxml")

from gesetze_corpus.fetchers.rechtsprechung.download import open_local
from gesetze_corpus.fetchers.rechtsprechung.parse import parse_decision_xml
from gesetze_corpus.fetchers.rechtsprechung.writer import (
    ecli_to_path,
    canonicalise_xml,
    write_decision,
)


SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<dokument>
  <ecli>ECLI:DE:BGH:2024:150124UIXZR123.23.0</ecli>
  <gericht>BGH</gericht>
  <entscheidungsdatum>2024-01-15</entscheidungsdatum>
  <aktenzeichen>IX ZR 123/23</aktenzeichen>
  <doktyp>Urteil</doktyp>
  <leitsatz>
    <p>Erster Leitsatz.</p>
    <p>Zweiter Leitsatz, mehrfach geschachtelt.</p>
  </leitsatz>
  <tenor>
    <p>Auf die Revision wird das Urteil aufgehoben.</p>
  </tenor>
  <gruende>
    <p>Erster Absatz der Gruende.</p>
    <p>Zweiter Absatz: Der Senat folgt seiner staendigen Rechtsprechung.</p>
  </gruende>
  <norm>BGB</norm>
  <norm>\u00a7 823 Abs. 1 BGB</norm>
  <norm>Art. 2 Abs. 1 GG</norm>
</dokument>
""".encode("utf-8")

OLDER_XML = """<?xml version="1.0" encoding="iso-8859-1"?>
<dokument>
  <gericht>BVerfG</gericht>
  <entscheidungsdatum>02.05.1995</entscheidungsdatum>
  <aktenzeichen>1 BvR 1/95</aktenzeichen>
  <doktyp>Beschluss</doktyp>
  <leitsatz>Der Schutz der Pressefreiheit erstreckt sich auch auf...</leitsatz>
  <tatbestand>Klaeger ist Verleger.</tatbestand>
  <entscheidungsgruende>Die Verfassungsbeschwerde ist begruendet.</entscheidungsgruende>
</dokument>
""".encode("iso-8859-1")


def test_parse_decision_extracts_metadata_and_blocks():
    doc = parse_decision_xml(SAMPLE_XML)
    assert doc.ecli == "ECLI:DE:BGH:2024:150124UIXZR123.23.0"
    assert doc.court == "BGH"
    assert doc.date == "2024-01-15"
    assert doc.case_no == "IX ZR 123/23"
    assert doc.decision_type == "Urteil"
    assert doc.leitsaetze == [
        "Erster Leitsatz.",
        "Zweiter Leitsatz, mehrfach geschachtelt.",
    ]
    assert doc.tenor[0].startswith("Auf die Revision")
    assert len(doc.gruende) == 2
    assert doc.normrefs == ["BGB", "\u00a7 823 Abs. 1 BGB", "Art. 2 Abs. 1 GG"]


def test_parse_decision_falls_back_to_split_blocks_for_older_xml():
    """Older BVerfG snapshots use <tatbestand>+<entscheidungsgruende>
    instead of a unified <gruende>; the parser must merge them."""
    doc = parse_decision_xml(OLDER_XML)
    assert doc.court == "BVerfG"
    assert doc.date == "1995-05-02"  # German -> ISO conversion
    assert doc.case_no == "1 BvR 1/95"
    assert any("Verleger" in p for p in doc.gruende)
    assert any("Verfassungsbeschwerde" in p for p in doc.gruende)
    # ECLI synthesised because the upstream omitted it.
    assert doc.ecli.startswith("ECLI:DE:BVERFG:1995:")


def test_ecli_to_path_handles_canonical_ecli():
    path = ecli_to_path("ECLI:DE:BGH:2024:150124UIXZR123.23.0")
    assert path == "decisions/DE/BGH/2024/150124UIXZR123.23.0"


def test_ecli_to_path_replaces_separators():
    """ECLIs with extra colon segments must collapse safely."""
    path = ecli_to_path("ECLI:DE:BVerfG:2020:rs.20200505.1bvr01010")
    assert path.startswith("decisions/DE/BVERFG/2020/")
    assert ":" not in path
    assert "/" not in path.split("decisions/")[1].split("/", 4)[-1]


def test_open_local_extracts_first_xml(tmp_path: Path):
    archive_path = tmp_path / "decision.zip"
    with ZipFile(archive_path, "w") as zf:
        zf.writestr("readme.txt", "ignore me")
        zf.writestr("payload.xml", SAMPLE_XML)
    archive = open_local(archive_path, ecli="ECLI:DE:BGH:2024:150124UIXZR123.23.0")
    assert archive.xml == SAMPLE_XML
    assert archive.xml_filename == "payload.xml"
    assert "readme.txt" in archive.extra_files


def test_write_decision_is_idempotent(tmp_path: Path):
    doc = parse_decision_xml(SAMPLE_XML)
    canonical = canonicalise_xml(SAMPLE_XML)

    first = write_decision(doc, canonical_xml=canonical, data_repo=tmp_path)
    assert first.written, "first write should produce files"
    target = tmp_path / first.relpath
    assert (target / "decision.md").exists()
    assert (target / "meta.json").exists()
    assert (target / "decision.xml").read_bytes() == canonical

    second = write_decision(doc, canonical_xml=canonical, data_repo=tmp_path)
    assert not second.written, f"second write touched {second.written}"
    assert sorted(second.unchanged) == ["decision.md", "decision.xml", "meta.json"]


def test_write_decision_meta_includes_normrefs_and_hash(tmp_path: Path):
    doc = parse_decision_xml(SAMPLE_XML)
    canonical = canonicalise_xml(SAMPLE_XML)
    result = write_decision(doc, canonical_xml=canonical, data_repo=tmp_path)
    meta_path = tmp_path / result.relpath / "meta.json"
    text = meta_path.read_text(encoding="utf-8")
    assert '"normrefs"' in text
    assert "\u00a7 823 Abs. 1 BGB" in text
    assert '"content_sha256"' in text
