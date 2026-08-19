from __future__ import annotations

import argparse
from pathlib import Path

from funnelcake_benchmark_builder import BenchmarkSpec
from funnelcake_discover_eval import DiscoveryEvalPlan
from funnelcake_intent_extraction import IntentProfile
from funnelcake_platform_profile import PlatformProfile
from funnelcake_reporting import ReportSpec, build_dashboard_overview, load_dashboard_fixture
from funnelcake_signal_mining import SignalSet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="funnelcake")
    parser.add_argument(
        "command",
        choices=["status", "dashboard-demo"],
        nargs="?",
        default="status",
        help="Command to run.",
    )
    return parser


def status() -> str:
    profile = PlatformProfile(name="example", homepage="https://example.com")
    signals = SignalSet(platform=profile.name, signals=())
    intent = IntentProfile(platform=profile.name, intents=())
    benchmark = BenchmarkSpec(platform=profile.name, tasks=())
    eval_plan = DiscoveryEvalPlan(platform=profile.name, benchmarks=())
    report = ReportSpec(platform=profile.name, sections=("summary",))

    return "\n".join(
        [
            "Funnelcake scaffold ready.",
            f"platform_profile={profile.name}",
            f"signals={len(signals.signals)}",
            f"intents={len(intent.intents)}",
            f"benchmark_tasks={len(benchmark.tasks)}",
            f"eval_benchmarks={len(eval_plan.benchmarks)}",
            f"report_sections={len(report.sections)}",
        ]
    )


def dashboard_demo() -> str:
    repo_root = Path(__file__).resolve().parents[4]
    fixture = load_dashboard_fixture(repo_root / "fixtures/dashboard/demo.json")
    overview = build_dashboard_overview(
        trials=fixture["trials"],
        failures=fixture["failures"],
        diagnoses=fixture["diagnoses"],
        metrics=fixture["metrics"],
        eligible_count=fixture["eligible_count"],
    )
    biggest_leak = overview.biggest_leak

    lines = ["DESSERT dashboard demo"]
    lines.extend(f"{score.stage.value}: {score.score:.0f}" for score in overview.stage_scores)

    if biggest_leak is not None:
        lines.append(
            "biggest_leak="
            f"{biggest_leak.stage.value} "
            f"{biggest_leak.failed_trials}/{biggest_leak.total_trials} "
            f"({biggest_leak.failure_rate:.0%})"
        )
        lines.extend(
            f"cluster={cluster.failure_type} trials={cluster.affected_trials}"
            for cluster in biggest_leak.top_clusters
        )

    return "\n".join(lines)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        print(status())
    elif args.command == "dashboard-demo":
        print(dashboard_demo())
