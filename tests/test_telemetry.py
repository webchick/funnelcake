from __future__ import annotations

import unittest
import tempfile

from funnelcake_shared import (
    FunnelTransitionStatus,
    MeasurementIntervalType,
    MeasurementWindow,
    PopulationDefinition,
    ProductFunnelStage,
)
from funnelcake_telemetry import (
    ProductFunnelConfig,
    build_filling_snapshot,
    compare_filling_snapshots,
    calculate_transition,
    derive_stage_attainments,
    filling_snapshot_to_prometheus,
    load_filling_snapshot,
    load_product_funnel_config,
    load_mapping,
    load_raw_events,
    normalize_events,
    write_filling_snapshot,
)

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TelemetryTest(unittest.TestCase):
    def test_json_mapping_derives_filling_attainments(self) -> None:
        raw_events = load_raw_events(REPO_ROOT / "fixtures/telemetry/posthog-ish-events.json")
        mapping = load_mapping(REPO_ROOT / "fixtures/telemetry/posthog-ish-mapping.yaml")
        events = normalize_events(raw_events, mapping, source="posthog_export")
        attainments = derive_stage_attainments(
            events,
            ProductFunnelConfig(value_task_families=("deployment",), return_interval_days=7),
        )

        self.assertEqual([event.event_type.value for event in events], [
            "account.created",
            "setup.completed",
            "workload.completed",
            "workload.completed",
            "subscription.started",
        ])
        self.assertIn(ProductFunnelStage.LAUNCH, {item.stage for item in attainments})
        self.assertIn(ProductFunnelStage.INITIAL_VALUE, {item.stage for item in attainments})
        self.assertIn(ProductFunnelStage.NEXT_VALUE, {item.stage for item in attainments})
        self.assertIn(ProductFunnelStage.GROW, {item.stage for item in attainments})

    def test_filling_snapshot_combines_estimates_derived_counts_and_incompatibility(self) -> None:
        raw_events = load_raw_events(REPO_ROOT / "fixtures/telemetry/posthog-ish-events.json")
        mapping = load_mapping(REPO_ROOT / "fixtures/telemetry/posthog-ish-mapping.yaml")
        config = load_product_funnel_config(REPO_ROOT / "fixtures/telemetry/filling-config.yaml")
        events = normalize_events(raw_events, mapping, source="posthog_export")
        snapshot = build_filling_snapshot(events, config)

        counts = {count.stage: count for count in snapshot.stage_counts}
        transitions = {transition.transition_id: transition for transition in snapshot.transitions}

        self.assertEqual(counts[ProductFunnelStage.FIT].count, 1000)
        self.assertEqual(counts[ProductFunnelStage.FIT].evidence_kind.value, "estimated")
        self.assertEqual(counts[ProductFunnelStage.LAUNCH].count, 1)
        self.assertEqual(counts[ProductFunnelStage.INITIAL_VALUE].count, 1)
        self.assertEqual(counts[ProductFunnelStage.NEXT_VALUE].count, 1)
        self.assertEqual(counts[ProductFunnelStage.GROW].count, 1)
        self.assertEqual(transitions["fit_to_investigate"].conversion_rate, 63.0)
        self.assertAlmostEqual(transitions["investigate_to_land"].conversion_rate or 0, 47.9365, places=3)
        self.assertEqual(
            transitions["land_to_launch"].status,
            FunnelTransitionStatus.INCOMPATIBLE_POPULATION,
        )
        self.assertEqual(transitions["initial_value_to_next_value"].conversion_rate, 100.0)

    def test_transition_refuses_incompatible_populations(self) -> None:
        window = MeasurementWindow(
            period_start="2026-07-01T00:00:00Z",
            period_end="2026-07-31T23:59:59Z",
            interval_type=MeasurementIntervalType.COHORT,
        )
        population = PopulationDefinition(
            id="mixed_sources",
            label="Mixed sources",
            description="Anonymous selected observations and identified activated accounts.",
        )

        transition = calculate_transition(
            (),
            ProductFunnelStage.LAND,
            ProductFunnelStage.LAUNCH,
            window=window,
            population=population,
            compatible_population=False,
            incompatibility_reason="Selected observations cannot be joined to activated accounts.",
        )

        self.assertEqual(transition.status, FunnelTransitionStatus.INCOMPATIBLE_POPULATION)
        self.assertIsNone(transition.conversion_rate)
        self.assertEqual(
            transition.status_reason,
            "Selected observations cannot be joined to activated accounts.",
        )

    def test_filling_snapshot_exports_prometheus_metrics(self) -> None:
        raw_events = load_raw_events(REPO_ROOT / "fixtures/telemetry/posthog-ish-events.json")
        mapping = load_mapping(REPO_ROOT / "fixtures/telemetry/posthog-ish-mapping.yaml")
        config = load_product_funnel_config(REPO_ROOT / "fixtures/telemetry/filling-config.yaml")
        events = normalize_events(raw_events, mapping, source="posthog_export")
        snapshot = build_filling_snapshot(events, config)

        metrics = filling_snapshot_to_prometheus(snapshot)

        self.assertIn("# TYPE funnelcake_filling_stage_count gauge", metrics)
        self.assertIn('funnelcake_filling_stage_count{stage="fit"', metrics)
        self.assertIn('funnelcake_filling_transition_rate{transition="fit_to_investigate"', metrics)
        self.assertIn("} 0.63", metrics)
        self.assertNotIn('transition="land_to_launch",', metrics)

    def test_snapshot_round_trips_and_compares_status_aware_deltas(self) -> None:
        mapping = load_mapping(REPO_ROOT / "fixtures/telemetry/posthog-ish-mapping.yaml")
        baseline_events = normalize_events(
            load_raw_events(REPO_ROOT / "fixtures/telemetry/posthog-ish-events.json"),
            mapping,
            source="posthog_export",
        )
        current_events = normalize_events(
            load_raw_events(REPO_ROOT / "fixtures/telemetry/posthog-ish-events-current.json"),
            mapping,
            source="posthog_export",
        )
        baseline = build_filling_snapshot(
            baseline_events,
            load_product_funnel_config(REPO_ROOT / "fixtures/telemetry/filling-config.yaml"),
        )
        current = build_filling_snapshot(
            current_events,
            load_product_funnel_config(REPO_ROOT / "fixtures/telemetry/filling-config-current.yaml"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = write_filling_snapshot(baseline, Path(temp_dir) / "baseline.json")
            loaded_baseline = load_filling_snapshot(baseline_path)

        comparison = compare_filling_snapshots(loaded_baseline, current)
        transitions = {transition.transition_id: transition for transition in comparison.transitions}
        counts = {count.stage: count for count in comparison.stage_counts}

        self.assertEqual(counts[ProductFunnelStage.FIT].delta, 200)
        self.assertEqual(transitions["fit_to_investigate"].delta_percentage_points, 2.0)
        self.assertEqual(transitions["launch_to_initial_value"].delta_percentage_points, -50.0)
        self.assertIsNone(transitions["land_to_launch"].delta_percentage_points)
        self.assertEqual(
            transitions["land_to_launch"].status_note,
            "no delta for status incompatible_population",
        )


if __name__ == "__main__":
    unittest.main()
