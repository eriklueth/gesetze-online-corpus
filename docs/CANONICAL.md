# Canonicalization v1

Version **v1**, eingefroren. Änderungen erzeugen `v2` und einen markierten Reformat-Commit im Daten-Repo.

Ziel: identischer Eingabetext produziert byteidentischen Output. Ohne diese Garantie sind Diffs im Daten-Repo wertlos.

## Text-Canonicalization

Gilt für alle String-Felder in `meta.json`, `toc.json`, Event-JSONs und den Fließtext in Markdown.

1. Eingabe auf `str` dekodieren (UTF-8).
2. `unicodedata.normalize("NFC", s)`.
3. Unicode-Kontrollzeichen (Kategorie `Cc`) außer `\n` und `\t` entfernen.
4. Non-Breaking-Space (`\u00a0`) zu ASCII-Space.
5. Zero-Width-Zeichen (`\u200b`, `\u200c`, `\u200d`, `\ufeff`) entfernen.
6. Typografische Anführungszeichen belassen wie in der Quelle (`„`, `"`, `«`, `»`). Kein Mapping.
7. Whitespace-Runs (`\s+`) im Fließtext eines Absatzes zu einem einzelnen ASCII-Space zusammenziehen.
8. `strip()` am Absatz-Start und -Ende.

Linebreaks: intern immer `\n`. Bei der Ausgabe in Dateien wird `\n` geschrieben (UTF-8, keine BOM).

## JSON-Canonicalization

1. UTF-8, `ensure_ascii=False`.
2. Keys alphabetisch sortiert (`sort_keys=True`).
3. Indent = 2 Leerzeichen, `separators=(",", ": ")`.
4. Genau ein `\n` am Dateiende.

## XML-Canonicalization

Für `laws/<BJNR>/source.xml`:

1. Input parsen mit `lxml.etree.fromstring(bytes)`.
2. Ausgabe per `lxml.etree.tostring(root, method="c14n2", with_comments=False, strip_text=False)`.
3. Prepend `<?xml version="1.0" encoding="UTF-8"?>\n` (c14n2 liefert es nicht selbst).
4. Ein trailing `\n` am Dateiende.

`c14n2` garantiert:

- Konsistente Attribut-Reihenfolge (alphabetisch).
- Normalisierte Whitespace in Attribut-Werten.
- Eindeutige Namespace-Deklarationen.
- Keine Kommentare (`with_comments=False`).

Kommentare aus dem Original-GII-XML gehen verloren — gewollt, sie enthalten oft Timestamps, die Scheindiffs erzeugen würden.

## Markdown-Canonicalization

Eine Paragraph-Datei hat genau diese Struktur:

```
---
<frontmatter-yaml>
---
<leerzeile>
# <number> <heading>
<leerzeile>
<absatz-1>
<leerzeile>
<absatz-2>
<leerzeile>
...
```

- Frontmatter-Keys in fixer Reihenfolge: `schema_version`, `bjnr`, `jurabk`, `type`, `number`, `heading`, `breadcrumb`, `stand_datum`, `source_xml`.
- `breadcrumb` als YAML-Sequenz (`- item`-Style).
- String-Werte mit Doppelpunkt, Sonderzeichen oder führendem `§` werden gequotet.
- Keine trailing Whitespace pro Zeile.
- Datei endet mit genau einem `\n`.

## Idempotenz-Test

`tests/test_idempotency.py` verifiziert für jede gerenderte Markdown/JSON/XML-Datei:

```
render(parse(render(x))) == render(x)
```

Wenn dieser Test rot wird, ist ein Canonicalization-Bug eingezogen und der Bestand muss reformatiert werden.

## Scheindiff-Regressionen

Wenn ein Re-Snapshot die `source_xml_sha256`-Werte unverändert lässt, aber die gerenderten Markdowns sich ändern, ist eine Canonicalization-Regression passiert. Die CI prüft das.
