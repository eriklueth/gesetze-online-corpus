#!/usr/bin/env python3
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

RAW_DIR = Path("raw")
NORMALIZED_DIR = Path("normalized")
INDEX_PATH = Path("index/laws.json")


def cleanup_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def xml_to_dict(element):
    if getattr(element, "string", None) and element.string == element.text:
        return cleanup_text(element.string)

    result = {}
    for child in getattr(element, "find_all", lambda *a, **k: [])(recursive=False):
        key = child.name
        value = xml_to_dict(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def extract_law_key(metadata: dict, fallback: str) -> str:
    for key in ["jurabk", "amtabk"]:
        value = metadata.get(key)
        if isinstance(value, list):
            value = value[0]
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def extract_norm_id(norm_meta: dict) -> str | None:
    enbez = norm_meta.get("enbez")
    if isinstance(enbez, list):
        enbez = enbez[0]
    if not isinstance(enbez, str) or not enbez.strip():
        return None

    gliederung = norm_meta.get("gliederungseinheit")
    if isinstance(gliederung, dict):
        prefix = gliederung.get("gliederungsbez")
        if isinstance(prefix, str) and prefix.strip():
            return f"{prefix.strip()} {enbez.strip()}"
    return enbez.strip()


def extract_title(norm, fallback: str = "") -> str:
    metadaten = norm.find("metadaten")
    if metadaten and metadaten.find("titel"):
        return cleanup_text(metadaten.find("titel").get_text(" ", strip=True))
    return fallback


def extract_paragraphs(norm) -> list[dict]:
    content = norm.find("textdaten")
    if not content:
        return []
    text = content.find("text")
    if not text:
        return []
    body = text.find("Content") or text.find("content") or text

    paragraphs = []
    current = None
    p_index = 0
    numbered_mode = False

    for p in body.find_all("P", recursive=False):
        for sup in p.find_all("SUP"):
            sup.decompose()

        value = cleanup_text(p.get_text(" ", strip=True))
        if not value:
            continue

        p_index += 1
        first_token = value.split()[0] if value.split() else ""
        match = re.match(r"^\(?(\d+[a-zA-Z]?)\)?", first_token)
        if match:
            paragraph_id = match.group(1)
            numbered_mode = True
            current = {"absatz": paragraph_id, "text": value}
            paragraphs.append(current)
            continue

        if numbered_mode and current is not None:
            current["text"] = cleanup_text(f"{current['text']} {value}")
            continue

        paragraph_id = str(p_index)
        current = {"absatz": paragraph_id, "text": value}
        paragraphs.append(current)

    return paragraphs


def normalize_xml(path: Path, meta: dict) -> dict:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "xml")
    metadaten_tag = soup.find("metadaten")
    metadaten = xml_to_dict(metadaten_tag) if metadaten_tag else {}

    title = ""
    if metadaten_tag and metadaten_tag.find("langue"):
        title = cleanup_text(metadaten_tag.find("langue").get_text(" ", strip=True))
    title = title or meta.get("title") or meta["law_id"]

    canonical_id = extract_law_key(metadaten, meta.get("xml_stem") or meta["law_id"])
    sections = []

    for norm in soup.find_all("norm"):
        norm_meta_tag = norm.find("metadaten")
        if not norm_meta_tag:
            continue
        norm_meta = xml_to_dict(norm_meta_tag)
        norm_id = extract_norm_id(norm_meta)
        if not norm_id or not re.match(r"^(§+|Art\.?|Artikel)\s*", norm_id):
            continue

        paragraphs = extract_paragraphs(norm)
        if not paragraphs:
            continue

        sections.append({
            "type": "norm",
            "number": norm_id,
            "heading": extract_title(norm),
            "content": paragraphs,
            "canonical_id": f"{canonical_id}:{norm_id}",
        })

    return {
        "law_id": meta["law_id"],
        "canonical_id": canonical_id,
        "title": title,
        "source_url": meta.get("zip_url"),
        "sections": sections,
        "metadata": {
            "jurabk": metadaten.get("jurabk"),
            "amtabk": metadaten.get("amtabk"),
            "ausfertigung_datum": metadaten.get("ausfertigung-datum"),
            "standangabe": metadaten.get("standangabe"),
            "raw_meta": meta,
        },
    }


def main() -> int:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    index = []

    for law_dir in sorted(RAW_DIR.iterdir() if RAW_DIR.exists() else []):
        if not law_dir.is_dir():
            continue
        meta_path = law_dir / "meta.json"
        xml_path = law_dir / "source.xml"
        if not meta_path.exists() or not xml_path.exists():
            continue

        meta = json.loads(meta_path.read_text())
        try:
            payload = normalize_xml(xml_path, meta)
            out = NORMALIZED_DIR / f"{meta['law_id']}.json"
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            index.append({
                "law_id": payload["law_id"],
                "canonical_id": payload["canonical_id"],
                "title": payload["title"],
                "source_url": payload["source_url"],
                "section_count": len(payload["sections"]),
            })
        except Exception as exc:
            (law_dir / "normalize-error.json").write_text(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))

    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(INDEX_PATH)
    print(len(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
