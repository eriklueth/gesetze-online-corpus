#!/usr/bin/env python3
import argparse
import json
import zipfile
from io import BytesIO
from pathlib import Path

from fetch_http import build_session

TOC_PATH = Path("index/toc.json")
RAW_DIR = Path("raw")


def fetch_bytes(session, url: str) -> bytes:
    response = session.get(url, timeout=(15, 120))
    response.raise_for_status()
    return response.content


def extract_primary_xml(blob: bytes) -> tuple[str, bytes]:
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError("zip contains no xml file")
        xml_name = sorted(xml_names)[0]
        return xml_name, zf.read(xml_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    toc = json.loads(TOC_PATH.read_text())
    fetched = []
    session = build_session()

    for item in toc.get("items", [])[: args.limit]:
        law_id = item["slug"] or "unknown-law"
        law_dir = RAW_DIR / law_id
        law_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "law_id": law_id,
            "title": item["title"],
            "slug": item["slug"],
            "zip_url": item["link"],
            "description": item.get("description"),
        }

        try:
            zip_blob = fetch_bytes(session, item["link"])
            (law_dir / "source.zip").write_bytes(zip_blob)
            xml_name, xml_blob = extract_primary_xml(zip_blob)
            (law_dir / "source.xml").write_bytes(xml_blob)
            meta["xml_filename"] = xml_name
            meta["xml_stem"] = Path(xml_name).stem
            fetched.append({"law_id": law_id, "xml_filename": xml_name})
        except Exception as exc:
            meta["fetch_error"] = str(exc)
            (law_dir / "error.json").write_text(json.dumps({"error": str(exc), "item": item}, ensure_ascii=False, indent=2))

        (law_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    print(json.dumps(fetched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
