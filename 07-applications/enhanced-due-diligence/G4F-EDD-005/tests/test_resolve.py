import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

import entity_resolution.normalize as normalize_module
from entity_resolution import (
    LIKELY_MATCH,
    NEEDS_REVIEW,
    NO_MATCH,
    MatchConfig,
    Record,
    generate_candidates,
    load_records,
    record_decision,
    resolve,
    score_pair,
)
from entity_resolution.__main__ import main

resolve_module = sys.modules["entity_resolution.resolve"]

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "synthetic_companies.json"


@pytest.fixture(scope="module")
def results():
    return {(r.left_id, r.right_id): r for r in resolve(load_records(DATA)).matches}


def pair(left_name, right_name, **shared):
    """Two records that differ only in name, plus whatever is passed in `shared`."""
    return Record("A", left_name, **shared), Record("B", right_name, **shared)


def write_records(path, rows):
    path.write_text(json.dumps({"records": rows}, ensure_ascii=False), encoding="utf-8")


# True matches


def test_ids_match_across_suffix_and_punctuation_variants(results):
    r = results[("REG-006", "VEN-006")]
    assert r.label == LIKELY_MATCH
    assert r.score == 100.0
    assert r.evidence["registration_id"] == "match"


def test_transliteration_with_matching_id(results):
    r = results[("REG-002", "VEN-002")]
    assert r.label == LIKELY_MATCH
    assert r.evidence["registration_id"] == "match"


def test_alias_hit_is_reported(results):
    r = results[("REG-003", "VEN-003")]
    assert r.label == LIKELY_MATCH
    assert r.evidence["name"]["alias_used"] is True
    assert r.evidence["name"]["left"] == "ZBL Research"
    assert any("alias" in note for note in r.evidence["notes"])


def test_partial_name_goes_to_review_not_match(results):
    r = results[("REG-001", "NEWS-001")]
    assert r.label == NEEDS_REVIEW
    assert r.evidence["name"]["score"] == 75.0
    assert r.score == 58.8


def test_transliteration_is_what_makes_spellings_match():
    a, b = pair("Shree Vaibhav Lakshmi Textiles", "Sri Vaibhav Laxmi Textiles")
    assert score_pair(a, b).evidence["name"]["score"] == 100.0


def test_transliteration_without_the_table_scores_lower(monkeypatch):
    monkeypatch.setattr(normalize_module, "TRANSLITERATIONS", {})
    a, b = pair("Shree Vaibhav Lakshmi Textiles", "Sri Vaibhav Laxmi Textiles")
    assert score_pair(a, b).evidence["name"]["score"] < 100.0


def test_accents_and_special_letters_do_not_hurt_a_match():
    a = Record(
        "A", "Møller Straße Łódź Ltd", registration_id="SYN-1", jurisdiction="PL"
    )
    b = Record(
        "B", "Moller Strasse Lodz Limited", registration_id="SYN-1", jurisdiction="PL"
    )
    r = score_pair(a, b)
    assert r.evidence["name"]["score"] == 100.0
    assert r.label == LIKELY_MATCH


# Identifiers


@pytest.mark.parametrize(
    ("left_id", "right_id"),
    [("00445790", "445790"), ("SYN-GB-1", "syn gb 1"), (" 0445790", "445-790")],
)
def test_equivalent_ids_match(left_id, right_id):
    a = Record("A", "Kestrel Paper Ltd", registration_id=left_id, jurisdiction="GB")
    b = Record("B", "Kestrel Paper Ltd", registration_id=right_id, jurisdiction="GB")
    r = score_pair(a, b)
    assert r.evidence["registration_id"] == "match"
    assert r.label == LIKELY_MATCH


def test_different_kinds_of_id_are_not_a_conflict():
    cin = Record(
        "A",
        "Quillon Agro Exports Pvt Ltd",
        registration_id="U01100MH2010PTC123456",
        jurisdiction="IN",
        city="Pune",
    )
    gstin = Record(
        "B",
        "Quillon Agro Exports Private Limited",
        registration_id="27AABCQ1234F1Z5",
        jurisdiction="IN",
        city="Pune",
    )
    r = score_pair(cin, gstin)
    assert r.evidence["registration_id"] == "unverified"
    assert r.label == NEEDS_REVIEW


def test_labelled_schemes_that_differ_are_not_compared():
    cin = Record(
        "A", "Quillon Agro Ltd", registration_id="U01100MH2010PTC123456",
        id_scheme="CIN", jurisdiction="IN",
    )  # fmt: skip
    gstin = Record(
        "B", "Quillon Agro Ltd", registration_id="27AABCQ1234F1Z5",
        id_scheme="GSTIN", jurisdiction="IN",
    )  # fmt: skip
    r = score_pair(cin, gstin)
    assert r.evidence["registration_id"] == "not comparable"
    assert any("different ID schemes" in note for note in r.evidence["notes"])
    assert r.label != NO_MATCH


def test_same_digits_in_different_schemes_do_not_match():
    a = Record(
        "A",
        "Kestrel Paper Ltd",
        registration_id="12345",
        id_scheme="CIN",
        jurisdiction="IN",
    )
    b = Record(
        "B",
        "Kestrel Paper Ltd",
        registration_id="12345",
        id_scheme="PAN",
        jurisdiction="IN",
    )
    assert score_pair(a, b).evidence["registration_id"] == "not comparable"


