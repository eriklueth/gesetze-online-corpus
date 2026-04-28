# Knowledge-Graph (Phase 11)

## Warum ueberhaupt ein Graph?

Der Korpus ist **strukturell**, nicht nur textuell:

- Jeder Paragraph zitiert andere Paragraphen.
- Jede Entscheidung zitiert Normen *und* andere Entscheidungen.
- Definitionen leben in einem § und werden an anderer Stelle verwendet
  (`Verbraucher i.S.d. § 13 BGB`).
- Tatbestaende verweisen auf Rechtsfolgen
  (`Wer X tut, wird mit Y bestraft`).
- Normen ersetzen, ergaenzen oder schraenken andere Normen ein.

Embeddings sind exzellent darin, *aehnliche* Snippets zu finden, aber
sie verlieren genau diese typisierten Strukturkanten. Eine reine
Vektor-Suche kann nicht beantworten: "welche Entscheidungen wenden
§ 823 Abs. 1 BGB an, wenn der Beklagte ein Verbraucher ist?". Der
Graph kann das mit drei Hops:

```
question
  -> § 823 Abs. 1 BGB
       -[applies_to]-> Entscheidung X (BGH, 2021)
       -[cites]------> § 13 BGB (Verbraucher)
       -[defines]----> "Verbraucher"
```

GraphRAG-Forschung zeigt, dass die Kombination Vektor + Graph (HybridRAG)
fuer juristische Korpora deutlich praezisere Antworten liefert als
beide Verfahren einzeln. Die Plattform setzt das auf einer einzigen
Postgres-Instanz um, ohne zweite Datenbank-Stack.

## Speicherwahl: Postgres, nicht Neo4j

Optionen, die wir abgewogen haben:

1. **Neo4j** (dedizierter Graph-Store)
   - Pro: ergonomisches Cypher, sehr schnelle Pfad-Queries.
   - Contra: zweiter operativer Stack, Synchronisations-Overhead,
     Lizenz-Politik bei AuraDB. Wuerde unsere "alles in Supabase"-These
     brechen.
2. **AWS Neptune / Azure Cosmos DB Gremlin**
   - Pro: managed.
   - Contra: Vendor-Lock-In, Kosten, kein Self-Hosting fuer Devs.
3. **Postgres mit `LTREE` + `recursive CTE`**
   - Pro: bleibt im selben Stack, transaktional zusammen mit `events`,
     `citations`, `decisions`. Kein neuer Backup-Pfad. RLS funktioniert.
   - Contra: kein Cypher, manuelle Pfad-Funktionen.
4. **Apache AGE auf Postgres**
   - Pro: Cypher-Subset *direkt* auf der bestehenden DB. Drop-in
     fuer (3) wenn man Cypher will.
   - Contra: Extension-Verfuegbarkeit auf Supabase ist (Stand 2026)
     limitiert; aktuell selbst-betriebene Postgres-Instanzen.

**Entscheidung:** Wir starten mit (3) -- normales Postgres, getypte
Edge-Tabellen, recursive CTEs. Das deckt die ersten 18 Monate. Sobald
Supabase AGE freischaltet oder wir auf eigenes Postgres umsteigen,
liefert der gleiche Datenbestand sofort Cypher-Queries; (4) wird
additiv eingeschaltet, ohne Datenmigration.

## Schema

Migration `0011_knowledge_graph.sql` legt drei neue Tabellen an
*neben* dem bestehenden `citations`-Table. `citations` bleibt das
"Roh-Extract" (regex- oder LLM-Output, eine Zeile pro Erwaehnung);
der Graph ist die kuratierte, deduplizierte Sicht.

### `kg_nodes`

```sql
create type kg_node_kind as enum (
  'law',         -- gesamtes Gesetz (BJNR-Schluessel)
  'section',     -- Paragraph/Artikel/Anlage (law_chunks.id)
  'decision',    -- ECLI
  'concept',     -- abstrakter Begriff ("Verbraucher", "Vorsatz")
  'tatbestand',  -- Tatbestandsmerkmal ("Verschulden", "Kausalitaet")
  'consequence', -- Rechtsfolge ("Schadensersatz", "Strafe")
  'event'        -- Aenderungsereignis (events.id)
);

create table kg_nodes (
  id            text primary key,           -- stable, kind-prefixed
  kind          kg_node_kind not null,
  jurisdiction  jurisdiction_id null,
  label         text not null,              -- short, human-readable
  attributes    jsonb not null default '{}',
  embedding     vector(1536) null,          -- optional, see below
  valid_from    date null,
  valid_to      date null,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);
```

`id` ist explizit string, damit kanonische Schluessel direkt
durchgereicht werden koennen:

| kind        | id-Beispiel                                                   |
|-------------|---------------------------------------------------------------|
| `law`       | `bund:bgb`                                                    |
| `section`   | `bund:bgb:p:0823`                                             |
| `decision`  | `ecli:DE:BGH:2024:150124UIXZR123.23.0`                        |
| `concept`   | `concept:verbraucher`                                         |
| `tatbestand`| `tb:verschulden`                                              |
| `consequence`| `rf:schadensersatz`                                          |
| `event`     | `event:bund:bgb:2025-01-01:effective`                         |

`embedding` ist *optional* auf Knoten. Fuer `concept`-Knoten
(abstrakte Begriffe) bauen wir eine eigene Repraesentation ueber den
mittleren Embedding aller Sektionen, in denen der Begriff erwaehnt
wird. So kann der Agent ueber Knoten-Embeddings auch "konzeptuelle
Naehe" abfragen, nicht nur Text-Naehe.

### `kg_edges`

