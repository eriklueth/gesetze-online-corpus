#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

TOC_PATH = Path("index/toc.json")
RAW_DIR = Path("raw")
BASE_URL = "https://www.gesetze-im-internet.de/"


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown-law"


def flatten_strings(node, acc: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "_tag":
                continue
            flatten_strings(value, acc)
    elif isinstance(node, list):
        for item in node:
            flatten_strings(item, acc)
    elif isinstance(node, str):
        acc.append(node)


def guess_metadata(item: dict) -> dict:
    strings: list[str] = []
    flatten_strings(item, strings)

    url_candidates = [s for s in strings if s.startswith("http") or s.startswith("/")]
    xml_candidates = [u for u in url_candidates if "xml" in u.lower()]
    html_candidates = [u for u in url_candidates if u.lower().endswith(".html") or u.startswith("/")]
    title = next((s for s in strings if len(s) > 6 and not s.startswith("http")), None)
    law_id = slugify(next((s for s in strings if re.fullmatch(r"[a-zA-Z0-9_\-]+", s) and len(s) < 40), title or "law"))

    return {
        "law_id": law_id,
        "title": title or law_id,
        "xml_url": urljoin(BASE_URL, xml_candidates[0]) if xml_candidates else None,
        "html_url": urljoin(BASE_URL, html_candidates[0]) if html_candidates else None,
        "raw_item": item,
    }


def fetch(url: str, target: Path) -> None:
    response = requests.get(url, timeout=60, headers={"User-Agent": "gesetze-online-corpus/0.1"})
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    toc = json.loads(TOC_PATH.read_text())
    fetched = []

    for item in toc.get("items", [])[: args.limit]:
        meta = guess_metadata(item)
        law_dir = RAW_DIR / meta["law_id"]
        law_dir.mkdir(parents=True, exist_ok=True)
        (law_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        try:
            if meta["xml_url"]:
                fetch(meta["xml_url"], law_dir / "source.xml")
                fetched.append({"law_id": meta["law_id"], "asset": "xml", "url": meta["xml_url"]})
            elif meta["html_url"]:
                fetch(meta["html_url"], law_dir / "source.html")
                fetched.append({"law_id": meta["law_id"], "asset": "html", "url": meta["html_url"]})
        except Exception as exc:
            (law_dir / "error.json").write_text(json.dumps({"error": str(exc), "meta": meta}, ensure_ascii=False, indent=2))

    print(json.dumps(fetched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
