# Roadmap

Dieses Dokument spiegelt den aktuellen Stand der Plattform
(`gesetze-online-corpus` + diverse `*-corpus-data` + `gesetze-online-app`)
auf dem Weg zur Deutschen-Recht-Platform und ist die kanonische
Implementations-Plan-Datei. Die Architektur-Doppel-Doku liegt in
`docs/KNOWLEDGE_GRAPH.md` und in den `*-corpus-data` SCHEMA.md-Dateien.

## Sources (Pipeline)

| Source              | Phase | Status         | Daten-Repo                                          |
|---------------------|-------|----------------|-----------------------------------------------------|
| `bund`              | 0     | produktiv      | `gesetze-corpus-data`                               |
| `vwv`               | 1     | aktiviert      | `vwv-corpus-data`                                   |
| `recht.bund.de`     | 1     | geplant (Scaffold) | (anreichernd, kein eigenes Repo — schreibt nach `gesetze-corpus-data`) |
| `rechtsprechung`    | 2     | aktiviert      | `rechtsprechung-corpus-data`                        |
| `land <iso>` (x16)  | 8     | Scaffold       | `landesrecht-<iso>-corpus-data`                     |
| `eu`                | 9     | aktiviert      | `eu-recht-corpus-data`                              |

> **Hinweis zu `recht.bund.de` / NeuRIS.** Der Adapter
> ([gesetze_corpus/sources/neuris.py](../gesetze_corpus/sources/neuris.py))
> ist absichtlich Scaffold und liefert leere Event-Listen, solange
> `GESETZE_NEURIS_ENABLED` nicht gesetzt ist. Die Endpunkt-URLs sind
> Platzhalter und muessen vor Aktivierung gegen das Live-Portal
> verifiziert werden. Bis dahin laeuft `events/detect.py`
> ausschliesslich auf der `stand_datum`-Heuristik. Wer auf echte
> Verkuendungsereignisse + ELI angewiesen ist, betrachtet diese
> Phase als **noch nicht aktiviert**.

CLI-Konvention:

```
gesetze-corpus <source> <subcommand> [opts]
gesetze-corpus bund sync
gesetze-corpus rechtsprechung sync --limit 20 [--commit]
gesetze-corpus vwv sync --repo C:/Projekte/vwv-corpus-data [--commit]
gesetze-corpus eu  sync     --since 2024-01-01 --limit 50 --repo ... [--commit]
gesetze-corpus eu  backfill --from 2000-01-01 --window-days 30 \
                            --cursor C:/.../.cursors/eu-backfill --repo ...
gesetze-corpus land by status
```

Die alten flachen Kommandos (`snapshot`, `sync`, `commit-events`, ...)
funktionieren als Aliase der entsprechenden `bund <...>` Befehle und
bleiben dauerhaft erhalten.

## Produkt (App)

| Phase | Feature                                                     | Status     |
|-------|-------------------------------------------------------------|------------|
| 3     | REST v1 read-only, Auth, `api_keys`, Dashboard              | aktiviert  |
| 3     | Supabase-SSR-Auth (Magic-Link), Tenant-Bootstrap            | aktiviert  |
| 3     | MCP-Server (stdio + HTTP)                                   | aktiviert  |
| 4     | GitHub-Webhook-Ingest, Fanout-Worker, Deliveries            | aktiviert  |
| 5     | Embeddings, Hybrid-Search-RPC, Regex-Citation-Graph         | aktiviert  |
| 6     | Widerspruchs-Detection v1 (LLM-Klassifikator)               | aktiviert  |
| 7     | Stripe, Tier-Gates, Rate-Limits, Fix-Vorschlaege            | aktiviert  |
| 10    | Rechtsprechung <-> Norm-Verlinkung                          | aktiviert  |
| 11    | **Knowledge-Graph + GraphRAG**                              | aktiviert  |
| 12    | Observability (strukturierte Logs, Healthcheck, Metriken)   | aktiviert  |

## Aktivierungsreihenfolge

Die Reihenfolge ist so gewaehlt, dass jede Phase einen nutzbaren
Zustand hinterlaesst:

1. **Phase 1 (Completeness Bund)** — VwV-Corpus (aktiviert).
   recht.bund.de-Events fuer echtes Inkrafttretensdatum + ELI sind
   weiterhin **geplant**, der Adapter
   ([gesetze_corpus/sources/neuris.py](../gesetze_corpus/sources/neuris.py))
   bleibt bis zur Verifizierung der Upstream-Endpunkte ein Scaffold.
2. **Phase 2 (Rechtsprechung Bund)** — BVerfG, BGH, BFH, BAG, BSG,
   BVerwG. Metadaten + Volltexte, noch keine Norm-Verknuepfung.
3. **Phase 3 (Produkt-MVP)** — Auth, REST v1, MCP stdio, Dashboard.
4. **Phase 4 (Webhooks)** — GitHub-Ingest, signierte Deliveries,
   Dead-Letter.
