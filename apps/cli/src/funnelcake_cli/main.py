from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from funnelcake_answer_observation import (
    compare_observation_sets,
    format_observation_comparison,
    format_domain_detail,
    format_observation_detail,
    format_observation_summary,
    format_observation_validation_report,
    format_product_detail,
    format_prompt_detail,
    import_observation_set_sqlite,
    load_observation_set,
    summarize_observations,
    validate_observation_file,
    write_observation_set,
)
from funnelcake_benchmark_builder import BenchmarkSpec, format_task_spec, load_task_spec
from funnelcake_discover_eval import (
    DiscoveryEvalPlan,
    PhoenixDependencyError,
    diagnose_task_run,
    evaluate_task_run,
    format_diagnosis_bundle,
    format_diagnosis_detail,
    format_trial_run,
    format_run_evaluation,
    load_diagnosis_bundle_artifact,
    load_trial_run,
    load_diagnosis_bundles_dir,
    load_trial_run_artifact,
    load_trial_runs_dir,
    run_task_spec,
    run_task_suite,
    send_run_to_phoenix,
    format_suite_run,
    write_diagnosis_bundle,
    write_otlp_json,
    write_run_evaluation,
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

    observe_answers = subparsers.add_parser(
        "observe-answers",
        help="Summarize AEO/GEO answer observations from a JSON observation set.",
    )
    observe_answers.add_argument("path", help="Path to an answer observation JSON file.")
    observe_answers.add_argument(
        "--json",
        action="store_true",
        help="Print the summary as machine-readable JSON.",
    )

    inspect_observation = subparsers.add_parser(
        "inspect-observation",
        help="Print one AEO/GEO observation with its raw answer and evidence.",
    )
    inspect_observation.add_argument("path", help="Path to an answer observation JSON file.")
    inspect_observation.add_argument("observation_id", help="Observation ID to inspect.")

    inspect_product = subparsers.add_parser(
        "inspect-product",
        help="Print all observations mentioning or recommending one AEO/GEO product.",
    )
    inspect_product.add_argument("path", help="Path to an answer observation JSON file.")
    inspect_product.add_argument("product", help="Product ID, name, or alias to inspect.")

    inspect_prompt = subparsers.add_parser(
        "inspect-prompt",
        help="Print all AEO/GEO observations for one prompt.",
    )
    inspect_prompt.add_argument("path", help="Path to an answer observation JSON file.")
    inspect_prompt.add_argument("prompt_id", help="Prompt ID to inspect.")

    inspect_domain = subparsers.add_parser(
        "inspect-domain",
        help="Print observations and prompts connected to one cited or retrieved domain.",
    )
    inspect_domain.add_argument("path", help="Path to an answer observation JSON file.")
    inspect_domain.add_argument("domain", help="Domain or URL to inspect.")

    normalize_observations = subparsers.add_parser(
        "normalize-observations",
        help="Validate and write a normalized AEO/GEO observation set.",
    )
    normalize_observations.add_argument("path", help="Path to an answer observation JSON file.")
    normalize_observations.add_argument(
        "--out",
        required=True,
        help="Path for the normalized observation-set JSON output.",
    )

    validate_observations = subparsers.add_parser(
        "validate-observations",
        help="Validate an AEO/GEO observation set and print ingestion warnings.",
    )
    validate_observations.add_argument("path", help="Path to an answer observation JSON file.")
    validate_observations.add_argument(
        "--json",
        action="store_true",
        help="Print validation results as machine-readable JSON.",
    )

    import_sqlite = subparsers.add_parser(
        "import-observations-sqlite",
        help="Import an AEO/GEO observation set into a SQLite database.",
    )
    import_sqlite.add_argument("path", help="Path to an answer observation JSON file.")
    import_sqlite.add_argument(
        "--db",
        default="data/funnelcake.db",
        help="SQLite database path.",
    )

    compare_observations = subparsers.add_parser(
        "compare-observations",
        help="Compare two AEO/GEO observation sets without making causal claims.",
    )
    compare_observations.add_argument("baseline_path", help="Path to the baseline observation JSON file.")
    compare_observations.add_argument("followup_path", help="Path to the follow-up observation JSON file.")
    compare_observations.add_argument(
        "--json",
        action="store_true",
        help="Print the comparison as machine-readable JSON.",
    )

    geo = subparsers.add_parser(
        "geo",
        help="Grouped AEO/GEO observation commands.",
    )
    geo_subparsers = geo.add_subparsers(dest="geo_command", required=True)

    geo_summary = geo_subparsers.add_parser(
        "summary",
        help="Summarize AEO/GEO answer observations from a JSON observation set.",
    )
    geo_summary.add_argument("path", help="Path to an answer observation JSON file.")
    geo_summary.add_argument(
        "--json",
        action="store_true",
        help="Print the summary as machine-readable JSON.",
    )

    geo_inspect_observation = geo_subparsers.add_parser(
        "inspect-observation",
        help="Print one AEO/GEO observation with its raw answer and evidence.",
    )
    geo_inspect_observation.add_argument("path", help="Path to an answer observation JSON file.")
    geo_inspect_observation.add_argument("observation_id", help="Observation ID to inspect.")

    geo_inspect_product = geo_subparsers.add_parser(
        "inspect-product",
        help="Print all observations mentioning or recommending one AEO/GEO product.",
    )
    geo_inspect_product.add_argument("path", help="Path to an answer observation JSON file.")
    geo_inspect_product.add_argument("product", help="Product ID, name, or alias to inspect.")

    geo_inspect_prompt = geo_subparsers.add_parser(
        "inspect-prompt",
        help="Print all AEO/GEO observations for one prompt.",
    )
    geo_inspect_prompt.add_argument("path", help="Path to an answer observation JSON file.")
    geo_inspect_prompt.add_argument("prompt_id", help="Prompt ID to inspect.")

    geo_inspect_domain = geo_subparsers.add_parser(
        "inspect-domain",
        help="Print observations and prompts connected to one cited or retrieved domain.",
    )
    geo_inspect_domain.add_argument("path", help="Path to an answer observation JSON file.")
    geo_inspect_domain.add_argument("domain", help="Domain or URL to inspect.")

    geo_normalize = geo_subparsers.add_parser(
        "normalize",
        help="Validate and write a normalized AEO/GEO observation set.",
    )
    geo_normalize.add_argument("path", help="Path to an answer observation JSON file.")
    geo_normalize.add_argument(
        "--out",
        required=True,
        help="Path for the normalized observation-set JSON output.",
    )

    geo_validate = geo_subparsers.add_parser(
        "validate",
        help="Validate an AEO/GEO observation set and print ingestion warnings.",
    )
    geo_validate.add_argument("path", help="Path to an answer observation JSON file.")
    geo_validate.add_argument(
        "--json",
        action="store_true",
        help="Print validation results as machine-readable JSON.",
    )

    geo_import_sqlite = geo_subparsers.add_parser(
        "import-sqlite",
        help="Import an AEO/GEO observation set into a SQLite database.",
    )
    geo_import_sqlite.add_argument("path", help="Path to an answer observation JSON file.")
    geo_import_sqlite.add_argument(
        "--db",
        default="data/funnelcake.db",
        help="SQLite database path.",
    )

    geo_compare = geo_subparsers.add_parser(
        "compare",
        help="Compare two AEO/GEO observation sets without making causal claims.",
    )
    geo_compare.add_argument("baseline_path", help="Path to the baseline observation JSON file.")
    geo_compare.add_argument("followup_path", help="Path to the follow-up observation JSON file.")
    geo_compare.add_argument(
        "--json",
        action="store_true",
        help="Print the comparison as machine-readable JSON.",
    )

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

    evaluate_run = subparsers.add_parser(
        "evaluate-run",
        help="Evaluate a captured run against a benchmark task spec.",
    )
    evaluate_run.add_argument("task_path", help="Path to a benchmark task JSON spec.")
    evaluate_run.add_argument("run_path", help="Path to a run artifact directory or run.json.")
    evaluate_run.add_argument(
        "--write",
        action="store_true",
        help="Write evaluation.json next to the run artifact.",
    )
    evaluate_run.add_argument(
        "--out",
        help="Path for evaluation JSON output. Implies --write.",
    )

    diagnose_run = subparsers.add_parser(
        "diagnose-run",
        help="Create conservative diagnoses from a task spec, run, and optional evaluation.",
    )
    diagnose_run.add_argument("task_path", help="Path to a benchmark task JSON spec.")
    diagnose_run.add_argument("run_path", help="Path to a run artifact directory or run.json.")
    diagnose_run.add_argument(
        "--evaluation",
        help="Path to evaluation.json. Defaults to <run-dir>/evaluation.json when present.",
    )
    diagnose_run.add_argument(
        "--write",
        action="store_true",
        help="Write diagnosis.json next to the run artifact.",
    )
    diagnose_run.add_argument(
        "--out",
        help="Path for diagnosis JSON output. Implies --write.",
    )

    show_diagnosis = subparsers.add_parser(
        "show-diagnosis",
        help="Print a diagnosis and resolve its evidence references against the trace.",
    )
    show_diagnosis.add_argument(
        "run_path",
        help="Path to a run artifact directory, run.json, or diagnosis.json.",
    )
    show_diagnosis.add_argument("diagnosis_id", help="Diagnosis ID to inspect.")

    run_suite = subparsers.add_parser(
        "run-suite",
        help="Run, evaluate, diagnose, and summarize one or more task specs.",
    )
    run_suite.add_argument(
        "paths",
        nargs="+",
        help="Task spec JSON files or directories containing task spec JSON files.",
    )
    run_suite.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Directory where normalized run artifacts should be written.",
    )
    run_suite.add_argument(
        "--agent",
        default="manual-placeholder",
        help="Agent or harness name to record on generated trials.",
    )
    run_suite.add_argument(
        "--eligible-count",
        type=int,
        help="Eligible intent count to use for conversion math.",
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

    diagnosis_bundles = load_diagnosis_bundles_dir(runs_dir)
    diagnoses = tuple(
        diagnosis
        for bundle in diagnosis_bundles
        for diagnosis in bundle.diagnoses
    )
    overview = build_dashboard_from_trial_runs(
        runs,
        eligible_count=eligible_count,
        diagnoses=diagnoses,
    )
    evaluation_count = len(list(Path(runs_dir).glob("*/evaluation.json")))
    diagnosis_count = len(diagnosis_bundles)
    return "\n".join(
        [
            format_dashboard_overview(overview),
            "",
            "Artifacts",
            f"evaluations={evaluation_count}/{len(runs)}",
            f"diagnoses={diagnosis_count}/{len(runs)}",
        ]
    )


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


def observe_answers(path: str, json_output: bool = False) -> str:
    observation_set = load_observation_set(path)
    summary = summarize_observations(observation_set)
    if json_output:
        return format_json(summary)
    return format_observation_summary(summary)


def inspect_observation(path: str, observation_id: str) -> str:
    observation_set = load_observation_set(path)
    return format_observation_detail(observation_set, observation_id)


def inspect_product(path: str, product: str) -> str:
    observation_set = load_observation_set(path)
    return format_product_detail(observation_set, product)


def inspect_prompt(path: str, prompt_id: str) -> str:
    observation_set = load_observation_set(path)
    return format_prompt_detail(observation_set, prompt_id)


def inspect_domain(path: str, domain: str) -> str:
    observation_set = load_observation_set(path)
    return format_domain_detail(observation_set, domain)


def normalize_observations(path: str, output_path: str) -> str:
    observation_set = load_observation_set(path)
    written_path = write_observation_set(observation_set, output_path)
    return "\n".join(
        [
            f"normalized_observation_set={observation_set.id}",
            f"observations={len(observation_set.observations)}",
            f"output_path={written_path}",
        ]
    )


def validate_observations(path: str, json_output: bool = False) -> str:
    report = validate_observation_file(path)
    if json_output:
        return format_json(report)
    return format_observation_validation_report(report)


def import_observations_sqlite(path: str, db_path: str) -> str:
    observation_set = load_observation_set(path)
    result = import_observation_set_sqlite(observation_set, db_path)
    return "\n".join(
        [
            f"imported_observation_set={result['run_id']}",
            f"db_path={result['db_path']}",
            f"observations={result['observations']}",
            f"citations={result['citations']}",
            f"retrieved_sources={result['retrieved_sources']}",
            f"product_mentions={result['product_mentions']}",
        ]
    )


def print_observation_validation(path: str, json_output: bool) -> None:
    report = validate_observation_file(path)
    print(format_json(report) if json_output else format_observation_validation_report(report))
    if not report.valid:
        raise SystemExit(1)


def compare_observations(
    baseline_path: str,
    followup_path: str,
    json_output: bool = False,
) -> str:
    baseline = load_observation_set(baseline_path)
    followup = load_observation_set(followup_path)
    comparison = compare_observation_sets(baseline, followup)
    if json_output:
        return format_json(comparison)
    return format_observation_comparison(comparison)


def geo_command(args: argparse.Namespace) -> str:
    if args.geo_command == "summary":
        return observe_answers(args.path, args.json)
    if args.geo_command == "inspect-observation":
        return inspect_observation(args.path, args.observation_id)
    if args.geo_command == "inspect-product":
        return inspect_product(args.path, args.product)
    if args.geo_command == "inspect-prompt":
        return inspect_prompt(args.path, args.prompt_id)
    if args.geo_command == "inspect-domain":
        return inspect_domain(args.path, args.domain)
    if args.geo_command == "normalize":
        return normalize_observations(args.path, args.out)
    if args.geo_command == "validate":
        return validate_observations(args.path, args.json)
    if args.geo_command == "import-sqlite":
        return import_observations_sqlite(args.path, args.db)
    if args.geo_command == "compare":
        return compare_observations(args.baseline_path, args.followup_path, args.json)
    raise ValueError(f"unknown geo command: {args.geo_command}")


def format_json(value: object) -> str:
    return json.dumps(asdict(value), indent=2)


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


def evaluate_run_command(
    task_path: str,
    run_path: str,
    write: bool,
    output_path: str | None,
) -> str:
    evaluation = evaluate_task_run(task_path, run_path)
    lines = [format_run_evaluation(evaluation)]
    if write or output_path is not None:
        written_path = write_run_evaluation(evaluation, run_path, output_path)
        lines.extend(["", f"output_path={written_path}"])
    return "\n".join(lines)


def diagnose_run_command(
    task_path: str,
    run_path: str,
    evaluation_path: str | None,
    write: bool,
    output_path: str | None,
) -> str:
    bundle = diagnose_task_run(task_path, run_path, evaluation_path)
    lines = [format_diagnosis_bundle(bundle)]
    if write or output_path is not None:
        written_path = write_diagnosis_bundle(bundle, run_path, output_path)
        lines.extend(["", f"output_path={written_path}"])
    return "\n".join(lines)


def show_diagnosis_command(run_path: str, diagnosis_id: str) -> str:
    artifact_path = Path(run_path)
    if artifact_path.name in {"run.json", "diagnosis.json"}:
        artifact_path = artifact_path.parent
    run = load_trial_run_artifact(artifact_path)
    bundle = load_diagnosis_bundle_artifact(artifact_path)
    return format_diagnosis_detail(bundle, run, diagnosis_id)


def run_suite_command(
    paths: list[str],
    artifacts_dir: str,
    agent: str,
    eligible_count: int | None,
) -> str:
    suite = run_task_suite(tuple(paths), artifacts_dir=artifacts_dir, agent=agent)
    runs_dir = str(Path(artifacts_dir) / "runs")
    return "\n\n".join(
        [
            format_suite_run(suite),
            dashboard_summary(runs_dir, eligible_count),
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
    elif args.command == "observe-answers":
        print(observe_answers(args.path, args.json))
    elif args.command == "inspect-observation":
        print(inspect_observation(args.path, args.observation_id))
    elif args.command == "inspect-product":
        print(inspect_product(args.path, args.product))
    elif args.command == "inspect-prompt":
        print(inspect_prompt(args.path, args.prompt_id))
    elif args.command == "inspect-domain":
        print(inspect_domain(args.path, args.domain))
    elif args.command == "normalize-observations":
        print(normalize_observations(args.path, args.out))
    elif args.command == "validate-observations":
        print_observation_validation(args.path, args.json)
    elif args.command == "import-observations-sqlite":
        print(import_observations_sqlite(args.path, args.db))
    elif args.command == "compare-observations":
        print(compare_observations(args.baseline_path, args.followup_path, args.json))
    elif args.command == "geo":
        if args.geo_command == "validate":
            print_observation_validation(args.path, args.json)
            return
        print(geo_command(args))
    elif args.command == "run-task":
        print(run_task(args.path, args.artifacts_dir, args.agent))
    elif args.command == "evaluate-run":
        print(evaluate_run_command(args.task_path, args.run_path, args.write, args.out))
    elif args.command == "diagnose-run":
        print(
            diagnose_run_command(
                args.task_path,
                args.run_path,
                args.evaluation,
                args.write,
                args.out,
            )
        )
    elif args.command == "show-diagnosis":
        print(show_diagnosis_command(args.run_path, args.diagnosis_id))
    elif args.command == "run-suite":
        print(run_suite_command(args.paths, args.artifacts_dir, args.agent, args.eligible_count))
