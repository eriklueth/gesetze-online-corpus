"""Nordrhein-Westfalen-Adapter (Scaffold).

Upstream: https://recht.nrw.de
Data repo: landesrecht-nw-corpus-data

Siehe `by.py` fuer das Aktivierungs-Muster.
"""

from __future__ import annotations

from ._template import LandAdapter, LandLawDocument, LandLawMeta, LandRenderedLaw


class NordrheinWestfalenAdapter(LandAdapter):
    iso = "nw"

    def fetch_toc(self):
        raise NotImplementedError(
            "NRW-Adapter ist noch nicht aktiv. Siehe docs/ROADMAP.md Phase 8."
        )

    def fetch_law(self, meta: LandLawMeta) -> LandLawDocument:
        raise NotImplementedError

    def render(self, doc: LandLawDocument) -> LandRenderedLaw:
        raise NotImplementedError
