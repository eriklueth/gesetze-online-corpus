"""Minimal EUR-Lex client (CELEX probe only).

The real fetcher uses SPARQL against Cellar to enumerate changes
incrementally. Until that's activated, this module exposes a single
`probe_celex(celex)` helper that dereferences a CELEX number into its
German-language HTML fallback via content negotiation.

Kept tiny on purpose — no writer, no canonicalization. Its job is to
make the upstream reachable from the CLI so the scaffold can be
exercised before activation.
"""

from __future__ import annotations

from ...http import get

_EUR_LEX_CONTENT_NEG = "https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:{celex}"
_EUR_LEX_META = "https://eur-lex.europa.eu/legal-content/DE/AUTO/?uri=CELEX:{celex}"


def probe_celex(celex: str) -> dict:
    """Return a small metadata dict for a CELEX.

    Does two GETs: the HTML renders for body, the AUTO variant for
    title. Both are best-effort; any parse error yields an empty
    value rather than an exception so the probe is still useful for
    diagnostics.
    """
    from lxml import html as lxml_html

    r = get(_EUR_LEX_CONTENT_NEG.format(celex=celex))
    body = r.content
    title = ""
    eli = ""
    try:
        doc = lxml_html.fromstring(body)
        title_el = doc.find(".//title")
        if title_el is not None and title_el.text:
            title = title_el.text.strip()
        for link in doc.iter("link"):
            href = link.get("href") or ""
            if "eli" in href:
                eli = href
                break
    except Exception:
        pass

    return {
        "celex": celex,
        "title": title,
        "eli": eli,
        "language": "de",
        "doc_type": _celex_doc_type(celex),
        "bytes": len(body),
    }


def _celex_doc_type(celex: str) -> str:
    """Infer document type from the CELEX sector/type letter.

    Sector 3 covers regular legislation: R = Verordnung, L = Richtlinie,
    D = Beschluss. We stay conservative and return "sonstige" for
    anything outside these common cases.
    """
    if len(celex) < 6:
        return "sonstige"
    type_char = celex[5:6]
    mapping = {"R": "eu-verordnung", "L": "eu-richtlinie", "D": "eu-beschluss"}
    return mapping.get(type_char, "sonstige")