```sql
create type kg_edge_kind as enum (
  'cites',          -- explizite Quellenzitation
  'defines',        -- "X i.S.d. § Y"
  'applies_to',     -- Entscheidung wendet Norm an
  'replaces',       -- Norm A wird ab Datum durch B ersetzt
  'modifies',       -- Norm A wird durch B geaendert
  'derogates',      -- lex specialis
  'requires',       -- Tatbestand A setzt B voraus
  'consequence_of', -- B ist Rechtsfolge von A
  'contradicts',    -- explizit detektiert (Phase 6)
  'mentions'        -- schwaecher als 'cites'
);

create table kg_edges (
  id          bigserial primary key,
  src         text not null references kg_nodes(id) on delete cascade,
  dst         text not null references kg_nodes(id) on delete cascade,
  kind        kg_edge_kind not null,
  weight      real not null default 1.0,    -- 0.0..1.0
  source      text null,                    -- 'regex' | 'llm' | 'manual'
  evidence    jsonb null,                   -- {chunk_id, span, citation_text}
  valid_from  date null,
  valid_to    date null,
  confidence  numeric(3,2) not null default 1.0,
  created_at  timestamptz default now(),
  unique (src, dst, kind, valid_from)
);

create index on kg_edges (src, kind);
create index on kg_edges (dst, kind);
create index on kg_edges using gin (evidence);
```

### `kg_paths` (materialisierte Sicht, optional)

Fuer Hot-Paths (z.B. "alle Entscheidungen, die § 823 BGB anwenden")
materialisieren wir die top-3 Hop-Pfade pro Knoten:

```sql
create materialized view kg_top_paths as
  select src, dst, kind, count(*) over (partition by src, kind) as fanout
  from kg_edges
  where confidence >= 0.8
  with data;
```

Refresh wird durch den Graph-Worker getriggert (s.u.).

## Pflege-Pipeline

```
+----------------+        +----------------+        +-----------------+
| events ingest  | -----> | citations  raw | -----> | graph builder   |
| (webhooks)     |        | (regex / LLM)  |        | (kg_nodes/edges)|
+----------------+        +----------------+        +-----------------+
                                                              |
                                                              v
                                                    +-----------------+
                                                    | kg_top_paths MV |
                                                    +-----------------+
```

Worker (`workers/graph_build.mjs`):

1. Liest `citations` mit `kind in ('regex','llm')`.
2. Resolviert `from_id`/`to_id` gegen `laws`/`law_chunks`/`decisions`,
   stable-IDs werden zu `kg_nodes`.
3. Bei Bedarf legt es Concept- und Tatbestand-Knoten an
   (heuristisch: substantivierte Form, Whitelist + LLM-Validierung).
4. Schreibt Edges idempotent (`unique (src, dst, kind, valid_from)`).
5. Refresht `kg_top_paths`.

Der Worker laeuft in derselben GitHub-Actions-Schedule wie die
anderen (siehe `.github/workflows/workers.yml`).

## API

```
GET /api/v1/graph/neighbors?id=<node-id>&kind=cites&depth=1
GET /api/v1/graph/path?from=<id>&to=<id>&depth=3
GET /api/v1/graph/concept/<slug>     -- Knoten + alle Anwendungs-Pfade
```

Antworten enthalten Edges *mit Evidence* (chunk_id, span), damit
Antworten nachpruefbar bleiben. Kein blackbox.

## Agent-Integration (HybridRAG)

`workers/agents/query.ts` wird so erweitert:

```
1. embeddings = embed(question)
2. seeds      = vector_search(law_chunks, embeddings, k=12)
3. expanded   = graph_expand(seeds.id_set, depth=2,
                             edges in {cites, applies_to, defines})
4. context    = dedupe(seeds + expanded)
   ranked by  alpha * vec_score + beta * graph_score
5. prompt     = build(question, context_with_paths)
6. answer     = LLM(prompt)
```

`graph_score` ist der Eigenvektor-Zentralitaets-Score auf dem
Subgraphen (PageRank-light). Implementierung: `pgvector` fuer (2),
recursive CTE fuer (3), inline matmul fuer (4).

Wenn `OPENAI_API_KEY` nicht gesetzt ist, gibt der Pfad weiterhin den
strukturierten Kontext zurueck -- der Graph alleine ist auch ohne
LLM nuetzlich (Anwaelte koennen ihn explorativ durchklicken).

## Was wir NICHT tun

- **Kein Triple-Store**, weil unser Schema von vornherein typisiert
  ist und wir aequivalent in Postgres sind.
- **Keine Ontology-Riesen** (OWL, RDF/SPARQL). Wir sind pragmatisch:
  ein flaches Vokabular, mit Versionierung, das alle 6 Monate
  reviewed wird.
- **Keine Auto-Erweiterung des Vokabulars durch LLM ohne Review.**
  Neue `kg_node_kind` und `kg_edge_kind` Werte gehen durch eine
  Migration, also durch einen Pull Request.

## Akzeptanzkriterien fuer Phase 11

- [x] Migration `0011_knowledge_graph.sql` idempotent.
- [x] Worker `graph_build.mjs` baut Knoten + Kanten aus `citations`.
- [x] API-Endpoint `/api/v1/graph/neighbors`.
- [x] Vitest-Smoke-Test fuer Knoten-/Kanten-Schreiben.
- [x] HybridRAG-Pfad in `workers/agents/query.ts` aktiv: zwei-stufiges
      Retrieval (vector seed -> graph expand) mit `retrieval_strategy`
      im Response. Graceful degrade auf `hybrid` und
      `lexical-fallback` ist getestet.
- [x] Materialized View `kg_top_paths` (Migration `0012`) mit
      service-role-only `kg_top_paths_refresh()` und
      Refresh-Hook am Ende jedes `graph_build`-Laufs.
