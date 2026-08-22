from __future__ import annotations

import unittest

from funnelcake_shared import (
    DESSERT_DIAGNOSTIC_METRIC_BY_ID,
    DESSERT_DIAGNOSTIC_METRIC_BY_STAGE,
    Duration,
    DurationUnit,
    MeasurementIntervalType,
    MeasurementQuality,
    MeasurementSource,
    MeasurementWindow,
    MetricResult,
    MetricStatus,
    MetricUnit,
    PRODUCT_FUNNEL_STAGE_DEFINITION_BY_STAGE,
    PRODUCT_FUNNEL_STAGE_ORDER,
    PRODUCT_FUNNEL_TRANSITION_BY_ID,
    PopulationDefinition,
    ProductFunnelStage,
    DessertStage,
)


class MetricContractTest(unittest.TestCase):
    def test_repeat_input_alias_normalizes_to_retain(self) -> None:
        self.assertEqual(DessertStage("repeat"), DessertStage.RETAIN)
        self.assertEqual(DessertStage("repeat").value, "retain")

    def test_product_funnel_is_primary_progression_model(self) -> None:
        self.assertEqual(
            PRODUCT_FUNNEL_STAGE_ORDER,
            (
                ProductFunnelStage.FIT,
                ProductFunnelStage.INVESTIGATE,
                ProductFunnelStage.LAND,
                ProductFunnelStage.LAUNCH,
                ProductFunnelStage.INITIAL_VALUE,
                ProductFunnelStage.NEXT_VALUE,
                ProductFunnelStage.GROW,
            ),
        )
        transition = PRODUCT_FUNNEL_TRANSITION_BY_ID["launch_to_initial_value"]
        self.assertEqual(transition.from_stage, ProductFunnelStage.LAUNCH)
        self.assertEqual(transition.to_stage, ProductFunnelStage.INITIAL_VALUE)
        self.assertEqual(ProductFunnelStage("activated"), ProductFunnelStage.LAUNCH)
        self.assertEqual(ProductFunnelStage("first_value").value, "initial_value")
        self.assertEqual(
            PRODUCT_FUNNEL_STAGE_DEFINITION_BY_STAGE[ProductFunnelStage.FIT].plg_meaning,
            "eligible demand",
        )

    def test_dessert_metrics_are_diagnostics_for_funnel_transitions(self) -> None:
        setup = DESSERT_DIAGNOSTIC_METRIC_BY_STAGE[DessertStage.SETUP]
        trust = DESSERT_DIAGNOSTIC_METRIC_BY_ID["autonomous_workload_share"]

        self.assertEqual(setup.id, "autonomous_setup_completion_rate")
        self.assertEqual(setup.diagnostic_for, ("land_to_launch",))
        self.assertIn("next_value_to_grow", trust.diagnostic_for)

    def test_metric_result_distinguishes_status_from_value(self) -> None:
        result = MetricResult(
            metric_id="value_retention_rate",
            stage=DessertStage.RETAIN,
            value=None,
            unit=MetricUnit.PERCENTAGE,
            numerator=None,
            denominator=None,
            window=MeasurementWindow(
                period_start="2026-07-01T00:00:00Z",
                period_end="2026-07-31T23:59:59Z",
                interval_type=MeasurementIntervalType.COHORT,
                return_interval=Duration(value=30, unit=DurationUnit.DAY),
            ),
            source=MeasurementSource.PRODUCTION,
            quality=MeasurementQuality.MAPPED,
            population=PopulationDefinition(
                id="july_agent_activated_accounts",
                label="July agent-activated accounts",
                description="Accounts activated by an agent-mediated successful workload during July.",
            ),
            status=MetricStatus.INSUFFICIENT_DATA,
            diagnostics={"oldest_activation_age_days": 18},
        )

        self.assertIsNone(result.value)
        self.assertEqual(result.status, MetricStatus.INSUFFICIENT_DATA)
        self.assertEqual(result.window.return_interval, Duration(value=30, unit=DurationUnit.DAY))


if __name__ == "__main__":
    unittest.main()
