"""Bayern-Adapter (Scaffold).

Upstream: https://www.gesetze-bayern.de
Data repo: landesrecht-by-corpus-data

Status: Adapter-Klasse steht, kein produktiver Fetch. Aktivierung in
Phase 8 — bis dahin wirft jeder Aufruf von `fetch_toc` eine
`NotImplementedError` mit Link auf die Roadmap.
"""

from __future__ import annotations

from ._template import LandAdapter, LandLawDocument, LandLawMeta, LandRenderedLaw


class BayernAdapter(LandAdapter):
    iso = "by"

    def fetch_toc(self):
        raise NotImplementedError(
            "Bayern-Adapter ist noch nicht aktiv. Siehe docs/ROADMAP.md Phase 8."
        )

    def fetch_law(self, meta: LandLawMeta) -> LandLawDocument:
        raise NotImplementedError

    def render(self, doc: LandLawDocument) -> LandRenderedLaw:
        raise NotImplementedError
