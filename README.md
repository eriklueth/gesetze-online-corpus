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

## Pipeline
1. RSS oder Änderungsfeed prüfen
2. betroffene Gesetze identifizieren
3. Rohdaten neu laden
4. strukturierte Daten und Markdown erzeugen
5. Chunks und Indizes aktualisieren
6. nur bei echten Änderungen committen

## Geplante Formate
- JSON pro Gesetz
- Markdown pro Gesetz
- JSONL für Retrieval und Embeddings

## Nächste Schritte
- Source-Mapping definieren
- Parser für amtliche Daten bauen
- GitHub Action für täglichen Sync anlegen
