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
- XML-Normalisierung als erste generische Parserstufe
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
Die amtlichen XML-Strukturen sind nicht trivial. Der aktuelle Parser ist bewusst robust und generisch, aber noch nicht juristisch perfekt. Als Nächstes sollte er auf die echten GII-Strukturen geschärft werden.

## Nächste Schritte
1. TOC-Struktur präzise auf stabile Felder mappen
2. Feed-Einträge deterministisch auf Gesetzes-IDs mappen
3. echte Parserlogik für Paragraphen, Absätze, Überschriften und Metadaten ergänzen
4. kanonische IDs und Rechtsstands-Versionierung einführen
5. Änderungsvergleiche und Verweisgraph ableiten
