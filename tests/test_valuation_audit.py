from tools.valuation_audit import language_heuristic


def test_language_heuristic_does_not_impute_unknown_text():
    assert language_heuristic("ZXQ 123") == "unresolved"


def test_language_heuristic_detects_synthetic_domain_markers():
    assert language_heuristic("remove and replace floor") == "english"
    assert language_heuristic("boden entfernen und erneuern") == "german"