def test_ids_in_different_jurisdictions_are_not_compared():
    a = Record("A", "Kestrel Paper Ltd", registration_id="SYN-1", jurisdiction="GB")
    b = Record("B", "Kestrel Paper Ltd", registration_id="SYN-1", jurisdiction="IE")
    r = score_pair(a, b)
    assert r.evidence["registration_id"] == "not comparable"
    assert r.label != LIKELY_MATCH


def test_placeholder_ids_are_treated_as_missing():
    a, b = pair(
        "Kestrel Paper Ltd",
        "Kestrel Paper Ltd",
        registration_id="N/A",
        jurisdiction="GB",
    )
    assert score_pair(a, b).evidence["registration_id"] == "missing"


# False matches


def test_same_name_conflicting_ids_is_vetoed(results):
    r = results[("REG-004", "REG-005")]
    assert r.evidence["name"]["score"] == 100
    assert r.evidence["registration_id"] == "conflict"
    assert r.score == MatchConfig().id_conflict_cap
    assert r.label == NO_MATCH


def test_id_conflict_cap_holds_even_with_everything_else_agreeing():
    shared = {"id_scheme": "GB company number", "jurisdiction": "GB", "city": "York"}
    a = Record("A", "Kestrel Paper Mills Ltd", registration_id="SYN-1", **shared)
    b = Record("B", "Kestrel Paper Mills Ltd", registration_id="SYN-2", **shared)
    r = score_pair(a, b)
    assert r.score == MatchConfig().id_conflict_cap
    assert r.label == NO_MATCH


def test_different_ids_without_a_named_scheme_go_to_review_not_veto():
    shared = {"jurisdiction": "GB", "city": "York"}
    a = Record("A", "Kestrel Paper Mills Ltd", registration_id="SYN-1", **shared)
    b = Record("B", "Kestrel Paper Mills Ltd", registration_id="SYN-2", **shared)
    r = score_pair(a, b)
    assert r.evidence["registration_id"] == "unverified"
    assert r.label == NEEDS_REVIEW
    assert any("scheme is not given" in note for note in r.evidence["notes"])


def test_unverified_different_ids_can_still_score_as_no_match():
    a = Record("A", "Ashgrove Dairy", registration_id="SYN-1", jurisdiction="GB")
    b = Record("B", "Pelham Widgets", registration_id="SYN-2", jurisdiction="GB")

    result = score_pair(a, b)

    assert result.evidence["registration_id"] == "unverified"
    assert result.label == NO_MATCH


def test_same_name_different_jurisdiction_is_no_match(results):
    r = results[("REG-004", "VEN-004")]
    assert r.evidence["same_jurisdiction"] is False
    assert r.score == 50.0
    assert r.label == NO_MATCH


def test_shared_first_word_only_is_no_match(results):
    r = results[("REG-006", "VEN-007")]
    assert r.evidence["name"]["score"] == pytest.approx(48.97959183673469)
    assert r.score == 41.8
    assert r.label == NO_MATCH


@pytest.mark.parametrize(
    ("left_name", "right_name"),
    [
        ("First National Bank", "First National Bank"),
        ("First National Bank", "First National Bank of Ohio"),
        ("Bank of Ohio", "Ohio Bank"),
    ],
)
def test_common_names_without_an_id_stay_below_likely_match(left_name, right_name):
    a, b = pair(left_name, right_name, jurisdiction="US", city="Columbus")
    r = score_pair(a, b)
    assert r.evidence["registration_id"] == "missing"
    assert r.score < MatchConfig().likely_match
    assert r.label == NEEDS_REVIEW


def test_name_jurisdiction_and_city_alone_cannot_reach_likely_match():
    a, b = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB", city="York")
    # Raw evidence adds up to exactly 80.0, the likely_match threshold.
    r = score_pair(a, b, MatchConfig(name_weight=0.65))
    assert r.score == 79.9
    assert r.label == NEEDS_REVIEW
    assert any("capped at 79.9" in note for note in r.evidence["notes"])
    # Raising the weights does not lift the cap.
    heavy = MatchConfig(
        name_weight=1.0, city_match_bonus=50, jurisdiction_match_bonus=50
    )
    assert score_pair(a, b, heavy).score == 79.9


def test_no_id_cap_is_configurable():
    a, b = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB", city="York")
    assert score_pair(a, b, MatchConfig(no_id_cap=60)).score == 60.0
    assert score_pair(a, b, MatchConfig(no_id_cap=60)).label == NEEDS_REVIEW


def test_rounding_does_not_cross_configured_label_boundaries():
    a, b = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB", city="York")
    no_id = score_pair(a, b, MatchConfig(no_id_cap=79.99))
    assert no_id.score == 79.99
    assert no_id.label == NEEDS_REVIEW

    left = Record(
        "C",
        "Kestrel Paper",
        registration_id="SYN-1",
        id_scheme="GB",
        jurisdiction="GB",
        city="York",
    )
    right = Record(
        "D",
        "Kestrel Paper",
        registration_id="SYN-2",
        id_scheme="GB",
        jurisdiction="GB",
        city="York",
    )
    conflict = score_pair(
        left,
        right,
        MatchConfig(id_conflict_cap=54.99, allow_id_conflict_review=True),
    )
    assert conflict.score == 54.99
    assert conflict.label == NO_MATCH

    left = Record(
        "E",
        "Ashgrove Dairy",
        registration_id="SYN-3",
        id_scheme="GB",
        jurisdiction="GB",
    )
    right = Record(
        "F",
        "Pelham Widgets",
        registration_id="SYN-3",
        id_scheme="GB",
        jurisdiction="GB",
    )
    renamed = score_pair(left, right, MatchConfig(needs_review=55.04))
    assert renamed.score == 55.04
    assert renamed.label == NEEDS_REVIEW


