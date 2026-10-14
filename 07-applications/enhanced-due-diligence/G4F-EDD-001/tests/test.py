import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema.json"
EXAMPLES_DIR = ROOT / "examples"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class TestEDDCaseSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker()
        )

    def assert_case_valid(self, case):
        errors = sorted(
            self.validator.iter_errors(case),
            key=lambda error: list(map(str, error.absolute_path))
        )
        messages = [
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        self.assertEqual(errors, [], "Validation errors:\n" + "\n".join(messages))

    def test_both_fictional_examples_are_valid(self):
        for path in sorted(EXAMPLES_DIR.glob("*.json")):
            with self.subTest(example=path.name):
                self.assert_case_valid(load_json(path))

    def test_missing_required_field_is_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        del case["case_id"]
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any("case_id" in error.message for error in errors))

    def test_invalid_subject_type_is_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        case["subject_type"] = "unknown_subject"
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any(
            list(error.absolute_path) == ["subject_type"]
            for error in errors
        ))

    def test_confidence_above_one_is_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        case["confidence"] = 1.2
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any(
            list(error.absolute_path) == ["confidence"]
            for error in errors
        ))

    def test_invalid_date_is_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        case["review_date"] = "13-10-2026"
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any(
            list(error.absolute_path) == ["review_date"]
            for error in errors
        ))

    def test_unknown_property_is_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        case["unexpected_field"] = "not allowed"
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any(
            "unexpected_field" in error.message
            for error in errors
        ))

    def test_duplicate_risk_categories_are_rejected(self):
        case = load_json(EXAMPLES_DIR / "case_low_risk.json")
        case["risk_categories"] = ["ownership_opacity", "ownership_opacity"]
        errors = list(self.validator.iter_errors(case))
        self.assertTrue(any(
            list(error.absolute_path) == ["risk_categories"]
            for error in errors
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
