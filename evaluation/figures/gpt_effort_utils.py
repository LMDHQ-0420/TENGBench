"""Shared real-result aggregation for GPT reasoning-effort figures."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from chart_utils import BLUE_DARK, CORAL, ORANGE, PURPLE, RESULT_ROOT, TEAL


MODELS = (
    ("gpt-5.2", "GPT-5.2", BLUE_DARK),
    ("gpt-5.5", "GPT-5.5", CORAL),
    ("gpt-5.6-luna", "GPT-5.6 Luna", PURPLE),
    ("gpt-5.6-terra", "GPT-5.6 Terra", TEAL),
    ("gpt-5.6-sol", "GPT-5.6 Sol", ORANGE),
)
EFFORTS = ("low", "mid", "max", "xhigh")
EFFORT_LABELS = ("Low", "Mid", "Max", "X-high")
LAYERS = ("L1", "L2", "L3")


def _read_score(path: Path) -> tuple[str, float] | None:
    """Return a normalized layer score from one persisted result file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    layer = str(data["layer"])
    evaluation = data.get("evaluation", {})
    if layer in {"L1", "L2"}:
        correct = evaluation.get("is_correct")
        if not isinstance(correct, bool):
            return None
        return layer, float(correct)
    if layer == "L3":
        result = evaluation.get("result")
        score = result.get("score") if isinstance(result, dict) else None
        if not isinstance(score, (int, float)):
            return None
        return layer, float(score)
    return None


def collect_effort_scores() -> tuple[
    dict[tuple[str, str, str], float], list[dict[str, str]], dict[str, int]
]:
    """Aggregate all complete GPT effort configurations from ``code/result``."""
    layer_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for model, _, _ in MODELS:
        for effort in EFFORTS:
            config_dir = RESULT_ROOT / f"{model}-{effort}"
            if not config_dir.is_dir():
                raise FileNotFoundError(f"Missing GPT result directory: {config_dir}")
            for path in config_dir.rglob("*.json"):
                parsed = _read_score(path)
                if parsed is None:
                    continue
                layer, score = parsed
                layer_values[(model, effort, layer)].append(score)

    expected_counts: dict[str, int] | None = None
    summary_rows: list[dict[str, str]] = []
    scores: dict[tuple[str, str, str], float] = {}
    for model, model_label, _ in MODELS:
        for effort in EFFORTS:
            current_counts = {
                layer: len(layer_values[(model, effort, layer)]) for layer in LAYERS
            }
            if expected_counts is None:
                expected_counts = current_counts
            elif current_counts != expected_counts:
                raise RuntimeError(
                    f"Incomplete GPT effort result set for {model}-{effort}: "
                    f"{current_counts} != {expected_counts}"
                )
            layer_means = {
                layer: float(np.mean(layer_values[(model, effort, layer)]))
                for layer in LAYERS
            }
            overall = float(np.mean([layer_means[layer] for layer in LAYERS]))
            for layer, value in layer_means.items():
                scores[(model, effort, layer)] = value
            scores[(model, effort, "Overall")] = overall
            summary_rows.append({
                "model": model,
                "model_label": model_label,
                "reasoning_effort": effort,
                "l1_score": f"{layer_means['L1']:.8f}",
                "l2_score": f"{layer_means['L2']:.8f}",
                "l3_score": f"{layer_means['L3']:.8f}",
                "overall_score": f"{overall:.8f}",
                "n_l1": str(current_counts["L1"]),
                "n_l2": str(current_counts["L2"]),
                "n_l3": str(current_counts["L3"]),
            })
    if expected_counts is None:
        raise RuntimeError("No GPT reasoning-effort results were found")
    return scores, summary_rows, expected_counts
