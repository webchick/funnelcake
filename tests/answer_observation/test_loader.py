from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from funnelcake_answer_observation import (
    extract_product_mentions,
    load_observation_set,
    import_observation_set_sqlite,
    run_fixture_provider,
    run_openai_provider,
    run_perplexity_provider,
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

    def test_extracts_product_mentions_from_answer_text(self) -> None:
        observation_set = load_observation_set(REPO_ROOT / "fixtures/geo/drupal-unextracted.json")
        extracted = extract_product_mentions(observation_set)
        mentions = extracted.observations[0].mentions

        self.assertEqual([mention.product_id for mention in mentions], ["drupal", "wordpress"])
        self.assertEqual(mentions[0].role, "recommended")
        self.assertEqual(mentions[0].display_name, "Drupal")
        self.assertEqual(mentions[1].role, "mentioned")
        self.assertEqual(mentions[1].display_name, "WordPress")
        self.assertEqual(mentions[0].attributes["extracted_by"], "deterministic_product_alias")

    def test_runs_fixture_provider_to_raw_observations(self) -> None:
        observation_set = run_fixture_provider(REPO_ROOT / "fixtures/geo/drupal-fixture-provider.json")

        self.assertEqual(observation_set.id, "drupal-fixture-provider-run")
        self.assertEqual(len(observation_set.prompts), 2)
        self.assertEqual(len(observation_set.products), 3)
        self.assertEqual(len(observation_set.observations), 2)
        self.assertEqual(observation_set.observations[0].provider, "fixture")
        self.assertEqual(observation_set.observations[0].model, "fixture-answer-engine")
        self.assertEqual(observation_set.observations[0].raw_request["prompt_id"], "cms-enterprise-fixture-001")
        self.assertEqual(observation_set.observations[0].raw_response["answer_id"], "fixture-obs-001")
        self.assertEqual(observation_set.observations[0].mentions, ())

    def test_runs_openai_provider_with_mocked_response(self) -> None:
        response_body = {
            "created_at": 1787201400,
            "output_text": "Drupal is a strong fit for large university multisite needs.",
            "output": [
                {
                    "content": [
                        {
                            "annotations": [
                                {
                                    "url": "https://www.drupal.org/",
                                    "title": "Drupal",
                                }
                            ]
                        }
                    ]
                }
            ],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(response_body).encode("utf-8")

        with patch(
            "funnelcake_answer_observation.runner.request.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            observation_set = run_openai_provider(
                REPO_ROOT / "fixtures/geo/drupal-openai-provider.json",
                api_key="test-key",
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        observation = observation_set.observations[0]

        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "gpt-5.6")
        self.assertEqual(payload["tools"], [{"type": "web_search"}])
        self.assertFalse(payload["store"])
        self.assertEqual(observation.provider, "openai")
        self.assertEqual(observation.timestamp, "2026-08-20T04:50:00Z")
        self.assertEqual(observation.raw_answer, response_body["output_text"])
        self.assertEqual(observation.citations[0].url, "https://www.drupal.org/")

    def test_openai_provider_requires_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                run_openai_provider(REPO_ROOT / "fixtures/geo/drupal-openai-provider.json")

    def test_runs_perplexity_provider_with_mocked_response(self) -> None:
        response_body = {
            "id": "sonar-response-001",
            "model": "sonar-pro",
            "created": 1787201460,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Drupal is a strong fit for large university multisite needs.",
                    }
                }
            ],
            "citations": [
                "https://www.drupal.org/",
            ],
            "search_results": [
                {
                    "title": "Drupal",
                    "url": "https://www.drupal.org/",
                    "source": "web",
                }
            ],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(response_body).encode("utf-8")

        with patch(
            "funnelcake_answer_observation.runner.request.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            observation_set = run_perplexity_provider(
                REPO_ROOT / "fixtures/geo/drupal-perplexity-provider.json",
                api_key="test-key",
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        observation = observation_set.observations[0]

        self.assertEqual(request.full_url, "https://api.perplexity.ai/v1/sonar")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "sonar-pro")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(observation.provider, "perplexity")
        self.assertEqual(observation.timestamp, "2026-08-20T04:51:00Z")
        self.assertEqual(observation.raw_answer, response_body["choices"][0]["message"]["content"])
        self.assertEqual(observation.citations[0].url, "https://www.drupal.org/")
        self.assertEqual(observation.retrieved_sources[0].url, "https://www.drupal.org/")

    def test_perplexity_provider_requires_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "PERPLEXITY_API_KEY"):
                run_perplexity_provider(REPO_ROOT / "fixtures/geo/drupal-perplexity-provider.json")


if __name__ == "__main__":
    unittest.main()
