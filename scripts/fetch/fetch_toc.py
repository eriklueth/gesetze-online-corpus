#!/usr/bin/env python3
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

TOC_URL = "https://www.gesetze-im-internet.de/gii-toc.xml"
OUT_PATH = Path("index/toc.json")


def text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    value = elem.text.strip()
    return value or None


def main() -> int:
    response = requests.get(TOC_URL, timeout=60, headers={"User-Agent": "gesetze-online-corpus/0.1"})
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = []
    for item in root.findall(".//item"):
        title = text(item.find("title"))
        link = text(item.find("link"))
        description = text(item.find("description"))
        if not title or not link:
            continue
        slug = link.removeprefix("https://www.gesetze-im-internet.de/").removesuffix("/xml.zip").strip("/")
        items.append({
            "title": title,
            "link": link,
            "description": description,
            "slug": slug,
        })

    payload = {
        "source_url": TOC_URL,
        "count": len(items),
        "items": items,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(OUT_PATH)
    print(payload["count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
