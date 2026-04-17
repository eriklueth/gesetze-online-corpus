#!/usr/bin/env python3
import json
from pathlib import Path


def main() -> int:
    src = Path("normalized/example-law.json")
    if not src.exists():
        raise SystemExit("normalized/example-law.json not found")

    data = json.loads(src.read_text())
    lines = [f"# {data['title']}", ""]
    for section in data.get("sections", []):
        lines.append(f"## § {section['number']} {section.get('heading', '')}".strip())
        lines.append("")
        for item in section.get("content", []):
            lines.append(f"({item['absatz']}) {item['text']}")
            lines.append("")

    out = Path("markdown/example-law.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).strip() + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
