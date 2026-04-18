from __future__ import annotations

from lxml import etree

_XML_DECL = b'<?xml version="1.0" encoding="UTF-8"?>\n'


def canonicalize_xml_bytes(raw: bytes) -> bytes:
    """Canonicalize XML bytes using XML Canonicalization 2.0.

    Strips comments and normalizes attribute order, whitespace in
    attributes and namespace declarations. The result is prepended with
    an explicit UTF-8 XML declaration and ends with a single newline.
    """
    parser = etree.XMLParser(
        remove_blank_text=False,
        remove_comments=False,
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
    )
    root = etree.fromstring(raw, parser=parser)
    canon = etree.tostring(  # type: ignore[call-overload]
        root,
        method="c14n2",
        with_comments=False,
        strip_text=False,
    )
    if not canon.endswith(b"\n"):
        canon = canon + b"\n"
    return _XML_DECL + canon
