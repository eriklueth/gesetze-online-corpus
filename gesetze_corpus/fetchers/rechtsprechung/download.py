"""Download per-decision archives from rechtsprechung-im-internet.de.

The portal hands out decisions as ZIP archives that contain at least
one XML document (and optionally PDFs / images). Listing entries
return the ZIP URL via `DecisionEntry.zip_url`. This module wraps
both the network fetch and the local-file fallback (for tests +
offline development).

The downloader does not write to disk; it returns the canonicalised
XML bytes as the unit of work for the parser. The writer is
responsible for persisting the full archive next to the rendered
Markdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from ...http import get


@dataclass
class DecisionArchive:
    """The resolved archive of a single decision.

    `xml_filename` is the name we found inside the ZIP, useful for
    logging and round-tripping. `xml` is the raw bytes; the parser
    is responsible for any encoding handling (the upstream uses
    iso-8859-1 in older entries and utf-8 from ~2018 onward).
    """

    ecli: str
    xml_filename: str
    xml: bytes
    extra_files: dict[str, bytes]


def fetch_archive(zip_url: str, *, ecli: str = "") -> DecisionArchive:
    """Fetch a per-decision ZIP and return its contents."""
    response = get(zip_url)
    return _open_zip(response.content, ecli=ecli, source=zip_url)


def open_local(path: str | Path, *, ecli: str = "") -> DecisionArchive:
    """Open a local ZIP fixture. Used by tests and offline replay."""
    raw = Path(path).read_bytes()
    return _open_zip(raw, ecli=ecli, source=str(path))


def _open_zip(raw: bytes, *, ecli: str, source: str) -> DecisionArchive:
    with ZipFile(BytesIO(raw)) as zf:
        xml_name: str | None = None
        extra: dict[str, bytes] = {}
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith(".xml") and xml_name is None:
                xml_name = name
            else:
                extra[name] = zf.read(name)
        if xml_name is None:
            raise ValueError(f"no .xml entry in archive {source}")
        xml = zf.read(xml_name)
    return DecisionArchive(ecli=ecli, xml_filename=xml_name, xml=xml, extra_files=extra)