@pytest.mark.parametrize("cap", [60.06, 79.99])
def test_rounding_preserves_no_id_cap_even_within_the_same_label(cap):
    a, b = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB", city="York")
    result = score_pair(a, b, MatchConfig(no_id_cap=cap))

    assert result.score <= cap
    assert result.label == NEEDS_REVIEW


def test_rounding_preserves_conflict_cap_even_within_the_same_label():
    shared = {"id_scheme": "CIN", "jurisdiction": "GB", "city": "York"}
    a = Record("A", "Kestrel Paper", registration_id="SYN-1", **shared)
    b = Record("B", "Kestrel Paper", registration_id="SYN-2", **shared)

    result = score_pair(a, b, MatchConfig(id_conflict_cap=30.06))

    assert result.score == 30.06
    assert result.label == NO_MATCH


@pytest.mark.parametrize(
    ("name_weight", "id_bonus", "needs_review", "likely_match"),
    [(0.4504, 0, 55.02, 80), (0.4496, 25, 55, 80)],
)
def test_labels_use_the_score_before_display_rounding(
    name_weight, id_bonus, needs_review, likely_match
):
    a, b = pair(
        "Kestrel Paper", "Kestrel Paper", registration_id="SYN-1", jurisdiction="GB"
    )
    config = MatchConfig(
        name_weight=name_weight,
        id_match_bonus=id_bonus,
        needs_review=needs_review,
        likely_match=likely_match,
    )

    result = score_pair(a, b, config)

    assert result.label == NEEDS_REVIEW
    assert needs_review <= result.score < likely_match


def test_cross_script_review_floor_and_ceiling_survive_rounding():
    a, b = pair("Северный Ветер", "Severnyi Veter", jurisdiction="RU")
    config = MatchConfig(needs_review=55.01, likely_match=55.02)

    result = score_pair(a, b, config)

    assert config.needs_review <= result.score < config.likely_match
    assert result.label == NEEDS_REVIEW


@pytest.mark.parametrize(
    ("other_name", "registration_id", "thresholds", "expected_label"),
    [
        ("Kestrel Papers", "SYN-1", {"likely_match": 97.594}, NEEDS_REVIEW),
        ("Kestrel Print", "SYN-1", {"likely_match": 84.99}, LIKELY_MATCH),
        ("Kestrel Papers", None, {"needs_review": 72.594}, NO_MATCH),
        ("Kestrel Print", None, {"needs_review": 59.99}, NEEDS_REVIEW),
    ],
)
def test_name_similarity_keeps_full_precision_through_resolution(
    other_name, registration_id, thresholds, expected_label, tmp_path, capsys
):
    records = [
        Record(
            "A", "Kestrel Paper", registration_id=registration_id, jurisdiction="GB"
        ),
        Record("B", other_name, registration_id=registration_id, jurisdiction="GB"),
    ]
    config = MatchConfig(**thresholds)

    (result,) = resolve(records, config).matches

    assert result.label == expected_label
    assert resolve_module._label(result.score, config) == expected_label
    assert record_decision(result, "analyst", True)["score"] == result.score
    path = tmp_path / "records.json"
    write_records(path, [dataclasses.asdict(record) for record in records])
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(thresholds), encoding="utf-8")
    assert main([str(path), "--config", str(config_path), "--json"]) == 0
    (shown,) = json.loads(capsys.readouterr().out)["matches"]
    assert (shown["score"], shown["label"]) == (result.score, expected_label)


@pytest.mark.parametrize(
    ("stars", "min_coverage", "expected_label"),
    [(5, 0.4442, LIKELY_MATCH), (7, 0.3638, NEEDS_REVIEW)],
)
def test_name_coverage_keeps_full_precision_through_resolution(
    stars, min_coverage, expected_label
):
    a, b = pair(
        "Acme" + "\u2605" * stars,
        "Acme" + "\u2605" * stars,
        registration_id="SYN-1",
        jurisdiction="GB",
    )

    (result,) = resolve([a, b], MatchConfig(min_name_coverage=min_coverage)).matches

    assert result.evidence["name"]["coverage"] == 4 / (4 + stars)
    assert result.label == expected_label


def test_a_lowered_likely_match_still_needs_an_id():
    a, b = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB", city="York")
    r = score_pair(a, b, MatchConfig(likely_match=70))
    assert r.score == 69.9
    assert r.label == NEEDS_REVIEW


# Same ID, different name


@pytest.mark.parametrize("other", ["Pelham Widgets Ltd", "Hollin Foods Ltd"])
def test_matching_id_with_a_different_name_is_never_below_review(other):
    a = Record("A", "Ashgrove Dairy Ltd", registration_id="SYN-GB-1", jurisdiction="GB")
    b = Record("B", other, registration_id="SYN-GB-1", jurisdiction="GB")
    r = score_pair(a, b)
    assert r.score >= MatchConfig().needs_review
    assert r.label == NEEDS_REVIEW
    assert any("renamed" in note for note in r.evidence["notes"])


