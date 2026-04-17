#!/usr/bin/env python3
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

TOC_URL = "https://www.gesetze-im-internet.de/gii-toc.xml"
OUT_PATH = Path("index/toc.json")


def strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1]


def text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def element_to_dict(elem: ET.Element) -> dict:
    data = {f"@{strip_ns(k)}": v for k, v in elem.attrib.items()}
    text = text_or_none(elem.text)
    if text:
        data["#text"] = text
    for child in list(elem):
        key = strip_ns(child.tag)
        child_data = element_to_dict(child)
        if key in data:
            if not isinstance(data[key], list):
                data[key] = [data[key]]
            data[key].append(child_data)
        else:
            data[key] = child_data
    return data


def collect_laws(root: ET.Element) -> list[dict]:
    laws: list[dict] = []
    for elem in root.iter():
        payload = element_to_dict(elem)
        payload["_tag"] = strip_ns(elem.tag)
        flat_values = " ".join(str(v) for v in payload.values() if isinstance(v, str)).lower()
        attrs = {k: v for k, v in payload.items() if k.startswith("@") and isinstance(v, str)}
        if any(keyword in flat_values for keyword in ["xml", "html", "titel", "title", "jurabk"]) or attrs:
            laws.append(payload)
    return laws


def main() -> int:
    response = requests.get(TOC_URL, timeout=60, headers={"User-Agent": "gesetze-online-corpus/0.1"})
    response.raise_for_status()

    root = ET.fromstring(response.content)
    payload = {
        "source_url": TOC_URL,
        "count": 0,
        "items": collect_laws(root),
    }
    payload["count"] = len(payload["items"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(OUT_PATH)
    print(payload["count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
