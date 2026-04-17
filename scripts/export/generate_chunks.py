#!/usr/bin/env python3
import json
from pathlib import Path

NORMALIZED_DIR = Path("normalized")
CHUNKS_DIR = Path("chunks")


def main() -> int:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(NORMALIZED_DIR.glob("*.json")):
        data = json.loads(src.read_text())
        out = CHUNKS_DIR / f"{data['law_id']}.jsonl"

        records = []
        for section in data.get("sections", []):
            for item in section.get("content", []):
                records.append({
                    "chunk_id": f"{data['law_id']}:p{section.get('number', 'x')}:a{item['absatz']}",
                    "law_id": data["law_id"],
                    "law_title": data["title"],
                    "paragraph_number": section.get("number"),
                    "absatz": item["absatz"],
                    "text": item["text"],
                    "source_url": data.get("source_url"),
                })

        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
        print(out)
        count += 1
    if count == 0:
        raise SystemExit("no normalized files found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
