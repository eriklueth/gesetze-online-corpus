"""Baden-Wuerttemberg-Adapter (Scaffold).

Upstream: https://www.landesrecht-bw.de
Data repo: landesrecht-bw-corpus-data

Siehe `by.py` fuer das Aktivierungs-Muster.
"""

from __future__ import annotations

from ._template import LandAdapter, LandLawDocument, LandLawMeta, LandRenderedLaw


class BadenWuerttembergAdapter(LandAdapter):
    iso = "bw"

    def fetch_toc(self):
        raise NotImplementedError(
            "BW-Adapter ist noch nicht aktiv. Siehe docs/ROADMAP.md Phase 8."
        )

    def fetch_law(self, meta: LandLawMeta) -> LandLawDocument:
        raise NotImplementedError

    def render(self, doc: LandLawDocument) -> LandRenderedLaw:
        raise NotImplementedError
