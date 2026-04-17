#!/usr/bin/env python3
import json
from pathlib import Path
import xml.etree.ElementTree as ET

RAW_DIR = Path("raw")
NORMALIZED_DIR = Path("normalized")
INDEX_PATH = Path("index/laws.json")


def strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1]


def text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(part.strip() for part in node.itertext() if part.strip()).strip()


def normalize_xml(path: Path, law_id: str, meta: dict) -> dict:
    root = ET.fromstring(path.read_bytes())
    title = text(root.find('.//langue')) or text(root.find('.//titel')) or meta.get('title') or law_id
    paragraphs = []
    for elem in root.iter():
        tag = strip_ns(elem.tag).lower()
        if tag in {"par", "paragraph", "norm"}:
            number = elem.attrib.get("paragraf") or elem.attrib.get("gliederungseinheit") or text(elem.find('.//enbez')) or text(elem.find('.//bez'))
            heading = text(elem.find('.//titel')) or text(elem.find('.//heading'))
            body = text(elem)
            if body:
                paragraphs.append({
                    "type": "paragraph",
                    "number": number or str(len(paragraphs) + 1),
                    "heading": heading,
                    "content": [{"absatz": 1, "text": body}],
                })
    return {
        "law_id": law_id,
        "title": title,
        "source_url": meta.get("xml_url") or meta.get("html_url"),
        "sections": paragraphs[:500],
        "metadata": {"raw_meta": meta},
    }


def main() -> int:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for law_dir in sorted(RAW_DIR.iterdir() if RAW_DIR.exists() else []):
        if not law_dir.is_dir():
            continue
        meta_path = law_dir / 'meta.json'
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        law_id = meta['law_id']
        xml_path = law_dir / 'source.xml'
        if not xml_path.exists():
            continue
        try:
            payload = normalize_xml(xml_path, law_id, meta)
            out = NORMALIZED_DIR / f'{law_id}.json'
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            index.append({"law_id": law_id, "title": payload["title"], "source_url": payload.get("source_url")})
        except Exception as exc:
            (law_dir / 'normalize-error.json').write_text(json.dumps({"error": str(exc)}, indent=2))
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(INDEX_PATH)
    print(len(index))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
