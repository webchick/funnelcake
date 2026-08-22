from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from funnelcake_collectors import (
    CollectorCapability,
    Experiment,
    format_observations,
    get_collector,
    load_observations,
    observations_to_dict,
    write_observations,
)
from funnelcake_shared import DessertStage, ProductFunnelStage


REPO_ROOT = Path(__file__).resolve().parents[1]


class CollectorTests(unittest.TestCase):
    def test_native_answer_observation_collector_normalizes_visibility(self) -> None:
        collector = get_collector("answer-observation")
        observations = collector.collect(
            Experiment(
                id="geo-drupal",
                capability=CollectorCapability.ANSWER_OBSERVATION,
                input_path=str(REPO_ROOT / "fixtures/geo/drupal-raw-collected.json"),
            )
        )

        self.assertTrue(observations)
        self.assertTrue(any(observation.signal == "agent_visibility" for observation in observations))
        self.assertTrue(any(observation.signal == "agent_selection" for observation in observations))
        self.assertEqual(observations[0].journey_stage, ProductFunnelStage.INVESTIGATE)
        self.assertEqual(observations[0].dessert_stage, DessertStage.DISCOVER)
        self.assertEqual(observations[0].provenance.collector, "native.answer_observation")

    def test_mcp_inspector_collector_preserves_raw_artifact(self) -> None:
        collector = get_collector("mcp-inspector")
        observations = collector.collect(
            Experiment(
                id="mcp-auth-check",
                capability=CollectorCapability.MCP_INSPECTION,
                input_path=str(REPO_ROOT / "fixtures/collectors/mcp-inspector-auth-failed.json"),
            )
        )

        auth = next(observation for observation in observations if observation.signal == "mcp_authentication")
        self.assertEqual(auth.journey_stage, ProductFunnelStage.LAUNCH)
        self.assertEqual(auth.dessert_stage, DessertStage.SETUP)
        self.assertFalse(auth.success)
        self.assertEqual(auth.value["error"], "OAuth authorization required")
        self.assertEqual(auth.evidence[0].content["tools_discovered"], 14)
        self.assertEqual(auth.provenance.raw_artifact_id, "mcp-auth-check:raw")

    def test_mcp_inspector_collector_understands_tools_list_json(self) -> None:
        collector = get_collector("mcp-inspector")
        observations = collector.collect(
            Experiment(
                id="mcp-tools-list",
                capability=CollectorCapability.MCP_INSPECTION,
                input_path=str(REPO_ROOT / "fixtures/collectors/mcp-inspector-tools-list.json"),
            )
        )

        tools = next(observation for observation in observations if observation.signal == "mcp_tool_discovery")
        self.assertTrue(tools.success)
        self.assertEqual(tools.value["tools_discovered"], 2)

    def test_promptfoo_collector_normalizes_eval_results(self) -> None:
        collector = get_collector("promptfoo")
        observations = collector.collect(
            Experiment(
                id="promptfoo-eval",
                capability=CollectorCapability.AGENT_EVALUATION,
                input_path=str(REPO_ROOT / "fixtures/collectors/promptfoo-results.json"),
            )
        )

        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0].provenance.collector, "external.promptfoo")
        self.assertEqual(observations[0].journey_stage, ProductFunnelStage.INITIAL_VALUE)
        self.assertEqual(observations[0].dessert_stage, DessertStage.EXECUTE)
        self.assertTrue(observations[0].success)
        self.assertFalse(observations[1].success)
        self.assertEqual(observations[1].value["score"], 0.31)

    def test_promptfoo_collector_normalizes_current_export_shape(self) -> None:
        collector = get_collector("promptfoo")
        observations = collector.collect(
            Experiment(
                id="promptfoo-export",
                capability=CollectorCapability.AGENT_EVALUATION,
                input_path=str(REPO_ROOT / "fixtures/collectors/promptfoo-export-results.json"),
            )
        )

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].actor, "echo")
        self.assertTrue(observations[0].success)
        self.assertEqual(observations[0].value["reason"], "All assertions passed")

    def test_observation_io_round_trips_normalized_contract(self) -> None:
        collector = get_collector("mcp-inspector")
        observations = collector.collect(
            Experiment(
                id="mcp-auth-check",
                capability=CollectorCapability.MCP_INSPECTION,
                input_path=str(REPO_ROOT / "fixtures/collectors/mcp-inspector-auth-failed.json"),
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_observations(observations, Path(temp_dir) / "observations.json")
            loaded = load_observations(path)

        self.assertEqual(loaded, observations)
        payload = observations_to_dict(loaded)
        self.assertEqual(payload["observations"][0]["provenance"]["collector"], "external.mcp_inspector")
        self.assertIn("normalized_observations=2", format_observations(loaded))


if __name__ == "__main__":
    unittest.main()
