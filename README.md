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

## Täglich laufen lassen

`gesetze-im-internet.de` GeoIP-filtert ausländische Cloud-Runner — GitHub-Actions erreicht die Domain nicht. Deshalb läuft der tägliche Sync **lokal** auf der eigenen Maschine. Einmal als Windows-Task registrieren:

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\Projekte\gesetze-online-corpus\scripts\sync-local.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 04:17
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "gesetze-corpus-sync" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

Der Task läuft täglich 04:17 und schreibt Logs nach `C:\Projekte\gesetze-online-corpus\logs\sync-*.log`.

Die GitHub-Action `.github/workflows/daily-snapshot.yml` bleibt vorbereitet. Sobald ein self-hosted Runner in Deutschland verfügbar ist, `runs-on: ubuntu-latest` auf `runs-on: [self-hosted, linux, de]` umstellen — der Rest funktioniert unverändert.

## Status

- Phase A — Schema-Freeze: **fertig**
- Phase B — Current Snapshot: **implementiert**, 6876 Gesetze live produziert
- Phase C v1 — Event-getriebene Updates per `stand_datum`: **implementiert**
- Phase C v2 — recht.bund.de für präzise Events: **nicht begonnen**
- Phase D — Backfill 2006→heute: **nicht begonnen**
