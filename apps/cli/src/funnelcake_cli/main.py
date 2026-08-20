from __future__ import annotations

import argparse
from pathlib import Path

from funnelcake_benchmark_builder import BenchmarkSpec, format_task_spec, load_task_spec
from funnelcake_discover_eval import (
    DiscoveryEvalPlan,
    PhoenixDependencyError,
    format_trial_run,
    load_trial_run,
    load_trial_run_artifact,
    load_trial_runs_dir,
    run_task_spec,
    send_run_to_phoenix,
    write_otlp_json,
    write_trial_run,
)
from funnelcake_intent_extraction import IntentProfile
from funnelcake_platform_profile import PlatformProfile
from funnelcake_reporting import (
    ReportSpec,
    build_dashboard_from_trial_runs,
    build_dashboard_overview,
    format_dashboard_overview,
    load_dashboard_fixture,
)
from funnelcake_signal_mining import SignalSet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="funnelcake")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Show scaffold status.")
    subparsers.add_parser("dashboard-demo", help="Render the dashboard demo fixture.")

    dashboard_summary = subparsers.add_parser(
        "dashboard-summary",
        help="Render a dashboard summary from captured run artifacts.",
    )
    dashboard_summary.add_argument(
        "--runs-dir",
        default="artifacts/runs",
        help="Directory containing <trial_id>/run.json artifacts.",
    )
    dashboard_summary.add_argument(
        "--eligible-count",
        type=int,
        help="Eligible intent count to use for conversion math.",
    )

    capture_run = subparsers.add_parser(
        "capture-run",
        help="Validate and write a captured trial run into artifacts.",
    )
    capture_run.add_argument("path", help="Path to a trial run JSON capture.")
    capture_run.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Directory where normalized run artifacts should be written.",
    )

    show_run = subparsers.add_parser(
        "show-run",
        help="Print a readable view of a captured trial run.",
    )
    show_run.add_argument("path", help="Path to a run artifact directory or run.json.")

    export_otlp = subparsers.add_parser(
        "export-otlp",
        help="Export a captured trial run as OTLP/JSON traces.",
    )
    export_otlp.add_argument("path", help="Path to a run artifact directory or run.json.")
    export_otlp.add_argument(
        "--out",
        help="Path for the OTLP/JSON output. Defaults to <run-dir>/otlp.json.",
    )

    send_phoenix = subparsers.add_parser(
        "send-phoenix",
        help="Send a captured trial run to Phoenix over OTLP HTTP/protobuf.",
    )
    send_phoenix.add_argument("path", help="Path to a run artifact directory or run.json.")
    send_phoenix.add_argument(
        "--endpoint",
        default="http://localhost:6006/v1/traces",
        help="Phoenix OTLP HTTP endpoint.",
    )
    send_phoenix.add_argument(
        "--project-name",
        default="funnelcake",
        help="Phoenix project name to attach as a resource attribute.",
    )
    send_phoenix.add_argument(
        "--api-key",
        help="Phoenix API key for Phoenix Cloud or authenticated deployments.",
    )

    validate_task = subparsers.add_parser(
        "validate-task",
        help="Validate and print a benchmark task spec.",
    )
    validate_task.add_argument("path", help="Path to a benchmark task JSON spec.")

    run_task = subparsers.add_parser(
        "run-task",
        help="Create a placeholder captured run from a benchmark task spec.",
    )
    run_task.add_argument("path", help="Path to a benchmark task JSON spec.")
    run_task.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Directory where normalized run artifacts should be written.",
    )
    run_task.add_argument(
        "--agent",
        default="manual-placeholder",
        help="Agent or harness name to record on the trial.",
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


def dashboard_summary(runs_dir: str, eligible_count: int | None) -> str:
    runs = load_trial_runs_dir(runs_dir)
    if not runs:
        return f"No runs found in {runs_dir}"

    overview = build_dashboard_from_trial_runs(runs, eligible_count=eligible_count)
    return format_dashboard_overview(overview)


def capture_run(path: str, artifacts_dir: str) -> str:
    run = load_trial_run(path)
    output_dir = write_trial_run(run, artifacts_dir)
    return "\n".join(
        [
            f"captured_trial={run.trial.id}",
            f"trace_id={run.trial.trace_id}",
            f"spans={len(run.spans)}",
            f"events={sum(len(span.events) for span in run.spans)}",
            f"failures={len(run.failures)}",
            f"final_state_passed={run.final_state.passed}",
            f"output_dir={output_dir}",
        ]
    )


def show_run(path: str) -> str:
    return format_trial_run(load_trial_run_artifact(path))


def export_otlp(path: str, output_path: str | None) -> str:
    run = load_trial_run_artifact(path)
    if output_path is None:
        artifact_path = Path(path)
        output_path = str((artifact_path if artifact_path.is_dir() else artifact_path.parent) / "otlp.json")
    written_path = write_otlp_json(run, output_path)
    return "\n".join(
        [
            f"exported_trial={run.trial.id}",
            f"trace_id={run.trial.trace_id}",
            f"output_path={written_path}",
        ]
    )


def send_phoenix(
    path: str,
    endpoint: str,
    project_name: str,
    api_key: str | None,
) -> str:
    try:
        result = send_run_to_phoenix(
            path,
            endpoint=endpoint,
            project_name=project_name,
            api_key=api_key,
        )
    except (PhoenixDependencyError, RuntimeError) as exc:
        return str(exc)

    return "\n".join(
        [
            f"sent_trial={result['trial_id']}",
            f"trace_id={result['trace_id']}",
            f"endpoint={result['endpoint']}",
            f"status={result['status']} {result['reason']}",
        ]
    )


def validate_task(path: str) -> str:
    return format_task_spec(load_task_spec(path))


def run_task(path: str, artifacts_dir: str, agent: str) -> str:
    run, output_dir = run_task_spec(path, artifacts_dir=artifacts_dir, agent=agent)
    return "\n".join(
        [
            f"trial={run.trial.id}",
            f"trace_id={run.trial.trace_id}",
            f"status={run.trial.status.value}",
            f"final_state_passed={run.final_state.passed}",
            f"output_dir={output_dir}",
        ]
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in (None, "status"):
        print(status())
    elif args.command == "dashboard-demo":
        print(dashboard_demo())
    elif args.command == "dashboard-summary":
        print(dashboard_summary(args.runs_dir, args.eligible_count))
    elif args.command == "capture-run":
        print(capture_run(args.path, args.artifacts_dir))
    elif args.command == "show-run":
        print(show_run(args.path))
    elif args.command == "export-otlp":
        print(export_otlp(args.path, args.out))
    elif args.command == "send-phoenix":
        print(send_phoenix(args.path, args.endpoint, args.project_name, args.api_key))
    elif args.command == "validate-task":
        print(validate_task(args.path))
    elif args.command == "run-task":
        print(run_task(args.path, args.artifacts_dir, args.agent))
