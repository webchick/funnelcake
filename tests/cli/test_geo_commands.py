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
        "packages/telemetry/src",
        "packages/collectors/src",
        "packages/reporting/src",
        "shared",
    ]
)


class GeoCliTest(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        extra_env: dict[str, str | None] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = PYTHONPATH
        for key, value in (extra_env or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
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

    def test_geo_run_fixture_feeds_extract_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw.json"
            extracted_path = Path(temp_dir) / "extracted.json"
            run_result = self.run_cli(
                "geo",
                "run-fixture",
                "fixtures/geo/drupal-fixture-provider.json",
                "--out",
                str(raw_path),
            )
            extract_result = self.run_cli(
                "geo",
                "extract-products",
                str(raw_path),
                "--out",
                str(extracted_path),
            )
            summary_result = self.run_cli(
                "geo",
                "summary",
                str(extracted_path),
                "--json",
            )
            summary = json.loads(summary_result.stdout)

        self.assertEqual(run_result.returncode, 0, run_result.stderr)
        self.assertEqual(extract_result.returncode, 0, extract_result.stderr)
        self.assertEqual(summary_result.returncode, 0, summary_result.stderr)
        self.assertIn("run_observation_set=drupal-fixture-provider-run", run_result.stdout)
        self.assertEqual(summary["response_count"], 2)
        self.assertEqual(summary["subject_visibility"]["mention_count"], 2)

    def test_geo_run_yaml_corpus_feeds_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "run.json"
            run_result = self.run_cli(
                "geo",
                "run",
                "fixtures/geo/drupal-prompts.yaml",
                "--providers",
                "fixture",
                "--repeat",
                "2",
                "--out",
                str(output_path),
            )
            report_result = self.run_cli(
                "geo",
                "report",
                str(output_path),
                "--json",
            )
            report = json.loads(report_result.stdout)

        self.assertEqual(run_result.returncode, 0, run_result.stderr)
        self.assertEqual(report_result.returncode, 0, report_result.stderr)
        self.assertIn("run_observation_set=drupal-fixture-corpus-run", run_result.stdout)
        self.assertIn("observations=2", run_result.stdout)
        self.assertIn("failed=0", run_result.stdout)
        self.assertEqual(report["response_count"], 2)
        self.assertEqual(report["subject_visibility"]["recommended_count"], 2)

    def test_geo_run_openai_requires_api_key(self) -> None:
        result = self.run_cli(
            "geo",
            "run-openai",
            "fixtures/geo/drupal-openai-provider.json",
            "--out",
            "/tmp/unused-openai-observations.json",
            extra_env={"OPENAI_API_KEY": None},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OPENAI_API_KEY is required", result.stderr)

    def test_geo_run_gemini_requires_api_key(self) -> None:
        result = self.run_cli(
            "geo",
            "run-gemini",
            "fixtures/geo/drupal-gemini-provider.json",
            "--out",
            "/tmp/unused-gemini-observations.json",
            extra_env={"GEMINI_API_KEY": None},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GEMINI_API_KEY is required", result.stderr)

    def test_geo_run_perplexity_requires_api_key(self) -> None:
        result = self.run_cli(
            "geo",
            "run-perplexity",
            "fixtures/geo/drupal-perplexity-provider.json",
            "--out",
            "/tmp/unused-perplexity-observations.json",
            extra_env={"PERPLEXITY_API_KEY": None},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PERPLEXITY_API_KEY is required", result.stderr)

    def test_export_otlp_writes_json_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "otlp.json"
            result = self.run_cli(
                "export-otlp",
                "fixtures/runs/setup-auth-docs.json",
                "--out",
                str(output_path),
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("exported_trial=FC-0001", result.stdout)
        self.assertEqual(payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"], "4bf92f3577b34da6a3ce929d0e0e0001")

    def test_send_otlp_rejects_invalid_header_syntax(self) -> None:
        result = self.run_cli(
            "send-otlp",
            "fixtures/runs/setup-auth-docs.json",
            "--endpoint",
            "http://collector.example/v1/traces",
            "--header",
            "invalid",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("header must use", result.stderr)

    def test_telemetry_normalize_and_inspect_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "normalized.json"
            current_output_path = Path(temp_dir) / "normalized-current.json"
            baseline_snapshot_path = Path(temp_dir) / "baseline-snapshot.json"
            current_snapshot_path = Path(temp_dir) / "current-snapshot.json"
            normalize_result = self.run_cli(
                "telemetry",
                "normalize",
                "fixtures/telemetry/posthog-ish-events.json",
                "--mapping",
                "fixtures/telemetry/posthog-ish-mapping.yaml",
                "--out",
                str(output_path),
            )
            current_normalize_result = self.run_cli(
                "telemetry",
                "normalize",
                "fixtures/telemetry/posthog-ish-events-current.json",
                "--mapping",
                "fixtures/telemetry/posthog-ish-mapping.yaml",
                "--out",
                str(current_output_path),
            )
            inspect_result = self.run_cli(
                "telemetry",
                "inspect",
                str(output_path),
            )
            snapshot_result = self.run_cli(
                "filling",
                "snapshot",
                str(output_path),
                "--config",
                "fixtures/telemetry/filling-config.yaml",
            )
            baseline_save_result = self.run_cli(
                "filling",
                "snapshot",
                str(output_path),
                "--config",
                "fixtures/telemetry/filling-config.yaml",
                "--out",
                str(baseline_snapshot_path),
            )
            current_save_result = self.run_cli(
                "filling",
                "snapshot",
                str(current_output_path),
                "--config",
                "fixtures/telemetry/filling-config-current.yaml",
                "--out",
                str(current_snapshot_path),
            )
            compare_result = self.run_cli(
                "filling",
                "compare",
                str(baseline_snapshot_path),
                str(current_snapshot_path),
            )
            prometheus_path = Path(temp_dir) / "filling.prom"
            prometheus_result = self.run_cli(
                "filling",
                "export-prometheus",
                str(current_snapshot_path),
                "--out",
                str(prometheus_path),
            )
            dashboard_result = self.run_cli(
                "dashboard-summary",
                "--filling-snapshot",
                str(current_snapshot_path),
                "--compare-to",
                str(baseline_snapshot_path),
                "--runs-dir",
                str(Path(temp_dir) / "missing-runs"),
            )
            baseline_snapshot_exists = baseline_snapshot_path.exists()
            current_snapshot_exists = current_snapshot_path.exists()
            prometheus_metrics = prometheus_path.read_text(encoding="utf-8") if prometheus_path.exists() else ""

        self.assertEqual(normalize_result.returncode, 0, normalize_result.stderr)
        self.assertIn("normalized_events=5", normalize_result.stdout)
        self.assertEqual(current_normalize_result.returncode, 0, current_normalize_result.stderr)
        self.assertIn("normalized_events=7", current_normalize_result.stdout)
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
        self.assertIn("initial_value", inspect_result.stdout)
        self.assertIn("next_value", inspect_result.stdout)
        self.assertEqual(snapshot_result.returncode, 0, snapshot_result.stderr)
        self.assertIn("fit: 1000 estimated", snapshot_result.stdout)
        self.assertIn("land->launch", snapshot_result.stdout)
        self.assertIn("status=incompatible_population", snapshot_result.stdout)
        self.assertEqual(baseline_save_result.returncode, 0, baseline_save_result.stderr)
        self.assertTrue(baseline_snapshot_exists)
        self.assertEqual(current_save_result.returncode, 0, current_save_result.stderr)
        self.assertTrue(current_snapshot_exists)
        self.assertEqual(compare_result.returncode, 0, compare_result.stderr)
        self.assertIn("fit->investigate", compare_result.stdout)
        self.assertIn("delta=+2.0pp", compare_result.stdout)
        self.assertIn("launch->initial_value", compare_result.stdout)
        self.assertIn("delta=-50.0pp", compare_result.stdout)
        self.assertIn("no delta for status incompatible_population", compare_result.stdout)
        self.assertEqual(prometheus_result.returncode, 0, prometheus_result.stderr)
        self.assertIn("prometheus_metrics=", prometheus_result.stdout)
        self.assertIn("funnelcake_filling_stage_count", prometheus_metrics)
        self.assertIn('funnelcake_filling_transition_rate{transition="launch_to_initial_value"', prometheus_metrics)
        self.assertEqual(dashboard_result.returncode, 0, dashboard_result.stderr)
        self.assertIn("Funnelcake product dashboard", dashboard_result.stdout)
        self.assertIn("FILLING snapshot", dashboard_result.stdout)
        self.assertIn("FILLING comparison", dashboard_result.stdout)
        self.assertIn("No DESSERT diagnostic runs found", dashboard_result.stdout)

    def test_collect_run_normalizes_mcp_inspector_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "mcp-observations.json"
            result = self.run_cli(
                "collect",
                "run",
                "--collector",
                "mcp-inspector",
                "fixtures/collectors/mcp-inspector-auth-failed.json",
                "--out",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("normalized_observations=2", result.stdout)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["provenance"]["collector"], "external.mcp_inspector")
            self.assertEqual(payload["observations"][0]["journey_stage"], "launch")

    def test_collect_inspect_reads_normalized_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "geo-observations.json"
            run_result = self.run_cli(
                "collect",
                "run",
                "--collector",
                "answer-observation",
                "fixtures/geo/drupal-raw-collected.json",
                "--out",
                str(output_path),
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)

            inspect_result = self.run_cli("collect", "inspect", str(output_path), "--json")

            self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
            payload = json.loads(inspect_result.stdout)
            self.assertTrue(payload["observations"])
            self.assertEqual(payload["observations"][0]["provenance"]["collector"], "native.answer_observation")

    def test_collect_run_normalizes_promptfoo_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "promptfoo-observations.json"
            result = self.run_cli(
                "collect",
                "run",
                "--collector",
                "promptfoo",
                "fixtures/collectors/promptfoo-results.json",
                "--out",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("normalized_observations=2", result.stdout)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["provenance"]["collector"], "external.promptfoo")
            self.assertEqual(payload["observations"][0]["signal"], "agent_eval_result")

    def test_collect_mcp_inspector_runs_command_and_writes_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_command = Path(temp_dir) / "fake-mcp-inspector"
            fake_command.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "print(json.dumps({'result': {'tools': [{'name': 'one'}, {'name': 'two'}]}}))",
                    ]
                ),
                encoding="utf-8",
            )
            fake_command.chmod(0o755)
            raw_output_path = Path(temp_dir) / "mcp-raw.json"
            output_path = Path(temp_dir) / "mcp-observations.json"

            result = self.run_cli(
                "collect",
                "mcp-inspector",
                "https://example.com/mcp",
                "--command",
                str(fake_command),
                "--raw-out",
                str(raw_output_path),
                "--out",
                str(output_path),
            )
            raw_output_exists = raw_output_path.exists()
            payload = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(raw_output_exists)
        self.assertIn("normalized_observations=2", result.stdout)
        self.assertEqual(payload["observations"][0]["provenance"]["collector"], "external.mcp_inspector")
        self.assertTrue(payload["observations"][0]["success"])
        self.assertEqual(payload["observations"][1]["value"]["tools_discovered"], 2)

    def test_collect_promptfoo_runs_command_and_writes_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_command = Path(temp_dir) / "fake-promptfoo"
            fake_command.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json, pathlib, sys",
                        "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])",
                        "output.parent.mkdir(parents=True, exist_ok=True)",
                        "output.write_text(json.dumps({'version': 3, 'results': {'outputs': [{'success': True, 'score': 0.9}]}}))",
                    ]
                ),
                encoding="utf-8",
            )
            fake_command.chmod(0o755)
            raw_output_path = Path(temp_dir) / "promptfoo-raw.json"
            output_path = Path(temp_dir) / "promptfoo-observations.json"

            result = self.run_cli(
                "collect",
                "promptfoo",
                "fixtures/collectors/promptfooconfig.yaml",
                "--command",
                str(fake_command),
                "--raw-out",
                str(raw_output_path),
                "--out",
                str(output_path),
            )
            raw_output_exists = raw_output_path.exists()
            payload = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(raw_output_exists)
        self.assertIn("normalized_observations=1", result.stdout)
        self.assertEqual(payload["observations"][0]["provenance"]["collector"], "external.promptfoo")
        self.assertEqual(payload["observations"][0]["journey_stage"], "initial_value")
        self.assertTrue(payload["observations"][0]["success"])


if __name__ == "__main__":
    unittest.main()
