from __future__ import annotations

from pathlib import Path

from .models import FillingSnapshot


def filling_snapshot_to_prometheus(snapshot: FillingSnapshot) -> str:
    lines = [
        "# HELP funnelcake_filling_stage_count FILLING stage population count.",
        "# TYPE funnelcake_filling_stage_count gauge",
    ]
    for count in snapshot.stage_counts:
        if count.count is None:
            continue
        labels = _labels(
            stage=count.stage.value,
            evidence_kind=count.evidence_kind.value,
            source=count.source.value,
            quality=count.quality.value,
            status=count.status.value,
        )
        lines.append(f"funnelcake_filling_stage_count{{{labels}}} {_number(count.count)}")

    lines.extend(
        [
            "",
            "# HELP funnelcake_filling_transition_rate FILLING transition conversion rate as a 0..1 ratio.",
            "# TYPE funnelcake_filling_transition_rate gauge",
        ]
    )
    for transition in snapshot.transitions:
        if transition.conversion_rate is None:
            continue
        labels = _labels(
            transition=transition.transition_id,
            from_stage=transition.from_stage.value,
            to_stage=transition.to_stage.value,
            evidence_kind=transition.evidence_kind.value,
            source=transition.source.value,
            quality=transition.quality.value,
            status=transition.status.value,
        )
        lines.append(f"funnelcake_filling_transition_rate{{{labels}}} {_number(transition.conversion_rate / 100)}")

    lines.extend(
        [
            "",
            "# HELP funnelcake_filling_transition_numerator FILLING transition numerator.",
            "# TYPE funnelcake_filling_transition_numerator gauge",
        ]
    )
    for transition in snapshot.transitions:
        if transition.numerator is None:
            continue
        labels = _labels(
            transition=transition.transition_id,
            from_stage=transition.from_stage.value,
            to_stage=transition.to_stage.value,
            status=transition.status.value,
        )
        lines.append(f"funnelcake_filling_transition_numerator{{{labels}}} {_number(transition.numerator)}")

    lines.extend(
        [
            "",
            "# HELP funnelcake_filling_transition_denominator FILLING transition denominator.",
            "# TYPE funnelcake_filling_transition_denominator gauge",
        ]
    )
    for transition in snapshot.transitions:
        if transition.denominator is None:
            continue
        labels = _labels(
            transition=transition.transition_id,
            from_stage=transition.from_stage.value,
            to_stage=transition.to_stage.value,
            status=transition.status.value,
        )
        lines.append(f"funnelcake_filling_transition_denominator{{{labels}}} {_number(transition.denominator)}")

    return "\n".join(lines) + "\n"


def write_prometheus_metrics(metrics: str, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(metrics, encoding="utf-8")
    return output_path


def _labels(**labels: str) -> str:
    return ",".join(f'{key}="{_escape_label(value)}"' for key, value in labels.items())


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.12g}"
