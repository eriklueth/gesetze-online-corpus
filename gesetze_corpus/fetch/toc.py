from __future__ import annotations

from dataclasses import dataclass

import requests
from lxml import etree

TOC_URL = "https://www.gesetze-im-internet.de/gii-toc.xml"


@dataclass
class TocEntry:
    title: str
    link: str
    slug: str


_STRIP_PREFIXES = (
    "https://www.gesetze-im-internet.de/",
    "http://www.gesetze-im-internet.de/",
)


def _slug_from_link(link: str) -> str:
    for p in _STRIP_PREFIXES:
        if link.startswith(p):
            link = link[len(p):]
            break
    if link.endswith("/xml.zip"):
        link = link[: -len("/xml.zip")]
    return link.strip("/")


def fetch_toc(session: requests.Session) -> list[TocEntry]:
    response = session.get(TOC_URL, timeout=(15, 120))
    response.raise_for_status()
    root = etree.fromstring(response.content)
    items: list[TocEntry] = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None:
            continue
        title = (title_el.text or "").strip()
        link = (link_el.text or "").strip()
        if not title or not link:
            continue
        slug = _slug_from_link(link)
        if not slug:
            continue
        # force HTTPS for downstream consistency
        if link.startswith("http://"):
            link = "https://" + link[len("http://"):]
        items.append(TocEntry(title=title, link=link, slug=slug))
    return items