def test_rename_in_sample_data(results):
    r = results[("REG-008", "VEN-009")]
    assert r.label == NEEDS_REVIEW
    assert r.score == MatchConfig().needs_review


# Non-Latin names


def test_different_cyrillic_names_with_a_shared_latin_word_are_not_a_match():
    a, b = pair(
        "Северный Ветер Energy", "Лунный Свет Energy", jurisdiction="RU", city="Moscow"
    )
    r = score_pair(a, b)
    assert r.evidence["cross_script"] is False
    assert r.evidence["name"]["score"] < 60
    assert r.label != LIKELY_MATCH
    assert r.label == NO_MATCH


def test_identical_cyrillic_names_compare_as_text():
    a = Record("A", "Северный Ветер ООО", registration_id="X1", jurisdiction="RU")
    b = Record("B", "СЕВЕРНЫЙ ВЕТЕР ООО", registration_id="X1", jurisdiction="RU")
    r = score_pair(a, b)
    assert r.evidence["name"]["score"] == 100.0
    assert r.label == LIKELY_MATCH


def test_cyrillic_against_latin_is_flagged_for_review_not_scored():
    a = Record("A", "Северный Ветер", registration_id="SYN-RU-1", jurisdiction="RU")
    b = Record("B", "Severnyi Veter", registration_id="SYN-RU-1", jurisdiction="RU")
    r = score_pair(a, b)
    assert r.evidence["cross_script"] is True
    assert r.evidence["name"]["score"] is None
    assert r.label == NEEDS_REVIEW
    assert any("different scripts" in note for note in r.evidence["notes"])


def test_cross_script_without_an_id_is_review_not_zero_and_not_likely():
    a = Record("A", "Северный Ветер", jurisdiction="RU", city="Moscow")
    b = Record("B", "Severnyi Veter", jurisdiction="RU", city="Moscow")
    r = score_pair(a, b)
    assert r.evidence["cross_script"] is True
    assert r.label == NEEDS_REVIEW
    assert r.score < MatchConfig().likely_match


def test_cross_script_does_not_override_an_id_conflict():
    shared = {"id_scheme": "OGRN", "jurisdiction": "RU"}
    a = Record("A", "Северный Ветер", registration_id="1", **shared)
    b = Record("B", "Severnyi Veter", registration_id="2", **shared)
    r = score_pair(a, b)
    assert r.evidence["cross_script"] is True
    assert r.label == NO_MATCH


def test_alias_in_the_other_script_makes_names_comparable():
    a = Record("A", "Северный Ветер", aliases=["Severnyi Veter"], jurisdiction="RU")
    b = Record("B", "Severnyi Veter Ltd", jurisdiction="RU")
    r = score_pair(a, b)
    assert r.evidence["cross_script"] is False
    assert r.evidence["name"]["alias_used"] is True
    assert r.evidence["name"]["score"] == 100.0


def test_much_of_a_name_lost_in_normalisation_limits_the_score():
    star = "\u2605" * 8
    a, b = pair(
        f"Acme {star}", f"Acme {star}", registration_id="SYN-1", jurisdiction="GB"
    )
    r = score_pair(a, b)
    assert r.evidence["name"]["coverage"] < 0.5
    assert r.score < MatchConfig().likely_match
    assert r.label == NEEDS_REVIEW


def test_cjk_names_are_compared_not_dropped():
    a, b = pair("東芝 Energy KK", "日立 Energy KK", jurisdiction="JP", city="Tokyo")
    r = score_pair(a, b)
    assert r.evidence["name"]["left_normalized"] == "東芝 energy kk"
    assert r.label != LIKELY_MATCH


# Jurisdiction and city


@pytest.mark.parametrize(
    ("left", "right"), [("UK", "GB"), ("GB ", "GB"), ("gb", "GBR")]
)
def test_jurisdiction_spellings_are_the_same_jurisdiction(left, right):
    a = Record("A", "Kestrel Paper Ltd", registration_id="SYN-1", jurisdiction=left)
    b = Record("B", "Kestrel Paper Ltd", registration_id="SYN-1", jurisdiction=right)
    r = score_pair(a, b)
    assert r.evidence["same_jurisdiction"] is True
    assert r.evidence["registration_id"] == "match"


def test_city_comparison_ignores_case_and_accents():
    a = Record("A", "Kestrel Paper Ltd", city="Zürich")
    b = Record("B", "Kestrel Paper Ltd", city=" ZURICH ")
    assert any("same city" in note for note in score_pair(a, b).evidence["notes"])


# Candidate generation


def test_blocking_skips_unrelated_records():
    records = load_records(DATA)
    pairs = {(a.record_id, b.record_id) for a, b in generate_candidates(records).pairs}
    assert ("REG-001", "VEN-001") in pairs
    assert ("REG-001", "REG-003") not in pairs
    # "Trading" alone is too common to block on, so Northgate pairs come from "northgate".
    assert ("REG-004", "VEN-004") in pairs


def test_shared_identifier_is_a_blocking_key():
    a = Record("A", "Ashgrove Dairy Ltd", registration_id="SYN-GB-1", jurisdiction="GB")
    b = Record("B", "AD Foods Ltd", registration_id="syn gb 1", jurisdiction="GB")
    assert len(generate_candidates([a, b]).pairs) == 1


