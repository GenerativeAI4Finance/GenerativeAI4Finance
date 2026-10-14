import pytest

from entity_resolution import normalize_identifier, normalize_name


@pytest.mark.parametrize(
    "raw",
    [
        "Quillon Agro Exports Private Limited",
        "QUILLON AGRO EXPORTS PVT. LTD.",
        "Quillon Agro Exports Pvt Ltd",
        "Quillon Agro Exports (P.V.T.) Ltd.",
    ],
)
def test_private_limited_variants_share_core_and_form(raw):
    n = normalize_name(raw)
    assert n.core == "quillon agro exports"
    assert n.legal_form == "private limited"


def test_ampersand_and_and_are_the_same():
    assert (
        normalize_name("Marlowe & Finch Corp").core
        == normalize_name("Marlowe and Finch Corporation").core
    )


def test_abbreviations_are_expanded():
    assert (
        normalize_name("Orvane Mfg. Intl. Ltd").core
        == "orvane manufacturing international"
    )


def test_transliteration_placeholders():
    a = normalize_name("Shree Vaibhav Lakshmi Textiles LLP")
    b = normalize_name("Sri Vaibhav Laxmi Textiles L.L.P.")
    assert a.core == b.core
    assert a.legal_form == b.legal_form == "llp"


def test_accents_are_folded():
    assert normalize_name("Société Lumière Ltd").core == "societe lumiere"


def test_stacked_suffix_keeps_outer_legal_form():
    n = normalize_name("Northgate Trading Co. Ltd")
    assert n.core == "northgate trading"
    assert n.legal_form == "limited"


def test_name_that_is_only_a_suffix_is_not_emptied():
    assert normalize_name("Limited").core == "limited"


def test_identifier_normalisation():
    assert normalize_identifier("syn-in 100877") == normalize_identifier(
        "SYN-IN-100877"
    )
    assert normalize_identifier("") is None
    assert normalize_identifier(None) is None
