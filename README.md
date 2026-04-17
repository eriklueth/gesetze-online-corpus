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
Aktuell ist das Repo als funktionierendes Grundgerüst angelegt:
- RSS-Update-Check als Startpunkt
- Platzhalter-Normalisierung
- Markdown-Export
- JSONL-Chunk-Export
- tägliche GitHub Action

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/fetch/rss_updates.py
./scripts/run_pipeline.sh
```

## Nächste Schritte
1. amtliche Quelldaten robust laden
2. Mapping von Feed-Einträgen auf Gesetzes-IDs aufbauen
3. echte Parserlogik für Hierarchie, Paragraphen und Absätze ergänzen
4. stabile kanonische IDs und Rechtsstands-Versionierung einführen
