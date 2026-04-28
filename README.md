# gesetze-online-corpus

Pipeline, die aus dem amtlichen XML von [gesetze-im-internet.de](https://www.gesetze-im-internet.de) einen **versionierten Markdown-Korpus des Bundesrechts** baut. Ein Commit im Daten-Repo entspricht einem Inkrafttretensereignis, backdated auf das `stand_datum` — `git log -- laws/BJNR…/paragraphs/0007g.md` zeigt also die Fassungsgeschichte eines Paragraphen an.

Dieses Repo enthält **ausschließlich Code** (Ingest, Parser, Canonicalizer, Renderer, CLI). Die erzeugten Gesetzestexte liegen im Sibling-Repo [`gesetze-corpus-data`](https://github.com/eriklueth/gesetze-corpus-data).

> **Status**: Phase B + C v1 produktiv, 6876 Gesetze live. Tägliche Updates laufen lokal gegen die GII-Domain (Details unten).

## Datenfluss

```
gesetze-im-internet.de ──► fetch (gii-toc.xml + <slug>/xml.zip)
                              │
                              ▼
                          parse   (lxml, Stammgesetz → Gliederung → §/Art./Anlage)
                              │
                              ▼
                        canonical (c14n2 XML, NFC-Text, LF, stabile Keys)
                              │
                              ▼
                          render  (Markdown + meta.json + toc.json)
                              │
                              ▼
        gesetze-corpus-data/laws/<BJNR>/…   +   events/<jahr>/<event_id>.json
                              │
                              ▼
                 git commit (GIT_AUTHOR_DATE = stand_datum)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Schema: [`docs/SCHEMA.md`](docs/SCHEMA.md) · Canonicalization: [`docs/CANONICAL.md`](docs/CANONICAL.md)

## Quickstart

```bash
# 1. Dependencies
pip install -e ".[dev]"

# 2. Daten-Repo als Sibling initialisieren (../gesetze-corpus-data)
python -m gesetze_corpus init-data

# 3. Erstmal klein: 5 Gesetze snapshotten
python -m gesetze_corpus snapshot --limit 5

# 4. Vollständiger täglicher Durchlauf (Snapshot + Event-Commits)
python -m gesetze_corpus sync

# 5. Tests
pytest
```

Standardpfad zum Daten-Repo: `../gesetze-corpus-data`. Überschreibbar per `--data-repo <pfad>` oder `GESETZE_DATA_REPO=…`.

## CLI

Die produktiven Befehle leben unter dem `bund`-Subkommando (Scope-Klarheit ab dem Moment, in dem VwV / Rechtsprechung / Landesrecht / EU als weitere Quellen dazukommen):

| Befehl | Zweck |
|---|---|
| `gesetze-corpus bund init-data` | Daten-Repo scaffolden + `git init` |
| `gesetze-corpus bund snapshot` | gesamtes GII-TOC verarbeiten |
| `gesetze-corpus bund snapshot --limit N` | erste N Gesetze |
| `gesetze-corpus bund snapshot --slug bgb` | einzelnes Gesetz |
| `gesetze-corpus bund commit-events` | backdated Commits pro `stand_datum` |
| `gesetze-corpus bund sync` | `snapshot` + `commit-events` (Daily Driver) |
| `gesetze-corpus bund verify` | Idempotenz + Hashes prüfen |

Die alten flachen Befehle (`gesetze-corpus sync`, `snapshot`, `commit-events`, …) funktionieren weiter als Aliase auf `bund <...>` und bleiben kompatibel mit bestehenden Scheduled Tasks.

Weitere Quellen (alle Phase-Scaffolds, siehe [`docs/ROADMAP.md`](docs/ROADMAP.md)):

| Befehl | Status |
|---|---|
| `gesetze-corpus vwv status` · `list` · `sync` | Scaffold, Phase 1 |
| `gesetze-corpus rechtsprechung status` · `list` · `sync` | Scaffold, Phase 2 |
| `gesetze-corpus land list` · `land <iso> status` · `land <iso> sync` | Scaffold, Phase 8 |
| `gesetze-corpus eu status` · `probe <celex>` · `sync` | Scaffold, Phase 9 |

`python -m gesetze_corpus …` funktioniert identisch, falls das Console-Script nicht im `PATH` ist.

## Repo-Struktur

```
gesetze_corpus/
    cli.py             # Entry Point; dispatched zu <source> <subcommand>
    fetchers/          # Per-Source-Facade
        bund.py        # Produktiv: GII-Pipeline (delegiert an ingest/)
        vwv/           # Scaffold: verwaltungsvorschriften-im-internet.de
        rechtsprechung/ # Scaffold: Bundesgerichte (rechtsprechung-im-internet.de)
        eu/            # Scaffold: EUR-Lex (CELEX + ELI)
        land/          # Scaffold: 16 Bundeslaender (_template.py + per-ISO Adapter)
    sources/           # Zusatzquellen (NeuRIS-Client fuer ELI-Anreicherung)
    fetch/             # GII TOC + ZIP Downloads, HTTP mit Retry
    parse/             # XML → strukturierte Zwischenform
    canonical/         # Text- + XML-Canonicalization (c14n2, NFC, LF)
    render/            # Markdown + meta.json + toc.json
    ingest/            # Orchestrator pro Gesetz
    events/            # stand_datum-Gruppierung, Event-Writer
    util/              # Slugs, Pfade
docs/                  # Architektur, Schema, Canonicalization, Roadmap
scripts/sync-local.ps1 # Windows-Scheduled-Task Wrapper
tests/                 # Parser-, Canonicalizer-, Idempotenz-Tests
```

## Täglich laufen lassen

`gesetze-im-internet.de` ist per GeoIP auf deutsche IPs beschränkt — GitHub-hosted Runner erreichen die Domain **nicht**. Der tägliche Sync läuft deshalb lokal. Einmal als Windows-Scheduled-Task registrieren:

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\Projekte\gesetze-online-corpus\scripts\sync-local.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 04:17
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "gesetze-corpus-sync" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

Logs landen unter `logs/sync-*.log`. Unter Linux/macOS tut es ein äquivalenter Cron-Eintrag:

```cron
17 4 * * *  cd /pfad/zu/gesetze-online-corpus && python -m gesetze_corpus sync >> logs/sync-$(date +\%Y\%m\%d).log 2>&1
```

Die Action `.github/workflows/daily-snapshot.yml` bleibt vorbereitet. Sobald ein self-hosted Runner in DE verfügbar ist, genügt ein Switch von `runs-on: ubuntu-latest` auf `runs-on: [self-hosted, linux, de]`.

## Entwicklung

```bash
pip install -e ".[dev]"
ruff check .
pyright
pytest
```

Idempotenz ist Test-Invariante: zwei aufeinanderfolgende `snapshot`-Läufe ohne Upstream-Änderung müssen einen leeren `git status` im Daten-Repo liefern.

## Quellen (Priorität)

1. **gesetze-im-internet.de (GII)** — Primärtext, konsolidiertes XML.
2. **recht.bund.de / NeuRIS** — geplant: echte Verkündungsereignisse + ELI, löst die `stand_datum`-Approximation in Phase C v2 auf.
3. **buzer.de** — geplant: ausschließlich Änderungs-Metadaten, niemals als Textquelle.

## Roadmap

Kurzueberblick, Details in [`docs/ROADMAP.md`](docs/ROADMAP.md):

- [x] Bund produktiv (`gesetze-corpus bund sync`)
- [x] Phase 1a: VwV-Corpus (`gesetze-corpus vwv sync`)
- [ ] Phase 1b: recht.bund.de-Events + ELI (Scaffold; Endpunkte vor Aktivierung verifizieren)
- [x] Phase 2: Rechtsprechung (Bundesgerichte, `rechtsprechung-corpus-data`)
- [x] Phase 3–7: Produkt-MVP, Webhooks, Semantic Search, Widerspruchs-Detection, Billing — lebt im Schwesterrepo [`gesetze-online-app`](https://github.com/eriklueth/gesetze-online-app)
- [ ] Phase 8: Landesrecht (BY, NW, BW zuerst, dann Rest) — Scaffold
- [x] Phase 9: EU-Recht via EUR-Lex (`gesetze-corpus eu sync` + `eu backfill`)
- [x] Phase 10: Rechtsprechung zu Norm verlinken (`workers/decision_linker.mjs` im App-Repo)

Zielbild ("Deutsche-Recht-Plattform"): geteilte Pipeline + ~21 CC0-Daten-Repos + proprietaerer Next.js-Stack mit REST, MCP, Webhooks und agentischer Widerspruchs-Detection. Architektur-Skizze: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Lizenz

Code: MIT (siehe `pyproject.toml`). Der erzeugte Korpus im Daten-Repo steht unter CC0-1.0; der amtliche Gesetzestext selbst ist nach § 5 UrhG gemeinfrei.
