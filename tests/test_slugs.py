from gesetze_corpus.util.slugs import classify_enbez


def test_paragraph_simple():
    assert classify_enbez("§ 1") == ("paragraph", "0001")


def test_paragraph_with_letter_suffix():
    assert classify_enbez("§ 14a") == ("paragraph", "0014a")


def test_article():
    assert classify_enbez("Artikel 5") == ("article", "art-0005")
    assert classify_enbez("Art 5") == ("article", "art-0005")


def test_annex_numbered():
    assert classify_enbez("Anlage 2") == ("annex", "0002")


def test_annex_unnumbered():
    assert classify_enbez("Anlage") == ("annex", "0000")


def test_non_sectioning_returns_none():
    assert classify_enbez("") is None
    assert classify_enbez("Erster Teil") is None
