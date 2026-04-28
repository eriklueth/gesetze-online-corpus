"""Landesrecht fetcher template.

Each Bundesland is an instance of this template. The required
contract is thin:

- `LandAdapter.fetch_toc() -> Iterable[LandLawMeta]`: list of laws on
  the upstream portal with stable IDs and titles.
- `LandAdapter.fetch_law(id) -> LandLawDocument`: the full document
  (source markup + parsed sections).
- `LandAdapter.render(doc) -> LandRenderedLaw`: markdown per section
  plus `meta.json` shape.

The rest (canonicalization, hash-stable writes into the data repo,
commit scheduling) is shared across Laender — this is the point of
the template.

Activation checklist for a new Land:

1. Implement `LandAdapter` in `gesetze_corpus/fetchers/land/<iso>.py`.
2. Register it in `REGISTRY` in `gesetze_corpus/fetchers/land/__init__.py`
   (already has upstream URLs, just flip `activated=True`).
3. Run `gesetze-corpus --data-repo ../landesrecht-<iso>-corpus-data land <iso> init-data`
   (not yet implemented — will reuse `bund.cmd_init_data` with different
   defaults at activation time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


@dataclass(frozen=True)
class LandLawMeta:
    id: str                       # upstream stable id
    title: str
    url: str
    stand_datum: str | None = None
    doc_type: str = "landesrecht"


@dataclass(frozen=True)
class LandLawSection:
    path: str                     # repo-relative path (e.g. "paragraphs/0007.md")
    number: str                   # "§ 7" | "Art 5" | "Anlage 1"
    heading: str | None
    markdown: str


@dataclass(frozen=True)
class LandLawDocument:
    meta: LandLawMeta
    source_bytes: bytes
    sections: list[LandLawSection] = field(default_factory=list)


@dataclass(frozen=True)
class LandRenderedLaw:
    meta_json: dict
    files: dict[str, str]          # rel_path -> markdown content


class LandAdapter(Protocol):
    """Per-Land implementation contract."""

    iso: str

    def fetch_toc(self) -> Iterable[LandLawMeta]: ...

    def fetch_law(self, meta: LandLawMeta) -> LandLawDocument: ...

    def render(self, doc: LandLawDocument) -> LandRenderedLaw: ...
