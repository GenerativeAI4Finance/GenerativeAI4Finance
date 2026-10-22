import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_dataset import generate_dataset  # noqa: E402


class TestSyntheticEDDDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset_schema = json.loads((ROOT / "schema/dataset.schema.json").read_text(encoding="utf-8"))
        cls.case_schema = json.loads((ROOT.parent / "G4F-EDD-001/schema.json").read_text(encoding="utf-8"))
        cls.dataset_validator = Draft202012Validator(cls.dataset_schema, format_checker=FormatChecker())
        cls.case_validator = Draft202012Validator(cls.case_schema, format_checker=FormatChecker())

    def test_checked_in_dataset_matches_regenerated_seed(self):
        checked_in = json.loads((ROOT / "data/edd_cases_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(checked_in, generate_dataset(seed=checked_in["seed"]))

    def test_same_seed_produces_identical_dataset(self):
        self.assertEqual(generate_dataset(91), generate_dataset(91))

    def test_different_seed_changes_dataset(self):
        self.assertNotEqual(generate_dataset(91), generate_dataset(92))

    def test_dataset_and_embedded_case_records_validate(self):
        dataset = json.loads((ROOT / "data/edd_cases_v1.json").read_text(encoding="utf-8"))
        self.dataset_validator.validate(dataset)
        self.assertEqual(dataset["case_count"], len(dataset["cases"]))
        for item in dataset["cases"]:
            with self.subTest(case_id=item["case_record"]["case_id"]):
                self.assertTrue(item["synthetic"])
                self.case_validator.validate(item["case_record"])

    def test_required_scenario_types_are_present(self):
        dataset = json.loads((ROOT / "data/edd_cases_v1.json").read_text(encoding="utf-8"))
        scenarios = {case["scenario"] for case in dataset["cases"]}
        self.assertEqual(scenarios, {
            "normal", "ambiguous_entity_match", "incomplete_records",
            "conflicting_claims", "stale_evidence",
        })

    def test_ids_are_unique_and_all_person_entities_are_synthetic(self):
        dataset = json.loads((ROOT / "data/edd_cases_v1.json").read_text(encoding="utf-8"))
        case_ids = [item["case_record"]["case_id"] for item in dataset["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for item in dataset["cases"]:
            self.assertTrue(item["subject_entity"]["synthetic"])
            self.assertTrue(all(person["synthetic"] for person in item["directors"]))
            self.assertTrue(all(sub["synthetic"] for sub in item["subsidiaries"]))
            person_ids = {person["person_id"] for person in item["directors"]}
            for shareholder in item["shareholders"]:
                if shareholder["owner_type"] == "individual":
                    self.assertIn(shareholder["owner_id"], person_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
