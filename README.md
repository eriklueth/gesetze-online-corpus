# gesetze-online-corpus — Tools

Tooling für den versionierten Korpus deutscher Bundesgesetze. Dieses Repo enthält **nur Code**. Die tatsächlichen Gesetzestexte liegen im separaten Daten-Repo **`gesetze-corpus-data`**.

## Architektur

- Detaillierte Architektur: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Daten-Schema v1: [`docs/SCHEMA.md`](docs/SCHEMA.md)
- Canonicalization-Regeln v1: [`docs/CANONICAL.md`](docs/CANONICAL.md)

Kern-Idee: ein Commit im Daten-Repo == ein Inkrafttretensereignis. Das Tools-Repo baut aus dem amtlichen GII-XML die kanonisierte Snapshot-Struktur und (später) Event-getriebene Update-Commits im Daten-Repo.

## Quellen

1. **gesetze-im-internet.de** (GII) — Primärtext, XML.
2. **recht.bund.de / NeuRIS** — geplant, Events + ELI.
3. **buzer.de** — geplant, nur Änderungs-Metadaten, keine Textquelle.

## Quickstart

```powershell
# Dependencies
pip install -e ".[dev]"

# Daten-Repo initialisieren (Sibling-Ordner ../gesetze-corpus-data)
python -m gesetze_corpus init-data

# Snapshot laufen lassen (klein anfangen!)
python -m gesetze_corpus snapshot --limit 5

# Idempotenz- und Parser-Tests
pytest
```

## CLI

```
python -m gesetze_corpus init-data            # Daten-Repo scaffolden + git init
python -m gesetze_corpus snapshot             # Gesamtes GII-TOC verarbeiten
python -m gesetze_corpus snapshot --limit N   # nur erste N Gesetze
python -m gesetze_corpus snapshot --slug bgb  # nur ein Gesetz
python -m gesetze_corpus commit-events        # Backdated Commits pro stand_datum
python -m gesetze_corpus sync                 # snapshot + commit-events (Daily-Driver)
python -m gesetze_corpus verify               # Idempotenz + Hashes prüfen
```

Standardpfad zum Daten-Repo: `../gesetze-corpus-data` (Sibling des Tools-Repos). Überschreibbar per `--data-repo <pfad>` oder Umgebungsvariable `GESETZE_DATA_REPO`.

## Status

- Phase A — Schema-Freeze: **fertig**
- Phase B — Current Snapshot: **implementiert**, 6876 Gesetze live produziert
- Phase C v1 — Event-getriebene Updates per `stand_datum`: **implementiert**
- Phase C v2 — recht.bund.de für präzise Events: **nicht begonnen**
- Phase D — Backfill 2006→heute: **nicht begonnen**
