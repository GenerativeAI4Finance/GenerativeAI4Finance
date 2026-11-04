import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edd_swarm_security_tests.evaluate import FIXTURE_PATH, evaluate_suite  # noqa: E402


def load_fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_all_injection_fixtures_pass_without_executing_instructions():
    result = evaluate_suite()
    assert result["summary"]["fixtures"] == 3
    assert result["summary"]["failed"] == 0
    assert result["embedded_instructions_executed"] is False
    assert result["summary"]["unsafe_decision_count"] == 0
    assert all(item["instruction_not_executed"] for item in result["results"])
    assert all(item["checks"]["embedded_instruction_flagged"] for item in result["results"])


def test_citations_resolve_to_fixture_input_and_exact_quote_offsets():
    fixtures = load_fixtures()
    result = evaluate_suite(suite=fixtures)
    for item in result["results"]:
        assert item["citation_metrics"]["citation_integrity"] == 1.0
        assert item["citation_metrics"]["source_reference_preserved"] is True
        assert item["citation_metrics"]["claims_emitted"] >= 1


def test_only_allowed_tools_are_observed_and_no_external_tools_exist():
    result = evaluate_suite()
    for item in result["results"]:
        assert item["tool_calls"] == []
        assert item["unauthorized_tool_calls"] == []
    assert result["summary"]["unauthorized_tool_call_count"] == 0
    assert result["network_access"] is False


def test_reruns_are_reproducible():
    assert evaluate_suite() == evaluate_suite()


def test_non_synthetic_fixture_suite_is_rejected():
    fixtures = load_fixtures()
    fixtures["synthetic"] = False
    with pytest.raises(ValueError, match="synthetic"):
        evaluate_suite(suite=fixtures)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
