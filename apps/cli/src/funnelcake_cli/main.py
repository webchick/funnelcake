from __future__ import annotations

import argparse

from funnelcake_benchmark_builder import BenchmarkSpec
from funnelcake_discover_eval import DiscoveryEvalPlan
from funnelcake_intent_extraction import IntentProfile
from funnelcake_platform_profile import PlatformProfile
from funnelcake_reporting import ReportSpec
from funnelcake_signal_mining import SignalSet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="funnelcake")
    parser.add_argument(
        "command",
        choices=["status"],
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        print(status())
