import pytest

from entity_resolution import normalize_identifier, normalize_name
from entity_resolution.normalize import (
    normalize_city,
    normalize_jurisdiction,
    normalize_scheme,
)


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


def test_identifier_case_and_separators_do_not_matter():
    assert normalize_identifier(" gb-0123/ab ") == "GB0123AB"


def test_numeric_identifiers_lose_leading_zeros():
    assert (
        normalize_identifier("00445790") == normalize_identifier("445790") == "445790"
    )
    assert normalize_identifier("SC0012") == "SC0012"


@pytest.mark.parametrize("value", ["N/A", "none", "NULL", "-", "000", "  "])
def test_placeholder_identifiers_count_as_missing(value):
    assert normalize_identifier(value) is None


@pytest.mark.parametrize(
    ("raw", "core", "form"),
    [
        ("Quillon Agro Exports Pvt.Ltd.", "quillon agro exports", "private limited"),
        ("Kestrel Paper Pty Ltd", "kestrel paper", "private limited"),
        ("Kestrel Paper AG", "kestrel paper", "ag"),
        ("Kestrel Paper S.A.", "kestrel paper", "sa"),
        ("Kestrel Paper SA", "kestrel paper", "sa"),
        ("Kestrel Paper B.V.", "kestrel paper", "bv"),
        ("Kestrel Paper N.V.", "kestrel paper", "nv"),
        ("Kestrel Paper S.p.A.", "kestrel paper", "spa"),
        ("Kestrel Paper S.r.l.", "kestrel paper", "srl"),
        ("Moller Shipping A/S", "moller shipping", "as"),
        ("Kestrel Paper", "kestrel paper", None),
    ],
)
def test_more_legal_forms_are_stripped(raw, core, form):
    n = normalize_name(raw)
    assert (n.core, n.legal_form) == (core, form)


def test_apostrophes_are_dropped_not_turned_into_spaces():
    assert normalize_name("Orvane Int'l Ltd").core == "orvane international"
    assert normalize_name("Orvane Int’l Ltd").core == "orvane international"
    assert normalize_name("Moody's Bakery").core == "moodys bakery"


def test_dotted_initials_join_but_dots_between_words_split():
    assert normalize_name("K.P.M. Ltd").core == "kpm"
    assert normalize_name("Kestrel Paper Mfg.Ltd.").legal_form == "limited"
    assert (
        normalize_name("Kestrel Paper Mfg.Ltd.").core == "kestrel paper manufacturing"
    )


@pytest.mark.parametrize(
    ("raw", "core"),
    [
        ("Straße Holdings", "strasse holdings"),
        ("Møller Shipping", "moller shipping"),
        ("Łódź Textiles", "lodz textiles"),
        ("Æther Labs", "aether labs"),
        ("Müller Logistik GmbH", "muller logistik"),
    ],
)
def test_letters_without_a_decomposition_are_folded(raw, core):
    assert normalize_name(raw).core == core


def test_non_latin_letters_are_kept_and_casefolded():
    n = normalize_name("Газпром Energy")
    assert n.core == "газпром energy"
    assert n.scripts == {"CYRILLIC", "LATIN"}
    assert n.non_latin_scripts == {"CYRILLIC"}
    assert normalize_name("СЕВЕРНЫЙ ВЕТЕР").core == "северный ветер"


@pytest.mark.parametrize("raw", ["Лукойл", "東芝 Energy KK", "شركة Energy", "ΕΛΛΗΝΙΚΗ"])
def test_non_latin_names_do_not_vanish(raw):
    assert normalize_name(raw).core


def test_marks_on_non_latin_letters_are_kept():
    assert normalize_name("Йод").core != normalize_name("Иод").core


def test_different_non_latin_names_stay_different():
    assert normalize_name("Газпром").core != normalize_name("Лукойл").core


def test_coverage_drops_when_symbols_are_lost():
    assert normalize_name("Acme Ltd").coverage == 1.0
    assert normalize_name("Acme ★★★★★★").coverage < 0.5


def test_stopword_only_name_is_not_emptied():
    assert normalize_name("The").core == "the"


def test_name_must_be_a_string():
    with pytest.raises(TypeError):
        normalize_name(None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("UK", "GB"),
        ("gb", "GB"),
        ("GB ", "GB"),
        (" gbr", "GB"),
        ("IN", "IN"),
        ("  ", None),
        (None, None),
    ],
)
def test_jurisdiction_codes_are_canonical(raw, expected):
    assert normalize_jurisdiction(raw) == expected


def test_city_ignores_case_accents_and_spacing():
    assert normalize_city(" Zürich ") == normalize_city("ZURICH") == "zurich"
    assert normalize_city("") is None


def test_scheme_labels_compare_loosely():
    assert normalize_scheme("Companies House") == normalize_scheme("companies-house")
    assert normalize_scheme("") is None
