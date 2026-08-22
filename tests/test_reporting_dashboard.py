from __future__ import annotations

import unittest

from funnelcake_reporting import build_dashboard_overview, load_dashboard_fixture

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReportingDashboardTest(unittest.TestCase):
    def test_dashboard_overview_does_not_build_fake_dessert_conversion(self) -> None:
        fixture = load_dashboard_fixture(REPO_ROOT / "fixtures/dashboard/demo.json")

        overview = build_dashboard_overview(
            trials=fixture["trials"],
            failures=fixture["failures"],
            diagnoses=fixture["diagnoses"],
            metrics=fixture["metrics"],
            eligible_count=fixture["eligible_count"],
        )

        self.assertEqual(overview.conversion, ())


if __name__ == "__main__":
    unittest.main()
