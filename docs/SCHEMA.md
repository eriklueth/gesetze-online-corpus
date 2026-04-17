# Daten-Schema v1

Version: **v1** (eingefroren). Änderungen erzeugen `v2` + einen markierten Reformat-Commit im Daten-Repo.

## `laws/<BJNR>/meta.json`

```json
{
  "schema_version": "v1",
  "bjnr": "BJNR001950896",
  "jurabk": "BGB",
  "amtabk": "BGB",
  "title": "Bürgerliches Gesetzbuch",
  "gii_slug": "bgb",
  "eli": null,
  "ausfertigung_datum": "1896-08-18",
  "stand_datum": "2024-01-01",
  "standangabe": [
    { "typ": "Neuf", "kommentar": "Neugefasst durch Bek. v. 2.1.2002 I 42, 2909; 2003, 738" }
  ],
  "source_urls": {
    "gii_xml_zip": "https://www.gesetze-im-internet.de/bgb/xml.zip",
    "gii_html": "https://www.gesetze-im-internet.de/bgb/"
  },
  "source_hashes": {
    "source_xml_sha256": "…"
  },
  "ingested_at": "2026-04-17T15:00:00Z",
  "tooling_version": "gesetze-corpus-tools@0.1.0"
}
```

Regeln:

- `bjnr` ist die stabile ID, abgeleitet vom XML-Dateistamm im GII-ZIP.
- `eli` bleibt `null`, bis recht.bund.de angebunden ist.
- `stand_datum` ist das letzte dokumentierte `standangabe`-Datum; wenn keines ableitbar, `null`.
- `ingested_at` ist UTC, ISO-8601 mit `Z`.
- Keys sind alphabetisch sortiert beim Serialisieren (für Diff-Stabilität).

## `laws/<BJNR>/toc.json`

```json
{
  "schema_version": "v1",
  "bjnr": "BJNR001950896",
  "sections": [
    {
      "type": "paragraph",
      "number": "§ 1",
      "heading": "Beginn der Rechtsfähigkeit",
      "file": "paragraphs/0001.md",
      "breadcrumb": ["Buch 1", "Abschnitt 1", "Titel 1"]
    },
    {
      "type": "annex",
      "number": "Anlage 1",
      "heading": "Tabelle",
      "file": "annexes/0001.md",
      "breadcrumb": []
    }
  ]
}
```

Die Reihenfolge in `sections` ist die kanonische Reihenfolge aus dem GII-XML. Dateinamen haben nur sekundäre Sortierrelevanz — `toc.json` ist autoritativ.

## `laws/<BJNR>/paragraphs/<padded>.md`

```markdown
---
schema_version: v1
bjnr: BJNR001950896
jurabk: BGB
type: paragraph
number: "§ 14a"
heading: Begriffsbestimmung
breadcrumb:
  - Buch 1
  - Abschnitt 3
stand_datum: "2024-01-01"
source_xml: source.xml
---

# § 14a Begriffsbestimmung

(1) Erster Absatz.

(2) Zweiter Absatz.
```

Regeln:

- YAML-Frontmatter: Keys in fixer Reihenfolge (siehe Renderer).
- Nach Frontmatter: genau eine Leerzeile, dann `# <number> <heading>`, dann Leerzeile, dann Absätze.
- Absätze sind durch eine Leerzeile getrennt.
- Dateiendet mit genau einem `\n`.

## Dateinamens-Padding

| Typ | Quelle | Dateiname |
|---|---|---|
| Paragraph `§ 1` | `enbez = "§ 1"` | `paragraphs/0001.md` |
| Paragraph `§ 14a` | `enbez = "§ 14a"` | `paragraphs/0014a.md` |
| Artikel `Art 5` | `enbez = "Art 5"` oder `"Artikel 5"` | `paragraphs/art-0005.md` |
| Anlage `Anlage 1` | `enbez = "Anlage 1"` | `annexes/0001.md` |
| Anlage `Anlage` (ohne Nummer) | `enbez = "Anlage"` | `annexes/0000.md` |

Padding: 4 Stellen für die Basis-Nummer, Suffix (`a`, `b`, ...) wird direkt angehängt ohne Padding.

## `events/<jahr>/<event_id>.json`

```json
{
  "schema_version": "v1",
  "event_id": "2026-01-15-bgbl-2026-I-nr-3-0001",
  "effective_date": "2026-01-15",
  "promulgation_date": "2026-01-09",
  "bgbl_citation": "BGBl. 2026 I Nr. 3",
  "eli": null,
  "amending_act": {
    "title": "Gesetz zur …",
    "jurabk": null,
    "bjnr": null
  },
  "affected": [
    {
      "law_bjnr": "BJNR001950896",
      "law_jurabk": "BGB",
      "changes": [
        { "op": "modify", "path": "laws/BJNR001950896/paragraphs/0014.md", "type": "paragraph" }
      ]
    }
  ],
  "sources": [
    { "type": "official", "url": "https://www.recht.bund.de/…" }
  ],
  "verification": {
    "roundtrip_ok": true,
    "official_bytes_match": true
  },
  "tooling_version": "gesetze-corpus-tools@0.1.0",
  "ingested_at": "2026-04-17T02:15:00Z"
}
```

Ops: `add`, `modify`, `remove`, `rename`.

## `sources/current/gii-index.json`

```json
{
  "schema_version": "v1",
  "updated_at": "2026-04-17T15:00:00Z",
  "toc_source_url": "https://www.gesetze-im-internet.de/gii-toc.xml",
  "laws": {
    "bgb": {
      "bjnr": "BJNR001950896",
      "title": "Bürgerliches Gesetzbuch",
      "zip_url": "https://www.gesetze-im-internet.de/bgb/xml.zip",
      "source_xml_sha256": "…",
      "fetched_at": "2026-04-17T15:00:00Z"
    }
  }
}
```

Keys `laws` sind alphabetisch sortiert nach `gii_slug`.
