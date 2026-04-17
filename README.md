# gesetze-online-corpus

Kontinuierlich aktualisierter, strukturierter Korpus deutscher Gesetze auf Basis amtlicher Quellen.

## Ziel
Dieses Repo ist die Source of Truth für den Gesetzeskorpus.

## Inhalte
- `raw/` amtliche Quelldaten
- `normalized/` strukturierte JSON-Dateien
- `markdown/` lesbare Markdown-Fassungen
- `chunks/` AI-Chunks pro Gesetz, Paragraph oder Absatz
- `index/` Indizes, Update-Logs und Mapping-Dateien
- `scripts/` Fetch-, Parse- und Export-Skripte
- `.github/workflows/` Update-Pipeline

## MVP Status
Aktuell ist das Repo als erstes echtes Ingest-Grundgerüst angelegt:
- RSS-Update-Check
- TOC-Fetch über `gii-toc.xml`
- Asset-Fetcher für XML oder HTML pro Gesetz
- XML-Normalisierung entlang der echten GII-`norm`/`metadaten`/`P`-Struktur
- Markdown-Export
- JSONL-Chunk-Export
- tägliche GitHub Action

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/fetch/rss_updates.py
python3 scripts/fetch/fetch_toc.py
python3 scripts/fetch/fetch_law_assets.py --limit 20
./scripts/run_pipeline.sh
```

## Wichtiger Hinweis
Die amtlichen XML-Strukturen sind nicht trivial. Der Parser ist jetzt deutlich näher an der echten GII-Struktur, inklusive `norm`, `metadaten`, `enbez`, `gliederungseinheit` und direkten `P`-Absätzen. Er ist aber noch nicht vollständig für Sonderfälle wie Anlagen, Tabellen, Satzebene und Fassungsvergleiche.

## Nächste Schritte
1. Feed-Einträge deterministisch auf Gesetzes-IDs mappen
2. Sonderfälle wie Anlagen, Tabellen und Revisionen sauber abbilden
3. Satzebene und Verweisgraph extrahieren
4. Rechtsstands-Versionierung einführen
5. Änderungsvergleiche ableiten
