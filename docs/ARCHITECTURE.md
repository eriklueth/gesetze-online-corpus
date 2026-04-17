# Architektur

Dieses Repo (`gesetze-online-corpus`) ist das **Tools-Repo**. Es enthält nur Code, Tests und CI. Es enthält keine Gesetzestexte.

Das zweite Repo ist **`gesetze-corpus-data`** (Sibling-Verzeichnis `../gesetze-corpus-data`). Es enthält ausschließlich die versionierten Gesetzestexte. Jeder Commit dort repräsentiert entweder einen initialen Snapshot oder ein Inkrafttretensereignis.

## Trennung der Verantwortlichkeiten

| Repo | Enthält | Commit-Semantik |
|---|---|---|
| `gesetze-online-corpus` (Tools) | Python-Paket, CLI, Parser, Renderer, Canonicalizer, Tests, CI-Workflows | Entwickler-Commits (Features, Fixes) |
| `gesetze-corpus-data` (Daten) | `laws/<BJNR>/…`, `events/<jahr>/…`, `sources/current/gii-index.json` | Bot-Commits, jeder Commit = Inkrafttretensereignis (oder Initial-Snapshot) |

## Quellen (Priorität)

1. **gesetze-im-internet.de (GII)** — konsolidierter amtlicher Volltext, XML über `gii-toc.xml` + `*/xml.zip`. Primärquelle für Textinhalte.
2. **recht.bund.de / NeuRIS** — offizielles Verkündungsereignis und ELI. Primärquelle für Events. Aktuell im Aufbau; Integration geplant, noch nicht implementiert.
3. **buzer.de** — ausschließlich als Metadatenquelle für Änderungshistorie (welches Datum, welche Paragraphen, welche BGBl-Fundstelle). Niemals als Textquelle. Keine öffentliche API; HTML-Parsing der stabilen URL-Muster (`/gesetz/<id>/l.htm`). Aktuell nicht implementiert.

Die Text-Wahrheit kommt **immer** aus GII / recht.bund.de. Buzer liefert nur Event-Metadaten. Synopsen werden nie gespiegelt.

## Phasen

### Phase A — Schema-Freeze (fertig)

`docs/SCHEMA.md` und `docs/CANONICAL.md` sind eingefroren. Änderungen daran erzeugen einen expliziten `chore(canonical): bump to vN`-Commit und einen Reformat-Lauf über den gesamten Bestand.

### Phase B — Current Snapshot (implementiert)

`python -m gesetze_corpus snapshot --limit N` oder ohne Limit:

1. `gii-toc.xml` laden, TOC-Slugs und ZIP-URLs bestimmen.
2. Pro Gesetz ZIP herunterladen, XML extrahieren, mit `xml.etree`/`lxml` kanonisieren (c14n2, UTF-8, LF).
3. Parsen in strukturierte Zwischenform (Stammgesetz-Meta, Gliederungsbäume, Paragraphen, Anlagen).
4. Rendern: eine Markdown-Datei pro `§`/`Artikel`/`Anlage`, plus `meta.json` und `toc.json` pro Gesetz.
5. Schreiben ins Daten-Repo unter `laws/<BJNR>/…`.
6. `sources/current/gii-index.json` mit Hash aller Quell-XMLs aktualisieren.

### Phase C — Live-Updates (Scaffold)

Tägliche GitHub-Action:

1. Snapshot laufen lassen (nur neue/geänderte Gesetze werden neu gerendert — erkannt über `sha256(source.xml)` in `sources/current/gii-index.json`).
2. Ein (zukünftiges) `detect-events` liest `recht.bund.de` / Buzer und gruppiert Änderungen nach `effective_date`.
3. Pro Event ein Commit ins Daten-Repo mit `GIT_AUTHOR_DATE = effective_date`.

In der aktuellen Implementierung ist (1) vorhanden, (2) und (3) sind als `events/`-Schema und Writer-Funktion vorbereitet, aber die Event-Quelle ist noch nicht angeschlossen. Bis dahin erzeugt der Tageslauf höchstens einen generischen `chore(sync): GII snapshot YYYY-MM-DD`-Commit.

### Phase D — Backfill 2006→heute (nicht implementiert)

Separates Projekt, braucht seriöse Roundtrip-Verifikation im CI. Wird in eigenem Branch `backfill-2006-to-now` aufgebaut und erst nach grünen Tests mit Main zusammengeführt.

## Daten-Repo-Layout

```
laws/
  BJNR001950896/                       # BGB, BJNR als stabile ID
    meta.json                          # jurabk, eli, title, ausfertigung_datum, source_urls, …
    toc.json                           # kanonische Reihenfolge + Breadcrumbs
    source.xml                         # kanonisiertes GII-XML (c14n2, NFC, LF)
    paragraphs/
      0001.md                          # § 1
      0014.md
      0014a.md
      art-0001.md                      # Artikel (bei Rechtsakten ohne §-Struktur)
    annexes/
      0001.md                          # Anlage 1

events/
  2026/
    2026-01-15-bgbl-2026-I-nr-3-0001.json

sources/
  current/
    gii-index.json                     # slug → { bjnr, title, sha256, zip_url, fetched_at }

README.md
SCHEMA.md                              # Kopie der Tools-Repo-Version, referenziert tooling-Version
LICENSE                                # CC0-1.0 für die amtliche Textbasis (§ 5 UrhG)
.gitattributes                         # * text eol=lf
.gitignore
```

## Invariante für das Daten-Repo

- **Keine Rebase-History-Änderungen** nach dem initialen Setup. Alle SHAs sind dauerhaft.
- **Keine Code-Commits**. Nur Daten.
- **Deterministische Ausgabe**: gleicher Input erzeugt byteidentischen Output (wird im CI getestet).
- **Jeder Commit** enthält entweder (a) den initialen Snapshot, (b) ein Inkrafttretensereignis mit Event-Datei, oder (c) einen markierten `chore(canonical)`-Lauf.

## Tools-Repo-Layout

```
gesetze_corpus/
  __init__.py
  __main__.py
  cli.py
  http.py
  fetch/          # GII TOC + ZIP-Downloads
  parse/          # XML → strukturierte Zwischenform
  canonical/      # Text- und XML-Canonicalization
  render/         # Markdown + meta.json + toc.json
  ingest/         # Orchestrator
  events/         # Event-Schema + Writer (Scaffold)
  util/           # Slugs, Pfade
docs/
tests/
  fixtures/
.github/workflows/
pyproject.toml
```