def test_id_blocks_keep_schemes_separate_when_a_mixed_block_is_oversized():
    records = []
    for i in range(499):
        scheme = f"registry-{i}"
        records.extend(
            [
                Record(
                    f"OTHER-{i}-A",
                    f"Vantor{i:04d}A",
                    registration_id="SHARED-1",
                    id_scheme=scheme,
                    jurisdiction="GB",
                ),
                Record(
                    f"OTHER-{i}-B",
                    f"Quillon{i:04d}B",
                    registration_id="SHARED-1",
                    id_scheme=scheme,
                    jurisdiction="GB",
                ),
            ]
        )
    records.append(
        Record(
            "OTHER-SINGLE",
            "Farnham Group",
            registration_id="SHARED-1",
            id_scheme="registry-single",
            jurisdiction="GB",
        )
    )
    records.extend(
        [
            Record(
                "RENAMED-OLD",
                "Ashgrove Dairy",
                registration_id="SHARED-1",
                id_scheme="CIN",
                jurisdiction="GB",
            ),
            Record(
                "RENAMED-NEW",
                "Pelham Widgets",
                registration_id="SHARED-1",
                id_scheme="CIN",
                jurisdiction="GB",
            ),
        ]
    )

    candidates = generate_candidates(records)
    pair_ids = {(a.record_id, b.record_id) for a, b in candidates.pairs}

    assert ("RENAMED-OLD", "RENAMED-NEW") in pair_ids
    assert candidates.skipped_blocks == []


def test_same_id_with_one_missing_scheme_remains_a_candidate():
    labelled = Record(
        "A",
        "Ashgrove Dairy",
        registration_id="SYN-1",
        id_scheme="CIN",
        jurisdiction="GB",
    )
    unlabelled = Record(
        "B", "Pelham Widgets", registration_id="SYN-1", jurisdiction="GB"
    )

    assert generate_candidates([labelled, unlabelled]).pairs == [(labelled, unlabelled)]


def test_different_named_schemes_do_not_block_by_id_alone():
    cin = Record(
        "A",
        "Ashgrove Dairy",
        registration_id="SYN-1",
        id_scheme="CIN",
        jurisdiction="GB",
    )
    gstin = Record(
        "B",
        "Pelham Widgets",
        registration_id="SYN-1",
        id_scheme="GSTIN",
        jurisdiction="GB",
    )

    assert generate_candidates([cin, gstin]).pairs == []


@pytest.mark.parametrize(("unlabelled_count", "limit"), [(1, 3), (2, 3)])
def test_unlabelled_cross_scheme_blocks_report_only_omitted_cross_pairs(
    unlabelled_count, limit
):
    records = [
        Record("A", "Ashgrove Dairy", registration_id="SYN-1", id_scheme="CIN"),
        Record("B", "Pelham Widgets", registration_id="SYN-1", id_scheme="CIN"),
    ] + [
        Record(f"U{i}", f"Quillon{i:03d}", registration_id="SYN-1")
        for i in range(unlabelled_count)
    ]

    candidates = generate_candidates(records, MatchConfig(max_id_block_size=limit))
    pairs = {(a.record_id, b.record_id) for a, b in candidates.pairs}

    assert ("A", "B") in pairs
    if unlabelled_count == 1:
        assert pairs == {("A", "B"), ("A", "U0"), ("B", "U0")}
        assert candidates.skipped_blocks == []
    else:
        assert pairs == {("A", "B"), ("U0", "U1")}
        (block,) = candidates.skipped_blocks
        assert block.size == 4
        assert block.pairs_not_compared == 4
        assert block.to_dict()["pairs_not_compared"] == 4


def test_identifier_blocks_are_namespaced_by_jurisdiction():
    a = Record("A", "Ashgrove Dairy Ltd", registration_id="SYN-1", jurisdiction="GB")
    b = Record("B", "Hollin Foods Ltd", registration_id="SYN-1", jurisdiction="IE")
    assert generate_candidates([a, b]).pairs == []


def token_block(n):
    return [Record(f"R{i}", f"Pelham {i:03d}") for i in range(n)]


