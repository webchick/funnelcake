from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH = ":".join(
    [
        "apps/cli/src",
        "packages/platform-profile/src",
        "packages/signal-mining/src",
        "packages/intent-extraction/src",
        "packages/answer-observation/src",
        "packages/benchmark-builder/src",
        "packages/discover-eval/src",
        "packages/reporting/src",
        "shared",
    ]
)


class GeoCliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = PYTHONPATH
        return subprocess.run(
            [sys.executable, "-m", "funnelcake_cli", *args],
            check=False,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_geo_validate_json_succeeds(self) -> None:
        result = self.run_cli(
            "geo",
            "validate",
            "fixtures/geo/drupal-raw-collected.json",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["observation_set_id"], "drupal-raw-collected-sample")
        self.assertEqual(report["observation_count"], 1)
        self.assertEqual(report["errors"], [])

    def test_geo_validate_missing_file_exits_nonzero(self) -> None:
        result = self.run_cli("geo", "validate", "fixtures/geo/missing.json")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Observation validation failed", result.stdout)
        self.assertIn("No such file or directory", result.stdout)

    def test_validate_observations_alias_json_succeeds(self) -> None:
        result = self.run_cli(
            "validate-observations",
            "fixtures/geo/drupal-raw-collected.json",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["product_count"], 2)

    def test_geo_summary_json_succeeds(self) -> None:
        result = self.run_cli(
            "geo",
            "summary",
            "fixtures/geo/drupal-raw-collected.json",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["observation_set_id"], "drupal-raw-collected-sample")
        self.assertEqual(summary["subject_visibility"]["recommended_count"], 1)

    def test_geo_normalize_writes_canonical_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "normalized.json"
            result = self.run_cli(
                "geo",
                "normalize",
                "fixtures/geo/drupal-raw-collected.json",
                "--out",
                str(output_path),
            )
            normalized = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("normalized_observation_set=drupal-raw-collected-sample", result.stdout)
        self.assertEqual(normalized["subject_entity"], "Drupal")
        self.assertNotIn("subjectEntity", normalized)
        self.assertEqual(normalized["observations"][0]["prompt_id"], "cms-enterprise-raw-001")
        self.assertNotIn("promptId", normalized["observations"][0])

    def test_geo_import_sqlite_writes_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "funnelcake.db"
            result = self.run_cli(
                "geo",
                "import-sqlite",
                "fixtures/geo/drupal-raw-collected.json",
                "--db",
                str(db_path),
            )
            with sqlite3.connect(db_path) as connection:
                observation_count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
                mention_count = connection.execute("SELECT COUNT(*) FROM product_mentions").fetchone()[0]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("imported_observation_set=drupal-raw-collected-sample", result.stdout)
        self.assertEqual(observation_count, 1)
        self.assertEqual(mention_count, 2)

    def test_geo_extract_products_writes_analyzable_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "extracted.json"
            result = self.run_cli(
                "geo",
                "extract-products",
                "fixtures/geo/drupal-unextracted.json",
                "--out",
                str(output_path),
            )
            summary_result = self.run_cli(
                "geo",
                "summary",
                str(output_path),
                "--json",
            )
            summary = json.loads(summary_result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary_result.returncode, 0, summary_result.stderr)
        self.assertIn("extracted_observation_set=drupal-unextracted-sample", result.stdout)
        self.assertEqual(summary["subject_visibility"]["mention_count"], 1)
        self.assertEqual(summary["subject_visibility"]["recommended_count"], 1)


if __name__ == "__main__":
    unittest.main()
