
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schema.json"
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class TestEvidenceSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)

        Draft202012Validator.check_schema(cls.schema)

        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker()
        )

    def assert_record_valid(self, record):
        errors = sorted(
            cls_errors(self.validator, record),
            key=lambda error: list(error.absolute_path)
        )

        if errors:
            messages = "\n".join(
                f"{list(error.absolute_path)}: {error.message}"
                for error in errors
            )
            self.fail(f"Record should be valid:\n{messages}")

    def assert_record_invalid(self, record):
        errors = list(self.validator.iter_errors(record))

        self.assertTrue(
            errors,
            "Expected validation to fail, but the record was accepted."
        )

    def load_example(self, filename):
        return load_json(EXAMPLES_DIR / filename)

    def test_schema_is_valid(self):
        Draft202012Validator.check_schema(self.schema)

    def test_all_five_examples_are_valid(self):
        example_files = sorted(EXAMPLES_DIR.glob("*.json"))

        self.assertEqual(
            len(example_files),
            5,
            "Expected exactly five example JSON files."
        )

        for path in example_files:
            with self.subTest(example=path.name):
                self.assert_record_valid(load_json(path))

    def test_missing_required_field_is_rejected(self):
        record = self.load_example("01_official_record.json")
        del record["evidence_id"]

        self.assert_record_invalid(record)

    def test_missing_claim_reference_is_rejected(self):
        record = self.load_example("01_official_record.json")
        del record["claim_reference"]

        self.assert_record_invalid(record)

    def test_empty_claim_reference_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["claim_reference"] = ""

        self.assert_record_invalid(record)

    def test_invalid_source_classification_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["source_classification"] = ["unverified"]

        self.assert_record_invalid(record)

    def test_invalid_publication_date_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["publication_date"] = "15-01-2026"

        self.assert_record_invalid(record)

    def test_invalid_evidence_status_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["evidence_status"] = "confirmed"

        self.assert_record_invalid(record)

    def test_unknown_property_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["extra_field"] = "not allowed"

        self.assert_record_invalid(record)

    def test_duplicate_classifications_are_rejected(self):
        record = self.load_example("01_official_record.json")
        record["source_classification"] = ["primary", "primary"]

        self.assert_record_invalid(record)

    def test_invalid_url_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["url"] = "not-a-valid-url"

        self.assert_record_invalid(record)

    def test_unavailable_evidence_requires_limitation(self):
        record = self.load_example("05_unavailable_source.json")
        record["limitations"] = []

        self.assert_record_invalid(record)

    def test_disputed_evidence_requires_limitation(self):
        record = self.load_example("04_disputed_evidence.json")
        record["limitations"] = []

        self.assert_record_invalid(record)

    def test_outdated_evidence_requires_limitation(self):
        record = self.load_example("01_official_record.json")
        record["evidence_status"] = "outdated"
        record["limitations"] = []

        self.assert_record_invalid(record)

    def test_null_access_date_is_allowed_when_not_accessed(self):
        record = self.load_example("05_unavailable_source.json")

        self.assert_record_valid(record)
    
    
    def test_url_without_hostname_is_rejected(self):
        record = self.load_example("01_official_record.json")
        record["url"] = "https://"
    
        self.assert_record_invalid(record)
    

def cls_errors(validator, record):
    return validator.iter_errors(record)


if __name__ == "__main__":
    unittest.main(verbosity=2)
