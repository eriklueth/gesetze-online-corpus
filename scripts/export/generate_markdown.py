#!/usr/bin/env python3
import json
from pathlib import Path

NORMALIZED_DIR = Path("normalized")
MARKDOWN_DIR = Path("markdown")


def render(data: dict) -> str:
    lines = [f"# {data['title']}", ""]
    for section in data.get("sections", []):
        label = section.get('number', '')
        heading = section.get('heading', '') or ''
        lines.append(f"## § {label} {heading}".strip())
        lines.append("")
        for item in section.get("content", []):
            lines.append(f"({item['absatz']}) {item['text']}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(NORMALIZED_DIR.glob("*.json")):
        data = json.loads(src.read_text())
        out = MARKDOWN_DIR / f"{data['law_id']}.md"
        out.write_text(render(data))
        print(out)
        count += 1
    if count == 0:
        raise SystemExit("no normalized files found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
