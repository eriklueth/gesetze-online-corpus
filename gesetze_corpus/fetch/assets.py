from __future__ import annotations

import zipfile
from dataclasses import dataclass
from io import BytesIO

import requests


@dataclass
class LawAsset:
    bjnr: str
    xml_filename: str
    xml_bytes: bytes
    zip_bytes: bytes


def fetch_law_xml(session: requests.Session, zip_url: str) -> LawAsset:
    response = session.get(zip_url, timeout=(15, 180))
    response.raise_for_status()
    zip_bytes = response.content
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        xml_names = sorted(n for n in zf.namelist() if n.lower().endswith(".xml"))
        if not xml_names:
            raise ValueError(f"zip {zip_url} contains no xml")
        xml_name = xml_names[0]
        xml_bytes = zf.read(xml_name)
    bjnr = xml_name.rsplit("/", 1)[-1]
    if bjnr.lower().endswith(".xml"):
        bjnr = bjnr[:-4]
    return LawAsset(
        bjnr=bjnr,
        xml_filename=xml_name,
        xml_bytes=xml_bytes,
        zip_bytes=zip_bytes,
    )
