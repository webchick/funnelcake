from __future__ import annotations

import json
import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