def id_block(n):
    return [
        Record(
            f"R{i}", f"Vantor{i:03d} Ltd", registration_id="SYN-1", jurisdiction="GB"
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(("n", "pairs"), [(49, 49 * 48 // 2), (50, 50 * 49 // 2)])
def test_name_token_blocks_up_to_the_limit_are_compared(n, pairs):
    candidates = generate_candidates(token_block(n))
    assert len(candidates.pairs) == pairs
    assert candidates.skipped_blocks == []


def test_name_token_block_over_the_limit_is_skipped_and_reported():
    candidates = generate_candidates(token_block(51))
    assert candidates.pairs == []
    (block,) = candidates.skipped_blocks
    assert (block.kind, block.key, block.size, block.limit) == (
        "name token",
        "pelham",
        51,
        50,
    )
    assert block.pairs_not_compared == 51 * 50 // 2


@pytest.mark.parametrize("n", [49, 50, 51])
def test_registration_id_blocks_are_never_dropped_at_the_name_limit(n):
    candidates = generate_candidates(id_block(n))
    assert len(candidates.pairs) == n * (n - 1) // 2
    assert candidates.skipped_blocks == []


def test_oversized_registration_id_block_is_skipped_and_reported():
    candidates = generate_candidates(id_block(51), MatchConfig(max_id_block_size=50))
    assert candidates.pairs == []
    (block,) = candidates.skipped_blocks
    assert block.kind == "registration ID"
    assert block.key == "GB:SYN1"
    assert (
        generate_candidates(
            id_block(50), MatchConfig(max_id_block_size=50)
        ).skipped_blocks
        == []
    )


def test_a_pair_in_a_skipped_name_block_is_still_found_through_its_id():
    records = token_block(51)
    records[0] = Record("R0", "Pelham 000", registration_id="SYN-9", jurisdiction="GB")
    records[1] = Record("R1", "Pelham 001", registration_id="SYN-9", jurisdiction="GB")
    candidates = generate_candidates(records)
    assert [(a.record_id, b.record_id) for a, b in candidates.pairs] == [("R0", "R1")]
    assert [b.kind for b in candidates.skipped_blocks] == ["name token"]


def test_resolve_reports_skipped_blocks():
    resolution = resolve(token_block(51))
    assert resolution.matches == []
    assert resolution.to_dict()["skipped_blocks"][0]["key"] == "pelham"


def test_normalised_names_are_computed_once_per_name(monkeypatch):
    calls = []
    real = resolve_module.normalize_name

    def counting(name):
        calls.append(name)
        return real(name)

    monkeypatch.setattr(resolve_module, "normalize_name", counting)
    records = [
        Record(f"R{i}", f"Pelham Widgets {i:02d}", aliases=[f"PW {i:02d}", "Pelham"])
        for i in range(10)
    ]
    assert len(resolve(records).matches) == 45
    assert len(calls) == 10 * 3


# Thresholds and review


def test_thresholds_are_configurable(results):
    a = Record("A", "Kestrel Paper Mills", registration_id="SYN-1", jurisdiction="GB")
    b = Record("B", "Kestrel Paper", registration_id="SYN-1", jurisdiction="GB")
    assert score_pair(a, b).label == LIKELY_MATCH
    assert score_pair(a, b, MatchConfig(likely_match=95)).label == NEEDS_REVIEW
    # A matching ID keeps the pair in review however high the bar is set.
    assert (
        score_pair(a, b, MatchConfig(likely_match=99, needs_review=98)).label
        == NEEDS_REVIEW
    )
    c = Record("C", "Kestrel Paper Mills", jurisdiction="GB")
    d = Record("D", "Kestrel Paper", jurisdiction="GB")
    assert (
        score_pair(c, d, MatchConfig(likely_match=99, needs_review=98)).label
        == NO_MATCH
    )


def test_label_changes_exactly_at_the_thresholds():
    a, b = pair(
        "Kestrel Paper", "Kestrel Paper", registration_id="SYN-1", jurisdiction="GB"
    )
    # name 100 * 0.65 + id match 25 = 90.0 with the default weights, plus jurisdiction 10 = 100.
    base = {"jurisdiction_match_bonus": 0}
    assert score_pair(a, b, MatchConfig(**base)).score == 90.0
    assert (
        score_pair(a, b, MatchConfig(likely_match=90.0, **base)).label == LIKELY_MATCH
    )
    assert (
        score_pair(a, b, MatchConfig(likely_match=90.1, **base)).label == NEEDS_REVIEW
    )
    assert (
        score_pair(a, b, MatchConfig(likely_match=99, needs_review=90.0, **base)).label
        == NEEDS_REVIEW
    )
    # Without an ID the same name and jurisdiction score 65 + 10 = 75.
    c, d = pair("Kestrel Paper", "Kestrel Paper", jurisdiction="GB")
    assert (
        score_pair(c, d, MatchConfig(likely_match=99, needs_review=75.0)).label
        == NEEDS_REVIEW
    )
    assert (
        score_pair(c, d, MatchConfig(likely_match=99, needs_review=75.1)).label
        == NO_MATCH
    )


def test_sample_pair_on_the_old_threshold_does_not_depend_on_weights(results):
    r = results[("REG-001", "VEN-001")]
    assert r.label == NEEDS_REVIEW
    assert r.score == 79.9
    a, b = (
        rec for rec in load_records(DATA) if rec.record_id in ("REG-001", "VEN-001")
    )
    assert score_pair(a, b, MatchConfig(name_weight=0.7)).score == 79.9


def test_config_loads_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"likely_match": 90, "needs_review": 60}), encoding="utf-8"
    )
    config = MatchConfig.from_file(path)
    assert (config.likely_match, config.needs_review) == (90, 60)


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        MatchConfig(likely_match=50, needs_review=70)
    with pytest.raises(ValueError):
        MatchConfig(likely_match=60, needs_review=60)
    with pytest.raises(ValueError, match="between 0 and 100"):
        MatchConfig(likely_match=150)


def test_misspelt_config_key_gives_a_clear_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"likely_match": 85, "needs_reveiw": 60}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="needs_reveiw.*did you mean 'needs_review'"):
        MatchConfig.from_file(path)


@pytest.mark.parametrize(
    "bad",
    [
        {"likely_match": "80"},
        {"likely_match": True},
        {"name_weight": -1},
        {"name_weight": 2},
        {"max_block_size": 1},
        {"max_block_size": 10.5},
        {"allow_id_conflict_review": "yes"},
        {"no_id_cap": 95},
        {"no_id_cap": 10},
    ],
)
def test_bad_config_values_rejected(bad):
    with pytest.raises(ValueError):
        MatchConfig(**bad)


