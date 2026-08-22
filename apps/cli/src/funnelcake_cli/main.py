from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from funnelcake_answer_observation import (
    compare_observation_sets,
    extract_product_mentions,
    format_observation_comparison,
    format_domain_detail,
    format_observation_detail,
    format_observation_summary,
    format_observation_validation_report,
    format_product_detail,
    format_prompt_detail,
    import_observation_set_sqlite,
    load_observation_set,
    run_fixture_provider,
    run_gemini_provider,
    run_openai_provider,
    run_perplexity_provider,
    run_provider_corpus,
    summarize_observations,
    validate_observation_file,
    write_observation_set,
)
from funnelcake_benchmark_builder import BenchmarkSpec, format_task_spec, load_task_spec
from funnelcake_collectors import (
    CollectorCapability,
    Experiment,
    MCPInspectorCollector,
    PromptfooCollector,
    format_observations,
    get_collector,
    load_observations,
    observations_to_dict,
    write_observations,
)
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
from funnelcake_telemetry import (
    build_filling_snapshot,
    compare_filling_snapshots,
    comparison_to_dict,
    format_filling_comparison,
    format_filling_snapshot,
    load_filling_snapshot,
    load_normalized_events,
    load_product_funnel_config,
    normalize_file,
    snapshot_to_dict,
    write_filling_snapshot,
    write_normalized_events,
)


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
    dashboard_summary.add_argument(
        "--filling-snapshot",
        help="Path to a saved FILLING snapshot JSON artifact for the product-facing dashboard.",
    )
    dashboard_summary.add_argument(
        "--compare-to",
        help="Optional baseline FILLING snapshot JSON to compare against --filling-snapshot.",
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

    extract_products = subparsers.add_parser(
        "extract-observation-products",
        help="Extract product mentions from raw AEO/GEO answer text.",
    )
    extract_products.add_argument("path", help="Path to an answer observation JSON file.")
    extract_products.add_argument(
        "--out",
        required=True,
        help="Path for the enriched observation-set JSON output.",
    )

    run_fixture = subparsers.add_parser(
        "run-observation-fixture",
        help="Run a fixture answer provider and write raw AEO/GEO observations.",
    )
    run_fixture.add_argument("path", help="Path to a fixture provider JSON config.")
    run_fixture.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    run_openai = subparsers.add_parser(
        "run-observation-openai",
        help="Run OpenAI Responses API prompts and write raw AEO/GEO observations.",
    )
    run_openai.add_argument("path", help="Path to an OpenAI provider JSON config.")
    run_openai.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    run_gemini = subparsers.add_parser(
        "run-observation-gemini",
        help="Run Gemini API prompts and write raw AEO/GEO observations.",
    )
    run_gemini.add_argument("path", help="Path to a Gemini provider JSON config.")
    run_gemini.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    run_perplexity = subparsers.add_parser(
        "run-observation-perplexity",
        help="Run Perplexity Sonar prompts and write raw AEO/GEO observations.",
    )
    run_perplexity.add_argument("path", help="Path to a Perplexity provider JSON config.")
    run_perplexity.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
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

    geo_extract_products = geo_subparsers.add_parser(
        "extract-products",
        help="Extract product mentions from raw AEO/GEO answer text.",
    )
    geo_extract_products.add_argument("path", help="Path to an answer observation JSON file.")
    geo_extract_products.add_argument(
        "--out",
        required=True,
        help="Path for the enriched observation-set JSON output.",
    )

    geo_run = geo_subparsers.add_parser(
        "run",
        help="Run a prompt corpus across one or more AEO/GEO providers.",
    )
    geo_run.add_argument("path", help="Path to a YAML or JSON prompt corpus.")
    geo_run.add_argument(
        "--providers",
        default="fixture",
        help="Comma-separated providers to run: fixture, openai, gemini, perplexity.",
    )
    geo_run.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of repetitions for each provider/prompt pair.",
    )
    geo_run.add_argument(
        "--out",
        help="Path for the observation-set JSON output. Defaults to artifacts/geo/<run-id>.json.",
    )

    geo_report = geo_subparsers.add_parser(
        "report",
        help="Render a readable AEO/GEO report from an observation set.",
    )
    geo_report.add_argument("path", help="Path to an answer observation JSON file.")
    geo_report.add_argument(
        "--json",
        action="store_true",
        help="Print the report as machine-readable JSON.",
    )

    geo_run_fixture = geo_subparsers.add_parser(
        "run-fixture",
        help="Run a fixture answer provider and write raw AEO/GEO observations.",
    )
    geo_run_fixture.add_argument("path", help="Path to a fixture provider JSON config.")
    geo_run_fixture.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    geo_run_openai = geo_subparsers.add_parser(
        "run-openai",
        help="Run OpenAI Responses API prompts and write raw AEO/GEO observations.",
    )
    geo_run_openai.add_argument("path", help="Path to an OpenAI provider JSON config.")
    geo_run_openai.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    geo_run_gemini = geo_subparsers.add_parser(
        "run-gemini",
        help="Run Gemini API prompts and write raw AEO/GEO observations.",
    )
    geo_run_gemini.add_argument("path", help="Path to a Gemini provider JSON config.")
    geo_run_gemini.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
    )

    geo_run_perplexity = geo_subparsers.add_parser(
        "run-perplexity",
        help="Run Perplexity Sonar prompts and write raw AEO/GEO observations.",
    )
    geo_run_perplexity.add_argument("path", help="Path to a Perplexity provider JSON config.")
    geo_run_perplexity.add_argument(
        "--out",
        required=True,
        help="Path for the raw observation-set JSON output.",
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

    telemetry = subparsers.add_parser(
        "telemetry",
        help="Grouped canonical telemetry commands.",
    )
    telemetry_subparsers = telemetry.add_subparsers(dest="telemetry_command", required=True)

    telemetry_normalize = telemetry_subparsers.add_parser(
        "normalize",
        help="Map JSON/JSONL product events into canonical Funnelcake telemetry.",
    )
    telemetry_normalize.add_argument("path", help="Path to raw JSON or JSONL events.")
    telemetry_normalize.add_argument(
        "--mapping",
        required=True,
        help="Path to the telemetry mapping YAML file.",
    )
    telemetry_normalize.add_argument(
        "--out",
        required=True,
        help="Path for normalized telemetry JSON output.",
    )
    telemetry_normalize.add_argument(
        "--source",
        default="generic_json",
        help="Source label to attach to normalized telemetry.",
    )

    telemetry_inspect = telemetry_subparsers.add_parser(
        "inspect",
        help="Inspect canonical telemetry and derived FILLING attainments.",
    )
    telemetry_inspect.add_argument("path", help="Path to normalized telemetry JSON.")
    telemetry_inspect.add_argument(
        "--return-interval-days",
        type=int,
        default=7,
        help="Return interval for deriving NEXT_VALUE.",
    )
    telemetry_inspect.add_argument(
        "--config",
        help="Path to a FILLING product config YAML file.",
    )
    telemetry_inspect.add_argument(
        "--json",
        action="store_true",
        help="Print inspection results as machine-readable JSON.",
    )

    filling = subparsers.add_parser(
        "filling",
        help="Grouped FILLING product-funnel commands.",
    )
    filling_subparsers = filling.add_subparsers(dest="filling_command", required=True)

    filling_snapshot = filling_subparsers.add_parser(
        "snapshot",
        help="Calculate a FILLING snapshot from normalized telemetry.",
    )
    filling_snapshot.add_argument("path", help="Path to normalized telemetry JSON.")
    filling_snapshot.add_argument(
        "--config",
        help="Path to a FILLING product config YAML file.",
    )
    filling_snapshot.add_argument(
        "--json",
        action="store_true",
        help="Print the snapshot as machine-readable JSON.",
    )
    filling_snapshot.add_argument(
        "--out",
        help="Path to write the snapshot JSON artifact.",
    )

    filling_compare = filling_subparsers.add_parser(
        "compare",
        help="Compare two saved FILLING snapshot JSON artifacts.",
    )
    filling_compare.add_argument("baseline_path", help="Path to the baseline snapshot JSON.")
    filling_compare.add_argument("current_path", help="Path to the current snapshot JSON.")
    filling_compare.add_argument(
        "--json",
        action="store_true",
        help="Print the comparison as machine-readable JSON.",
    )

    collect = subparsers.add_parser(
        "collect",
        help="Grouped normalized evidence collector commands.",
    )
    collect_subparsers = collect.add_subparsers(dest="collect_command", required=True)

    collect_run = collect_subparsers.add_parser(
        "run",
        help="Normalize evidence from a native or external collector artifact.",
    )
    collect_run.add_argument("path", help="Path to the collector input artifact.")
    collect_run.add_argument(
        "--collector",
        required=True,
        help="Collector id or alias, e.g. answer-observation or mcp-inspector.",
    )
    collect_run.add_argument(
        "--capability",
        help="Collector capability. Defaults from --collector when omitted.",
    )
    collect_run.add_argument(
        "--experiment-id",
        help="Experiment id to attach to normalized observations. Defaults to the input stem.",
    )
    collect_run.add_argument("--task-id", help="Optional task id to attach to observations.")
    collect_run.add_argument("--actor", help="Optional actor label to attach to observations.")
    collect_run.add_argument(
        "--json",
        action="store_true",
        help="Print normalized observations as machine-readable JSON.",
    )
    collect_run.add_argument(
        "--out",
        help="Path to write normalized observations JSON.",
    )

    collect_inspect = collect_subparsers.add_parser(
        "inspect",
        help="Print normalized collector observations.",
    )
    collect_inspect.add_argument("path", help="Path to normalized observations JSON.")
    collect_inspect.add_argument(
        "--json",
        action="store_true",
        help="Print normalized observations as machine-readable JSON.",
    )

    collect_mcp = collect_subparsers.add_parser(
        "mcp-inspector",
        help="Run MCP Inspector and normalize its JSON result.",
    )
    collect_mcp.add_argument("server", help="MCP server command or URL to inspect.")
    collect_mcp.add_argument(
        "--method",
        default="tools/list",
        help="MCP method to inspect, default: tools/list.",
    )
    collect_mcp.add_argument("--tool-name", help="Tool name for methods that require one.")
    collect_mcp.add_argument(
        "--command",
        dest="executable",
        default="mcp-inspector",
        help="MCP Inspector executable name or path.",
    )
    collect_mcp.add_argument(
        "--raw-out",
        help="Optional path to save raw MCP Inspector JSON output.",
    )
    collect_mcp.add_argument(
        "--experiment-id",
        help="Experiment id to attach to normalized observations. Defaults from server/method.",
    )
    collect_mcp.add_argument("--task-id", help="Optional task id to attach to observations.")
    collect_mcp.add_argument("--actor", help="Optional actor label to attach to observations.")
    collect_mcp.add_argument(
        "--json",
        action="store_true",
        help="Print normalized observations as machine-readable JSON.",
    )
    collect_mcp.add_argument(
        "--out",
        help="Path to write normalized observations JSON.",
    )

    collect_promptfoo = collect_subparsers.add_parser(
        "promptfoo",
        help="Run Promptfoo and normalize its JSON eval results.",
    )
    collect_promptfoo.add_argument("config", help="Path to a Promptfoo config file.")
    collect_promptfoo.add_argument(
        "--command",
        dest="executable",
        default="promptfoo",
        help="Promptfoo executable name or path.",
    )
    collect_promptfoo.add_argument(
        "--raw-out",
        required=True,
        help="Path to save raw Promptfoo JSON results.",
    )
    collect_promptfoo.add_argument(
        "--experiment-id",
        help="Experiment id to attach to normalized observations. Defaults to config stem.",
    )
    collect_promptfoo.add_argument("--task-id", help="Optional task id to attach to observations.")
    collect_promptfoo.add_argument("--actor", help="Optional actor label to attach to observations.")
    collect_promptfoo.add_argument(
        "--journey-stage",
        default="initial_value",
        help="FILLING stage to attach to Promptfoo observations. Default: initial_value.",
    )
    collect_promptfoo.add_argument(
        "--json",
        action="store_true",
        help="Print normalized observations as machine-readable JSON.",
    )
    collect_promptfoo.add_argument(
        "--out",
        help="Path to write normalized observations JSON.",
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


def dashboard_summary(
    runs_dir: str,
    eligible_count: int | None,
    filling_snapshot_path: str | None = None,
    compare_to_path: str | None = None,
) -> str:
    sections = []
    if filling_snapshot_path is not None:
        current_snapshot = load_filling_snapshot(filling_snapshot_path)
        sections.extend(["Funnelcake product dashboard", format_filling_snapshot(current_snapshot)])
        if compare_to_path is not None:
            comparison = compare_filling_snapshots(
                load_filling_snapshot(compare_to_path),
                current_snapshot,
            )
            sections.append(format_filling_comparison(comparison))

    runs = load_trial_runs_dir(runs_dir)
    if not runs:
        if sections:
            sections.append(f"No DESSERT diagnostic runs found in {runs_dir}")
            return "\n\n".join(sections)
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
    sections.append(
        "\n".join(
            [
                format_dashboard_overview(overview),
                "",
                "Artifacts",
                f"evaluations={evaluation_count}/{len(runs)}",
                f"diagnoses={diagnosis_count}/{len(runs)}",
            ]
        )
    )
    return "\n\n".join(sections)


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


def extract_observation_products(path: str, output_path: str) -> str:
    observation_set = load_observation_set(path)
    extracted = extract_product_mentions(observation_set)
    written_path = write_observation_set(extracted, output_path)
    mention_count = sum(len(observation.mentions) for observation in extracted.observations)
    return "\n".join(
        [
            f"extracted_observation_set={extracted.id}",
            f"observations={len(extracted.observations)}",
            f"mentions={mention_count}",
            f"output_path={written_path}",
        ]
    )


def run_observation_corpus(path: str, providers: str, repeat: int, output_path: str | None) -> str:
    provider_names = tuple(provider.strip() for provider in providers.split(",") if provider.strip())
    observation_set = run_provider_corpus(path, provider_names, repeat=repeat)
    extracted = extract_product_mentions(observation_set)
    final_output_path = output_path or str(Path("artifacts") / "geo" / f"{extracted.id}.json")
    written_path = write_observation_set(extracted, final_output_path)
    success_count = sum(1 for observation in extracted.observations if observation.success)
    failure_count = len(extracted.observations) - success_count
    return "\n".join(
        [
            f"run_observation_set={extracted.id}",
            f"providers={','.join(provider_names)}",
            f"repeat={repeat}",
            f"observations={len(extracted.observations)}",
            f"succeeded={success_count}",
            f"failed={failure_count}",
            f"output_path={written_path}",
        ]
    )


def run_observation_fixture(path: str, output_path: str) -> str:
    observation_set = run_fixture_provider(path)
    written_path = write_observation_set(observation_set, output_path)
    return "\n".join(
        [
            f"run_observation_set={observation_set.id}",
            f"provider={observation_set.attributes.get('provider', '')}",
            f"observations={len(observation_set.observations)}",
            f"output_path={written_path}",
        ]
    )


def run_observation_openai(path: str, output_path: str) -> str:
    observation_set = run_openai_provider(path)
    written_path = write_observation_set(observation_set, output_path)
    return "\n".join(
        [
            f"run_observation_set={observation_set.id}",
            f"provider={observation_set.attributes.get('provider', '')}",
            f"observations={len(observation_set.observations)}",
            f"output_path={written_path}",
        ]
    )


def run_observation_gemini(path: str, output_path: str) -> str:
    observation_set = run_gemini_provider(path)
    written_path = write_observation_set(observation_set, output_path)
    return "\n".join(
        [
            f"run_observation_set={observation_set.id}",
            f"provider={observation_set.attributes.get('provider', '')}",
            f"observations={len(observation_set.observations)}",
            f"output_path={written_path}",
        ]
    )


def run_observation_perplexity(path: str, output_path: str) -> str:
    observation_set = run_perplexity_provider(path)
    written_path = write_observation_set(observation_set, output_path)
    return "\n".join(
        [
            f"run_observation_set={observation_set.id}",
            f"provider={observation_set.attributes.get('provider', '')}",
            f"observations={len(observation_set.observations)}",
            f"output_path={written_path}",
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
    if args.geo_command == "report":
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
    if args.geo_command == "extract-products":
        return extract_observation_products(args.path, args.out)
    if args.geo_command == "run":
        return run_observation_corpus(args.path, args.providers, args.repeat, args.out)
    if args.geo_command == "run-fixture":
        return run_observation_fixture(args.path, args.out)
    if args.geo_command == "run-openai":
        return run_observation_openai(args.path, args.out)
    if args.geo_command == "run-gemini":
        return run_observation_gemini(args.path, args.out)
    if args.geo_command == "run-perplexity":
        return run_observation_perplexity(args.path, args.out)
    if args.geo_command == "compare":
        return compare_observations(args.baseline_path, args.followup_path, args.json)
    raise ValueError(f"unknown geo command: {args.geo_command}")


def telemetry_command(args: argparse.Namespace) -> str:
    if args.telemetry_command == "normalize":
        events = normalize_file(args.path, args.mapping, source=args.source)
        output_path = write_normalized_events(events, args.out)
        return "\n".join(
            [
                f"normalized_events={len(events)}",
                f"output_path={output_path}",
            ]
        )
    if args.telemetry_command == "inspect":
        return filling_snapshot_command(args.path, args.config, args.json, args.return_interval_days)
    raise ValueError(f"unknown telemetry command: {args.telemetry_command}")


def filling_command(args: argparse.Namespace) -> str:
    if args.filling_command == "snapshot":
        return filling_snapshot_command(args.path, args.config, args.json, output_path=args.out)
    if args.filling_command == "compare":
        return filling_compare_command(args.baseline_path, args.current_path, args.json)
    raise ValueError(f"unknown filling command: {args.filling_command}")


def filling_snapshot_command(
    path: str,
    config_path: str | None,
    json_output: bool,
    return_interval_days: int | None = None,
    output_path: str | None = None,
) -> str:
    events = load_normalized_events(path)
    config = load_product_funnel_config(config_path)
    if return_interval_days is not None and config_path is None:
        config = config.__class__(
            entity_id_field=config.entity_id_field,
            activation_events=config.activation_events,
            value_events=config.value_events,
            revenue_events=config.revenue_events,
            value_task_families=config.value_task_families,
            return_interval_days=return_interval_days,
            estimated_stage_counts=config.estimated_stage_counts,
            incompatible_transitions=config.incompatible_transitions,
        )
    snapshot = build_filling_snapshot(events, config)
    written_path = write_filling_snapshot(snapshot, output_path) if output_path is not None else None
    if json_output:
        payload = snapshot_to_dict(snapshot)
        if written_path is not None:
            payload["output_path"] = str(written_path)
        return json.dumps(payload, indent=2)
    lines = [format_filling_snapshot(snapshot)]
    if written_path is not None:
        lines.extend(["", f"output_path={written_path}"])
    return "\n".join(lines)


def filling_compare_command(
    baseline_path: str,
    current_path: str,
    json_output: bool,
) -> str:
    comparison = compare_filling_snapshots(
        load_filling_snapshot(baseline_path),
        load_filling_snapshot(current_path),
    )
    if json_output:
        return json.dumps(comparison_to_dict(comparison), indent=2)
    return format_filling_comparison(comparison)


def collect_command(args: argparse.Namespace) -> str:
    if args.collect_command == "run":
        return collect_run_command(
            args.collector,
            args.path,
            args.capability,
            args.experiment_id,
            args.task_id,
            args.actor,
            args.json,
            args.out,
        )
    if args.collect_command == "inspect":
        observations = load_observations(args.path)
        if args.json:
            return json.dumps(observations_to_dict(observations), indent=2)
        return format_observations(observations)
    if args.collect_command == "mcp-inspector":
        return collect_mcp_inspector_command(
            args.server,
            args.method,
            args.executable,
            args.tool_name,
            args.raw_out,
            args.experiment_id,
            args.task_id,
            args.actor,
            args.json,
            args.out,
        )
    if args.collect_command == "promptfoo":
        return collect_promptfoo_command(
            args.config,
            args.executable,
            args.raw_out,
            args.experiment_id,
            args.task_id,
            args.actor,
            args.journey_stage,
            args.json,
            args.out,
        )
    raise ValueError(f"unknown collect command: {args.collect_command}")


def collect_run_command(
    collector_id: str,
    path: str,
    capability: str | None,
    experiment_id: str | None,
    task_id: str | None,
    actor: str | None,
    json_output: bool,
    output_path: str | None,
) -> str:
    collector = get_collector(collector_id)
    experiment = Experiment(
        id=experiment_id or Path(path).stem,
        capability=_collector_capability(collector_id, capability),
        input_path=path,
        task_id=task_id,
        actor=actor,
    )
    observations = collector.collect(experiment)
    written_path = write_observations(observations, output_path) if output_path is not None else None
    if json_output:
        payload = observations_to_dict(observations)
        if written_path is not None:
            payload["output_path"] = str(written_path)
        return json.dumps(payload, indent=2)
    lines = [format_observations(observations)]
    if written_path is not None:
        lines.extend(["", f"output_path={written_path}"])
    return "\n".join(lines)


def collect_mcp_inspector_command(
    server: str,
    method: str,
    command: str,
    tool_name: str | None,
    raw_output_path: str | None,
    experiment_id: str | None,
    task_id: str | None,
    actor: str | None,
    json_output: bool,
    output_path: str | None,
) -> str:
    collector = MCPInspectorCollector()
    experiment = Experiment(
        id=experiment_id or f"mcp-{_slug(server)}-{_slug(method)}",
        capability=CollectorCapability.MCP_INSPECTION,
        task_id=task_id,
        actor=actor,
    )
    observations = collector.collect_from_server(
        experiment,
        server,
        method=method,
        command=command,
        tool_name=tool_name,
        raw_output_path=raw_output_path,
    )
    return _format_collect_output(observations, json_output, output_path)


def collect_promptfoo_command(
    config_path: str,
    command: str,
    raw_output_path: str,
    experiment_id: str | None,
    task_id: str | None,
    actor: str | None,
    journey_stage: str,
    json_output: bool,
    output_path: str | None,
) -> str:
    collector = PromptfooCollector()
    experiment = Experiment(
        id=experiment_id or Path(config_path).stem,
        capability=CollectorCapability.AGENT_EVALUATION,
        task_id=task_id,
        actor=actor,
        attributes={"journey_stage": journey_stage},
    )
    observations = collector.collect_from_config(
        experiment,
        config_path,
        command=command,
        raw_output_path=raw_output_path,
    )
    return _format_collect_output(observations, json_output, output_path)


def _format_collect_output(
    observations: tuple[object, ...],
    json_output: bool,
    output_path: str | None,
) -> str:
    written_path = write_observations(observations, output_path) if output_path is not None else None
    if json_output:
        payload = observations_to_dict(observations)
        if written_path is not None:
            payload["output_path"] = str(written_path)
        return json.dumps(payload, indent=2)
    lines = [format_observations(observations)]
    if written_path is not None:
        lines.extend(["", f"output_path={written_path}"])
    return "\n".join(lines)


def _collector_capability(collector_id: str, capability: str | None) -> CollectorCapability:
    if capability is not None:
        return CollectorCapability(capability)
    aliases = {
        "answer-observation": CollectorCapability.ANSWER_OBSERVATION,
        "native-answer-observation": CollectorCapability.ANSWER_OBSERVATION,
        "native.answer_observation": CollectorCapability.ANSWER_OBSERVATION,
        "mcp-inspector": CollectorCapability.MCP_INSPECTION,
        "external.mcp_inspector": CollectorCapability.MCP_INSPECTION,
        "promptfoo": CollectorCapability.AGENT_EVALUATION,
        "external.promptfoo": CollectorCapability.AGENT_EVALUATION,
    }
    try:
        return aliases[collector_id]
    except KeyError as exc:
        raise ValueError(f"--capability is required for collector {collector_id!r}") from exc


def _slug(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in slug.split("-") if part)[:48] or "unknown"


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

    try:
        if args.command in (None, "status"):
            print(status())
        elif args.command == "dashboard-demo":
            print(dashboard_demo())
        elif args.command == "dashboard-summary":
            print(
                dashboard_summary(
                    args.runs_dir,
                    args.eligible_count,
                    args.filling_snapshot,
                    args.compare_to,
                )
            )
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
        elif args.command == "extract-observation-products":
            print(extract_observation_products(args.path, args.out))
        elif args.command == "run-observation-fixture":
            print(run_observation_fixture(args.path, args.out))
        elif args.command == "run-observation-openai":
            print(run_observation_openai(args.path, args.out))
        elif args.command == "run-observation-gemini":
            print(run_observation_gemini(args.path, args.out))
        elif args.command == "run-observation-perplexity":
            print(run_observation_perplexity(args.path, args.out))
        elif args.command == "compare-observations":
            print(compare_observations(args.baseline_path, args.followup_path, args.json))
        elif args.command == "geo":
            if args.geo_command == "validate":
                print_observation_validation(args.path, args.json)
                return
            print(geo_command(args))
        elif args.command == "telemetry":
            print(telemetry_command(args))
        elif args.command == "filling":
            print(filling_command(args))
        elif args.command == "collect":
            print(collect_command(args))
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
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
