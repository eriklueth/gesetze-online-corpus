#!/usr/bin/env python3
import json
from pathlib import Path


def main() -> int:
    sample = {
        "law_id": "example-law",
        "title": "Example Law",
        "source_url": "https://www.gesetze-im-internet.de/",
        "sections": [
            {
                "type": "paragraph",
                "number": "1",
                "heading": "Beispielnorm",
                "content": [
                    {
                        "absatz": 1,
                        "text": "Dies ist ein Platzhalter für die spätere Parserlogik."
                    }
                ]
            }
        ]
    }
    out = Path("normalized/example-law.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sample, ensure_ascii=False, indent=2))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