5. **Phase 5 (Semantic)** — Embeddings, Hybrid-Search, Citations.
6. **Phase 6 (Widerspruchs-Detection)** — Kandidaten-Pipeline, LLM.
7. **Phase 7 (Billing)** — Stripe, Tiers, Rate-Limits.
8. **Phase 8 (Landesrecht)** — BY, NW, BW, dann Rest.
9. **Phase 9 (EU-Recht)** — EUR-Lex, Cross-Corpus-Check Bund-vs-EU.
10. **Phase 10 (Linkage)** — Rechtsprechung zu Normen verknuepfen.
11. **Phase 11 (Knowledge-Graph)** — Typisierter Property-Graph aus
    Citations + Definitionen + Tatbestaenden, getrennt vom plain
    `citations`-Table; HybridRAG-Pfad fuer Agenten (siehe
    `docs/KNOWLEDGE_GRAPH.md`).
12. **Phase 12 (Observability)** — strukturierte JSON-Logs,
    Healthcheck-Endpoint, Heartbeats pro Worker, Metriken-Export.

## Knowledge-Graph (Phase 11) auf einen Blick

Die Plattform betreibt einen typisierten Wissensgraphen *zusaetzlich*
zu den Embeddings, nicht als Ersatz. Knoten sind `law`, `section`,
`decision`, `concept`, `tatbestand`. Kanten sind getypt
(`cites`, `defines`, `replaces`, `applies_to`, `consequence_of`,
`contradicts`) mit `confidence`, `source`, `valid_from`, `valid_to`.

Speicher-Implementierung: **Postgres** mit `LTREE` und `recursive CTE`
fuer Pfad-Queries, plus optionalem `Apache AGE`-Layer fuer Cypher.
Pflege durch dedizierte Worker, identisch versioniert wie die uebrigen
Tabellen. Vollstaendige Begruendung & Schema in
[`docs/KNOWLEDGE_GRAPH.md`](KNOWLEDGE_GRAPH.md).

Im Agent-Pfad lauft die Retrieval-Pipeline:

```
seed = embedding-search(question, k=12)
  -> graph-expand(seed, depth=2, edge-types=[cites,defines,applies_to])
  -> rerank-by-graph-relevance(...)
  -> LLM-prompt(question, context+graph-paths)
```

So bekommt das Modell nicht nur "die 12 aehnlichsten Snippets",
sondern auch die *strukturellen* Beziehungen (Definition -> Anwendung
-> Rechtsprechung -> Widerspruch).

## Backfill-Strategie

Jede Pipeline hat zwei Modi:

- **Delta** (taeglich, scheduled): nur was sich seit dem letzten Lauf
  geaendert hat. Ein flacher Cursor in `worker_cursors` (oder
  `<repo>/.cursors/<source>` fuer File-System-Pipelines) macht den
  Lauf resumierbar.
- **Backfill** (selten, manuell): vollstaendiger Re-Scan vom
  Anfang. Idempotent dank Unique-Constraints / Content-Hashes; darf
  parallel zum Delta-Job laufen, wenn er einen separaten Cursor
  benutzt.

| Pipeline / Worker      | Delta                   | Backfill                                      |
|------------------------|-------------------------|-----------------------------------------------|
| `bund sync`            | events + commit-events  | `events backfill` (nutzt Source-XML-Hashes)   |
| `vwv sync`             | listing + writer        | wie delta + `--commit` fuer backdating        |
| `rechtsprechung sync`  | listing + writer        | wie delta + `--commit` fuer backdating        |
| `eu sync`              | SPARQL `since=...`      | `eu backfill --from --to --window-days`       |
| Worker `citations`     | `worker_cursors`-Cursor | `--backfill` ignoriert Cursor                 |
| Worker `graph_build`   | `worker_cursors`-Cursor | `--backfill` ignoriert Cursor                 |
| Worker `embeddings`    | `embedding IS NULL`     | `--backfill` mit `<target>-backfill`-Cursor   |

`commit_paths`/`commit_all` aus `gesetze_corpus.util.gitcommit`
backdaten `GIT_AUTHOR_DATE` + `GIT_COMMITTER_DATE` auf die jeweilige
Stand- oder Entscheidungsdatum, sodass `git log` einer Datei die
echte Norm-/Entscheidungs-Geschichte zeigt -- unabhaengig davon,
wann unser Sync gelaufen ist.

## Invarianten ueber alle Sources

- **1 Commit = 1 Inkrafttretens-/Verkuendungsereignis.** `git log` auf
  eine Paragraphen-/Entscheidungsdatei ist die Fassungsgeschichte.
- **Datenrepos sind CC0**, wo rechtlich moeglich. Amtliche Normtexte
  sind nach § 5 UrhG ohnehin gemeinfrei.
- **Stabile IDs** ueber Sync-Laeufe hinweg. BJNR fuer GII-Gesetze,
  ECLI fuer Entscheidungen, CELEX fuer EU-Recht.
- **Deterministische Ausgabe.** Zwei aufeinanderfolgende Syncs ohne
  Upstream-Aenderung duerfen im Data-Repo keinen `git status`-Diff
  erzeugen.
- **Graph + Embeddings sind redundant, nicht alternativ.** Beide
  werden persistiert, beide werden im Retrieval kombiniert. Faellt
  einer von beiden aus, degradiert die App graceful auf den anderen.
