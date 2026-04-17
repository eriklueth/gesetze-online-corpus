#!/usr/bin/env python3
import json
from pathlib import Path


def main() -> int:
    src = Path("normalized/example-law.json")
    if not src.exists():
        raise SystemExit("normalized/example-law.json not found")

    data = json.loads(src.read_text())
    out = Path("chunks/example-law.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for section in data.get("sections", []):
        for item in section.get("content", []):
            records.append({
                "chunk_id": f"{data['law_id']}:p{section['number']}:a{item['absatz']}",
                "law_id": data["law_id"],
                "law_title": data["title"],
                "paragraph_number": section["number"],
                "absatz": item["absatz"],
                "text": item["text"],
                "source_url": data["source_url"],
            })

    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
