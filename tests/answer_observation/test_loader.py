from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from funnelcake_answer_observation import (
    load_observation_set,
    import_observation_set_sqlite,
    validate_observation_file,
    write_observation_set,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class ObservationLoaderTest(unittest.TestCase):
    def test_loads_raw_collected_aliases(self) -> None:
        observation_set = load_observation_set(REPO_ROOT / "fixtures/geo/drupal-raw-collected.json")
        observation = observation_set.observations[0]

        self.assertEqual(observation_set.subject_entity, "Drupal")
        self.assertEqual(observation_set.subject_product_id, "drupal")
        self.assertEqual(observation.prompt_id, "cms-enterprise-raw-001")
        self.assertEqual(observation.run_id, "raw-run-001")
        self.assertEqual(observation.model_version, "2026-08")
        self.assertTrue(observation.search_enabled)
        self.assertEqual(observation.run_number, 1)
        self.assertEqual(observation.repetition, 1)
        self.assertIn("university multisite program", observation.raw_answer)
        self.assertEqual(observation.raw_request["search"], True)
        self.assertEqual(observation.raw_response["provider_payload_fixture"], True)
        self.assertEqual(observation.mentions[0].product_id, "drupal")
        self.assertEqual(observation.mentions[0].rank, 1)
        self.assertEqual(observation.retrieved_sources[0].product_id, "drupal")
        self.assertEqual(
            observation.claims[0].source_urls,
            ("https://www.drupal.org/case-study/higher-education",),
        )

    def test_writes_canonical_observation_json(self) -> None:
        observation_set = load_observation_set(REPO_ROOT / "fixtures/geo/drupal-raw-collected.json")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = write_observation_set(
                observation_set,
                Path(temp_dir) / "normalized.json",
            )
            normalized = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(normalized["subject_entity"], "Drupal")
        self.assertNotIn("subjectEntity", normalized)
        self.assertEqual(normalized["observations"][0]["prompt_id"], "cms-enterprise-raw-001")
        self.assertNotIn("promptId", normalized["observations"][0])
        self.assertEqual(normalized["observations"][0]["model_version"], "2026-08")
        self.assertNotIn("modelVersion", normalized["observations"][0])
        self.assertEqual(normalized["observations"][0]["retrieved_sources"][0]["product_id"], "drupal")
        self.assertEqual(
            normalized["observations"][0]["claims"][0]["source_urls"],
            ["https://www.drupal.org/case-study/higher-education"],
        )

    def test_validation_reports_evidence_quality_warnings(self) -> None:
        record = {
            "id": "warning-sample",
            "subject_entity": "Drupal",
            "prompts": [
                {
                    "id": "unused-prompt",
                    "prompt": "Unused prompt?",
                }
            ],
            "products": [
                {
                    "id": "drupal",
                    "name": "Drupal",
                }
            ],
            "observations": [
                {
                    "id": "warn-001",
                    "prompt_id": "missing-prompt",
                    "prompt": "What CMS should I use?",
                    "raw_answer": "",
                    "search_enabled": True,
                    "mentions": [
                        {
                            "entity": "ExampleCMS",
                            "product_id": "examplecms",
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "warnings.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            report = validate_observation_file(path)

        self.assertTrue(report.valid)
        self.assertIn("observation references prompt_id not in prompt registry: missing-prompt", report.warnings)
        self.assertIn("prompt has no observations: unused-prompt", report.warnings)
        self.assertIn("observation warn-001 succeeded but raw_answer is empty", report.warnings)
        self.assertIn("observation warn-001 has no provider or engine", report.warnings)
        self.assertIn("observation warn-001 has no model", report.warnings)
        self.assertIn("observation warn-001 has no timestamp", report.warnings)
        self.assertIn("observation warn-001 has no citations", report.warnings)
        self.assertIn("observation warn-001 has search_enabled=true but no retrieved_sources", report.warnings)
        self.assertIn(
            "observation warn-001 references product_id not in product registry: examplecms",
            report.warnings,
        )

    def test_validation_reports_hard_load_errors(self) -> None:
        report = validate_observation_file(REPO_ROOT / "fixtures/geo/does-not-exist.json")

        self.assertFalse(report.valid)
        self.assertEqual(report.observation_count, 0)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("No such file or directory", report.errors[0])

    def test_imports_observation_set_to_sqlite(self) -> None:
        observation_set = load_observation_set(REPO_ROOT / "fixtures/geo/drupal-raw-collected.json")

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "funnelcake.db"
            result = import_observation_set_sqlite(observation_set, db_path)
            with sqlite3.connect(db_path) as connection:
                run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                observation_count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
                citation_count = connection.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
                retrieved_count = connection.execute("SELECT COUNT(*) FROM retrieved_sources").fetchone()[0]
                mention_count = connection.execute("SELECT COUNT(*) FROM product_mentions").fetchone()[0]
                first_mention = connection.execute(
                    """
                    SELECT product_id, recommended, recommendation_position
                    FROM product_mentions
                    WHERE observation_id = 'raw-obs-001'
                    ORDER BY id
                    LIMIT 1
                    """
                ).fetchone()

        self.assertEqual(result["run_id"], "drupal-raw-collected-sample")
        self.assertEqual(run_count, 1)
        self.assertEqual(observation_count, 1)
        self.assertEqual(citation_count, 1)
        self.assertEqual(retrieved_count, 2)
        self.assertEqual(mention_count, 2)
        self.assertEqual(first_mention, ("drupal", 1, 1))


if __name__ == "__main__":
    unittest.main()
