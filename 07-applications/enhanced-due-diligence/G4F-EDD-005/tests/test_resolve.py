import json
from pathlib import Path

import pytest

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

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic_companies.json"


@pytest.fixture(scope="module")
def results():
    return {(r.left_id, r.right_id): r for r in resolve(load_records(DATA))}


# True matches


def test_suffix_and_punctuation_variants_match(results):
    r = results[("REG-001", "VEN-001")]
    assert r.label == LIKELY_MATCH
    assert r.evidence["name"]["score"] == 100


def test_transliteration_with_matching_id(results):
    r = results[("REG-002", "VEN-002")]
    assert r.label == LIKELY_MATCH
    assert r.evidence["registration_id"] == "match"


def test_alias_hit_is_reported(results):
    r = results[("REG-003", "VEN-003")]
    assert r.label == LIKELY_MATCH
    assert r.evidence["name"]["alias_used"] is True
    assert any("alias" in note for note in r.evidence["notes"])


def test_abbreviations_with_matching_id(results):
    assert results[("REG-006", "VEN-006")].label == LIKELY_MATCH


def test_partial_name_goes_to_review_not_match(results):
    assert results[("REG-001", "NEWS-001")].label == NEEDS_REVIEW


# False matches


def test_same_name_conflicting_ids_is_vetoed(results):
    r = results[("REG-004", "REG-005")]
    assert r.evidence["name"]["score"] == 100
    assert r.evidence["registration_id"] == "conflict"
    assert r.score <= MatchConfig().id_conflict_cap
    assert r.label == NO_MATCH


def test_same_name_different_jurisdiction_is_not_a_likely_match(results):
    r = results[("REG-004", "VEN-004")]
    assert r.evidence["same_jurisdiction"] is False
    assert r.label != LIKELY_MATCH


def test_shared_first_word_only_is_no_match(results):
    assert results[("REG-006", "VEN-007")].label == NO_MATCH


def test_id_conflict_cap_holds_even_with_everything_else_agreeing():
    a = Record(
        "A",
        "Kestrel Paper Mills Ltd",
        registration_id="SYN-1",
        jurisdiction="GB",
        city="York",
    )
    b = Record(
        "B",
        "Kestrel Paper Mills Ltd",
        registration_id="SYN-2",
        jurisdiction="GB",
        city="York",
    )
    r = score_pair(a, b)
    assert r.score == MatchConfig().id_conflict_cap
    assert r.label == NO_MATCH


def test_ids_in_different_jurisdictions_are_not_compared():
    a = Record(
        "A", "Kestrel Paper Mills Ltd", registration_id="SYN-1", jurisdiction="GB"
    )
    b = Record(
        "B", "Kestrel Paper Mills Ltd", registration_id="SYN-1", jurisdiction="IE"
    )
    assert score_pair(a, b).evidence["registration_id"] == "not comparable"


# Candidate generation


def test_blocking_skips_unrelated_records():
    records = load_records(DATA)
    pairs = {(a.record_id, b.record_id) for a, b in generate_candidates(records)}
    assert ("REG-001", "VEN-001") in pairs
    assert ("REG-001", "REG-003") not in pairs
    # "Trading" alone is too common to block on, so Northgate pairs come from "northgate".
    assert ("REG-004", "VEN-004") in pairs


def test_shared_identifier_is_a_blocking_key():
    a = Record("A", "Ashgrove Dairy Ltd", registration_id="SYN-GB-1", jurisdiction="GB")
    b = Record("B", "AD Foods Ltd", registration_id="syn gb 1", jurisdiction="GB")
    assert len(generate_candidates([a, b])) == 1


def test_oversized_blocks_are_skipped():
    records = [Record(str(i), f"Pelham Widgets {i}") for i in range(5)]
    assert len(generate_candidates(records, MatchConfig(max_block_size=10))) == 10
    assert generate_candidates(records, MatchConfig(max_block_size=4)) == []


# Thresholds and review


def test_thresholds_are_configurable(results):
    r = results[("VEN-005", "NEWS-002")]
    assert r.label == NEEDS_REVIEW
    a, b = (
        rec for rec in load_records(DATA) if rec.record_id in ("VEN-005", "NEWS-002")
    )
    assert score_pair(a, b, MatchConfig(likely_match=70)).label == LIKELY_MATCH
    assert (
        score_pair(a, b, MatchConfig(likely_match=95, needs_review=90)).label
        == NO_MATCH
    )


def test_config_loads_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"likely_match": 90, "needs_review": 60}))
    config = MatchConfig.from_file(path)
    assert (config.likely_match, config.needs_review) == (90, 60)


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        MatchConfig(likely_match=50, needs_review=70)


def test_results_are_unconfirmed_until_a_reviewer_decides(results):
    assert all(r.status == "unconfirmed" for r in results.values())
    decision = record_decision(
        results[("REG-001", "VEN-001")], reviewer="analyst-1", accepted=True
    )
    assert decision["status"] == "confirmed"
    assert decision["score"] == results[("REG-001", "VEN-001")].score
    with pytest.raises(ValueError):
        record_decision(results[("REG-001", "VEN-001")], reviewer="", accepted=True)


def test_cli_output(capsys):
    assert main([str(DATA), "--hide-no-match"]) == 0
    out = capsys.readouterr().out
    assert "REG-001 <> VEN-001" in out
    assert "REG-004 <> REG-005" not in out
    assert "do not establish" in out


def test_cli_json(capsys):
    main([str(DATA), "--json"])
    rows = json.loads(capsys.readouterr().out)
    expected = {"left_id", "right_id", "score", "label", "evidence", "status"}
    assert expected <= rows[0].keys()
