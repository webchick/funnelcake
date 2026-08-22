from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from funnelcake_discover_eval import (
    load_trial_run,
    send_run_to_otlp,
    trial_run_to_otlp_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    status = 202
    reason = "Accepted"

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class OtlpTests(unittest.TestCase):
    def test_otlp_json_preserves_required_funnelcake_attributes(self) -> None:
        run = load_trial_run(REPO_ROOT / "fixtures/runs/setup-auth-docs.json")
        payload = trial_run_to_otlp_json(run)

        resource_attributes = _attribute_map(
            payload["resourceSpans"][0]["resource"]["attributes"]
        )
        span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        span_attributes = _attribute_map(span["attributes"])
        event_attributes = _attribute_map(span["events"][0]["attributes"])

        self.assertEqual(resource_attributes["service.name"], "funnelcake")
        self.assertEqual(resource_attributes["funnelcake.trial.id"], "FC-0001")
        self.assertEqual(resource_attributes["funnelcake.stage"], "setup")
        self.assertEqual(resource_attributes["funnelcake.task.family"], "setup/auth-discovery")
        self.assertEqual(span["traceId"], "4bf92f3577b34da6a3ce929d0e0e0001")
        self.assertEqual(span["spanId"], "00f067aa0ba90001")
        self.assertEqual(span_attributes["service.name"], "funnelcake")
        self.assertEqual(span_attributes["funnelcake.actor"], "manual-capture-example")
        self.assertEqual(span_attributes["funnelcake.trial.id"], "FC-0001")
        self.assertEqual(span_attributes["funnelcake.stage"], "setup")
        self.assertEqual(span_attributes["funnelcake.task.family"], "setup/auth-discovery")
        self.assertEqual(event_attributes["funnelcake.event.id"], "event-fc-0001-search")
        self.assertEqual(event_attributes["funnelcake.event.type"], "search")

    def test_send_run_to_otlp_posts_json_payload(self) -> None:
        run = load_trial_run(REPO_ROOT / "fixtures/runs/setup-auth-docs.json")
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            result = send_run_to_otlp(
                run,
                "http://collector.example/v1/traces",
                api_key="secret",
                headers={"X-Scope-OrgID": "funnelcake"},
            )

        request = captured["request"]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(result["status"], 202)
        self.assertEqual(result["content_type"], "application/json")
        self.assertEqual(request.full_url, "http://collector.example/v1/traces")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(request.get_header("X-scope-orgid"), "funnelcake")
        self.assertEqual(body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"], run.trial.trace_id)
        self.assertEqual(captured["timeout"], 30)


def _attribute_map(attributes: list[dict[str, object]]) -> dict[str, object]:
    return {
        attribute["key"]: _any_value(attribute["value"])
        for attribute in attributes
    }


def _any_value(value: dict[str, object]) -> object:
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    return value


if __name__ == "__main__":
    unittest.main()