def test_id_conflict_cap_must_stay_below_needs_review():
    with pytest.raises(ValueError, match="id_conflict_cap"):
        MatchConfig(id_conflict_cap=99)
    with pytest.raises(ValueError, match="id_conflict_cap"):
        MatchConfig(id_conflict_cap=55)
    assert MatchConfig(id_conflict_cap=54.9).id_conflict_cap == 54.9


def test_id_conflict_cap_opt_out_is_explicit():
    config = MatchConfig(id_conflict_cap=70, allow_id_conflict_review=True)
    shared = {"id_scheme": "CIN", "jurisdiction": "GB", "city": "York"}
    a = Record("A", "Kestrel Paper Mills Ltd", registration_id="SYN-1", **shared)
    b = Record("B", "Kestrel Paper Mills Ltd", registration_id="SYN-2", **shared)
    r = score_pair(a, b, config)
    assert r.score == 70.0
    assert r.label == NEEDS_REVIEW


def test_config_cannot_be_changed_after_validation():
    config = MatchConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.id_conflict_cap = 99


# Input validation


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"record_id": "", "name": "X"}, "record_id"),
        ({"record_id": "A", "name": None}, "name is required"),
        ({"record_id": "A", "name": ""}, "name must not be blank"),
        ({"record_id": "A", "name": "   "}, "name must not be blank"),
        ({"record_id": "A", "name": "..."}, "no letters or digits"),
        ({"record_id": "A", "name": 42}, "name must be a string"),
        (
            {"record_id": "A", "name": "Kestrel", "aliases": "Kx"},
            "aliases must be a list",
        ),
        ({"record_id": "A", "name": "Kestrel", "aliases": [None]}, "alias is required"),
        (
            {"record_id": "A", "name": "Kestrel", "aliases": ["Kx", 3]},
            "alias must be a string",
        ),
        (
            {"record_id": "A", "name": "Kestrel", "aliases": [" "]},
            "alias must not be blank",
        ),
        (
            {"record_id": "A", "name": "Kestrel", "registration_id": 445790},
            "registration_id must be a string",
        ),
        (
            {"record_id": "A", "name": "Kestrel", "city": ["Pune"]},
            "city must be a string",
        ),
    ],
)
def test_invalid_records_raise_clear_errors(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Record(**kwargs)


@pytest.mark.parametrize("marks", ["\u0301\u0301", "\u093e", "\u05b0"])
@pytest.mark.parametrize("as_alias", [False, True])
def test_combining_marks_alone_are_not_a_name_or_alias(marks, as_alias):
    kwargs = {"name": "Kestrel", "aliases": [marks]} if as_alias else {"name": marks}

    with pytest.raises(ValueError, match="no letters or digits"):
        Record("A", **kwargs)


@pytest.mark.parametrize(
    "text", ["Caf\u0065\u0301", "\u0915\u093e", "\u0439", "\u00b2"]
)
@pytest.mark.parametrize("as_alias", [False, True])
def test_letters_and_numbers_with_combining_marks_remain_valid(text, as_alias):
    kwargs = {"name": "Kestrel", "aliases": [text]} if as_alias else {"name": text}

    record = Record("A", **kwargs)

    assert (record.aliases[0] if as_alias else record.name) == text


def test_aliases_none_means_no_aliases_and_lists_are_kept():
    assert Record("A", "Kestrel", aliases=None).aliases == ()
    assert Record("A", "Kestrel", aliases=["Kx"]).aliases == ("Kx",)


def test_single_letter_alias_string_no_longer_scores_as_a_match():
    with pytest.raises(ValueError, match="aliases must be a list"):
        Record("A", "Kestrel Paper", aliases="k")


def test_duplicate_record_ids_rejected():
    with pytest.raises(ValueError, match="duplicate record_id 'A'"):
        generate_candidates([Record("A", "Kestrel"), Record("A", "Vantor")])


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [{"record_id": "A", "name": "Kestrel", "country": "GB"}],
            "unknown field.*'country'",
        ),
        ([{"record_id": "A"}], "missing name"),
        ([{"name": "Kestrel"}], "missing record_id"),
        (["Kestrel"], "must be a JSON object"),
        ([{"record_id": "A", "name": None}], "name is required"),
        (
            [
                {"record_id": "A", "name": "Kestrel"},
                {"record_id": "A", "name": "Vantor"},
            ],
            "duplicate record_id",
        ),
    ],
)
def test_load_records_reports_bad_rows(tmp_path, rows, message):
    path = tmp_path / "records.json"
    write_records(path, rows)
    with pytest.raises(ValueError, match=message):
        load_records(path)


def test_load_records_rejects_wrong_shape_and_bad_json(tmp_path):
    path = tmp_path / "records.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="'records' list"):
        load_records(path)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_records(path)
    path.write_bytes('{"records": []}'.encode("utf-16"))
    with pytest.raises(ValueError):
        load_records(path)


# Files and encoding


def test_records_load_as_utf8(tmp_path):
    path = tmp_path / "records.json"
    names = [
        "Société Lumière Ltd",
        "Северный Ветер ООО",
        "東芝 Energy KK",
        "Straße Łódź",
    ]
    write_records(
        path, [{"record_id": f"R{i}", "name": n} for i, n in enumerate(names)]
    )
    assert [r.name for r in load_records(path)] == names


def test_utf8_file_with_byte_order_mark_loads(tmp_path):
    path = tmp_path / "records.json"
    body = json.dumps(
        {"records": [{"record_id": "A", "name": "Société"}]}, ensure_ascii=False
    )
    path.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    assert load_records(path)[0].name == "Société"


def test_config_file_is_read_as_utf8(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'{"_note": "caf\xc3\xa9"}')
    with pytest.raises(ValueError, match="unknown config key '_note'"):
        MatchConfig.from_file(path)


def test_cli_handles_non_latin_names_whatever_the_console_encoding(tmp_path):
    path = tmp_path / "records.json"
    write_records(
        path,
        [
            {
                "record_id": "A",
                "name": "Северный Ветер",
                "registration_id": "1",
                "jurisdiction": "RU",
            },
            {
                "record_id": "B",
                "name": "Severnyi Veter",
                "registration_id": "1",
                "jurisdiction": "RU",
            },
        ],
    )
    done = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-m", "entity_resolution", str(path)],
        check=False,
        cwd=ROOT,
        capture_output=True,
        env={"PYTHONIOENCODING": "cp1252", "PATH": "", "SYSTEMROOT": "C:\\Windows"},
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "'Северный Ветер' vs 'Severnyi Veter'" in done.stdout.decode("utf-8")


# Results and review


def test_results_are_unconfirmed_until_a_reviewer_decides(results):
    assert all(r.status == "unconfirmed" for r in results.values())
    result = results[("REG-001", "VEN-001")]
    decision = record_decision(result, reviewer="analyst-1", accepted=True)
    assert decision["status"] == "confirmed"
    assert decision["reviewer"] == "analyst-1"
    assert decision["score"] == result.score
    assert decision["label"] == result.label
    # The decision is a separate record. The result itself never changes.
    assert result.status == "unconfirmed"
    rejected = record_decision(
        result, reviewer="analyst-1", accepted=False, note="different parent"
    )
    assert rejected["status"] == "rejected"
    assert rejected["note"] == "different parent"


@pytest.mark.parametrize("reviewer", ["", "   ", None, 7])
def test_decision_needs_a_real_reviewer_name(results, reviewer):
    with pytest.raises(ValueError, match="reviewer is required"):
        record_decision(
            results[("REG-001", "VEN-001")], reviewer=reviewer, accepted=True
        )


def test_decision_input_is_checked(results):
    result = results[("REG-001", "VEN-001")]
    with pytest.raises(TypeError):
        record_decision(result, reviewer="a", accepted="yes")
    with pytest.raises(TypeError):
        record_decision({"left_id": "x"}, reviewer="a", accepted=True)


def test_results_are_immutable(results):
    r = results[("REG-001", "VEN-001")]
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.score = 100.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.label = LIKELY_MATCH
    with pytest.raises(AttributeError):
        r.status = "confirmed"
    with pytest.raises(TypeError):
        r.evidence["registration_id"] = "match"
    with pytest.raises(TypeError):
        r.evidence["name"]["score"] = 0
    with pytest.raises(AttributeError):
        r.evidence["notes"].append("edited")
    assert r.status == "unconfirmed"


def test_result_dict_is_plain_json(results):
    d = results[("REG-001", "VEN-001")].to_dict()
    assert d["status"] == "unconfirmed"
    assert isinstance(d["evidence"]["notes"], list)
    assert json.loads(json.dumps(d)) == d


# CLI


def test_cli_output(capsys):
    assert main([str(DATA), "--hide-no-match"]) == 0
    out = capsys.readouterr().out
    assert "REG-001 <> VEN-001  score=79.9  needs review  [unconfirmed]" in out
    assert "REG-004 <> REG-005" not in out
    assert "do not establish" in out


def test_cli_shows_vetoed_pairs_without_the_flag(capsys):
    assert main([str(DATA)]) == 0
    out = capsys.readouterr().out
    assert "REG-004 <> REG-005  score=30.0  no match" in out
    assert "registration IDs conflict" in out


def test_cli_json(capsys):
    assert main([str(DATA), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["skipped_blocks"] == []
    first = output["matches"][0]
    assert set(first) == {"left_id", "right_id", "score", "label", "evidence", "status"}
    assert (first["left_id"], first["right_id"]) == ("REG-002", "VEN-002")
    assert first["score"] == 100.0
    assert first["status"] == "unconfirmed"
    assert set(first["evidence"]) == {
        "name",
        "registration_id",
        "same_jurisdiction",
        "cross_script",
        "notes",
    }
    assert len(output["matches"]) == 14


def test_cli_reports_skipped_blocks(tmp_path, capsys):
    path = tmp_path / "records.json"
    write_records(
        path, [{"record_id": r.record_id, "name": r.name} for r in token_block(51)]
    )
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "warning: 1 block(s) were too large" in out
    assert "name token block 'pelham' has 51 records (limit 50)" in out
    assert main([str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skipped_blocks"][0]["size"] == 51


def test_cli_reports_bad_input_without_a_traceback(tmp_path, capsys):
    path = tmp_path / "records.json"
    write_records(path, [{"record_id": "A", "name": None}])
    assert main([str(path)]) == 2
    assert "error:" in capsys.readouterr().err
    config = tmp_path / "config.json"
    config.write_text('{"needs_reveiw": 60}', encoding="utf-8")
    assert main([str(DATA), "--config", str(config)]) == 2
    assert "needs_reveiw" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.json")]) == 2
    assert "error:" in capsys.readouterr().err
