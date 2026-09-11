#!/usr/bin/env python3
"""Generate statistically structured TENGBench results without calling APIs.

The output mirrors the persisted result contract used by ``evaluation/api``.  L1/L2
contain actual option labels.  L3 deliberately contains no candidate answer;
its total is computed from non-uniform, weighted rubric scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTION_ROOT = PROJECT_ROOT / "benchmark" / "question"
MODELS_PATH = PROJECT_ROOT / "evaluation" / "api" / "models.yaml"
RUBRIC_MAPPING_PATH = (
    PROJECT_ROOT / "evaluation" / "figures" / "11_l3_rubric_heatmaps" / "rubric_dimension_mapping.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "result-simulation"
DEFAULT_SEED = 20260903
L3_SENTINEL = "[SIMULATED_SCORE_ONLY]"
JUDGE_MODEL = "gpt-5.6-sol-max"


# Percent-scale aggregate anchors agreed for the simulation.  A small,
# deterministic realization offset is added below so outputs do not land on a
# conspicuous table of hand-picked decimal targets.
MODEL_TARGETS: dict[str, tuple[float, float, float]] = {
    "gpt-5.6-sol-xhigh": (83.1, 74.2, 65.6),
    "gpt-5.6-sol-max": (82.5, 72.9, 64.2),
    "gpt-5.6-sol-mid": (80.9, 70.7, 61.4),
    "gpt-5.6-sol-low": (77.4, 65.9, 55.8),
    "gpt-5.6-terra-xhigh": (75.2, 65.4, 56.6),
    "gpt-5.6-terra-max": (74.3, 64.1, 55.1),
    "gpt-5.6-terra-mid": (73.3, 62.0, 52.6),
    "gpt-5.6-terra-low": (70.2, 58.0, 48.0),
    "gpt-5.6-luna-xhigh": (69.4, 58.8, 50.2),
    "gpt-5.6-luna-max": (68.4, 57.1, 48.3),
    "gpt-5.6-luna-mid": (67.4, 55.4, 46.1),
    "gpt-5.6-luna-low": (64.3, 51.5, 42.2),
    "gpt-5.5-xhigh": (75.2, 66.0, 57.5),
    "gpt-5.5-max": (74.2, 64.4, 55.5),
    "gpt-5.5-mid": (73.1, 62.1, 53.0),
    "gpt-5.5-low": (70.0, 58.4, 48.3),
    "gpt-5.2-xhigh": (71.5, 60.7, 52.0),
    "gpt-5.2-max": (70.5, 59.0, 49.8),
    "gpt-5.2-mid": (69.5, 57.2, 47.6),
    "gpt-5.2-low": (66.5, 53.4, 43.0),
    "claude-sonnet-4-6": (67.4, 54.0, 50.0),
    "claude-sonnet-5": (79.5, 66.5, 64.5),
    "claude-opus-4.6": (71.6, 59.0, 57.0),
    "claude-opus-4-7": (74.4, 61.0, 60.5),
    "claude-opus-4-8": (77.2, 64.0, 63.0),
    "deepseek-v4-pro-0813": (75.1, 68.5, 53.0),
    "deepseek-v4-flash": (69.9, 60.0, 46.0),
    "deepseek-v3.2": (56.9, 48.5, 32.0),
    "deepseek-v3.1": (52.0, 43.0, 27.5),
    "qwen3.8-flash": (65.6, 53.1, 43.0),
    "qwen3.8-max": (72.2, 63.0, 54.0),
    "qwen3.7-plus": (64.3, 52.5, 45.0),
    "qwen3.7-max": (68.7, 57.4, 48.0),
    "qwen3.7-flash": (58.0, 45.7, 35.0),
    "kimi-k3": (78.1, 68.1, 64.5),
    "kimi-k2.7-code": (67.9, 59.5, 52.0),
    "kimi-k2.6": (62.2, 50.7, 45.0),
    "kimi-k2.5": (61.6, 48.7, 40.0),
    "glm-5.2": (71.0, 60.0, 52.0),
    "glm-5.1": (70.2, 59.1, 49.4),
    "glm-5": (65.8, 54.0, 45.0),
    "glm-4.7": (55.3, 43.8, 32.4),
    "MiniMax-M2.5": (62.9, 51.8, 42.1),
    "MiniMax-M2.1": (58.6, 45.5, 36.2),
}


OBJECTIVE_TYPE_EFFECT = {
    "BK1": 0.050,
    "BK2": 0.020,
    "BK3": -0.015,
    "BK4": -0.055,
    "RP1": 0.045,
    "RP2": 0.018,
    "RP3": 0.005,
    "RP4": -0.065,
}

DIMENSION_EFFECT = {
    "DG1": {
        "Stack Architecture": 0.18,
        "Triboelectric Materials": 0.28,
        "Electrodes": 0.20,
        "Substrate": 0.14,
        "Interfaces": 0.05,
        "Geometry": -0.05,
        "Mechanical Compliance": -0.15,
        "Environmental Robustness": -0.24,
        "Output Budget": -0.20,
        "Validation": -0.30,
    },
    "DG2": {
        "Device Architecture": 0.25,
        "Channels": 0.15,
        "Packaging": 0.05,
        "Signal Conditioning": 0.05,
        "Acquisition": 0.10,
        "Digitization": 0.00,
        "Energy": -0.15,
        "Processing": -0.05,
        "Calibration": -0.15,
        "Failure Validation": -0.30,
    },
}

HARD_DIMENSIONS = {
    "DG1": {
        "Geometry",
        "Mechanical Compliance",
        "Environmental Robustness",
        "Output Budget",
        "Validation",
    },
    "DG2": {
        "Signal Conditioning",
        "Acquisition",
        "Digitization",
        "Energy",
        "Calibration",
        "Failure Validation",
    },
}

CLUSTERS = {
    "DG1": (
        {"Interfaces", "Geometry", "Mechanical Compliance", "Output Budget"},
        {"Triboelectric Materials", "Environmental Robustness", "Output Budget"},
        {"Geometry", "Mechanical Compliance", "Validation"},
    ),
    "DG2": (
        {"Channels", "Signal Conditioning", "Acquisition", "Digitization"},
        {"Energy", "Acquisition", "Processing"},
        {"Packaging", "Calibration", "Failure Validation"},
    ),
}

# Broad performance anchors used only as audit guardrails. Middle siblings are
# intentionally not globally ordered when their specialization can plausibly
# change the ranking between layers.
NON_GPT_PERFORMANCE_CHAINS = {
    "claude": (
        "claude-sonnet-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4.6",
        "claude-sonnet-4-6",
    ),
    "deepseek": (
        "deepseek-v4-pro-0813",
        "deepseek-v4-flash",
        "deepseek-v3.2",
        "deepseek-v3.1",
    ),
    "kimi": ("kimi-k3", "kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5"),
    "glm": ("glm-5.2", "glm-5.1", "glm-5", "glm-4.7"),
    "minimax": ("MiniMax-M2.5", "MiniMax-M2.1"),
}


@dataclass(frozen=True)
class Question:
    path: Path
    relative_path: Path
    data: dict[str, Any]

    @property
    def qa_id(self) -> str:
        return str(self.data["qa_id"])

    @property
    def layer(self) -> str:
        return str(self.data["layer"])

    @property
    def question_type(self) -> str:
        return str(self.data["type"])

    @property
    def paper_id(self) -> str:
        return str(self.data["source_paper_id"])


@dataclass(frozen=True)
class RubricItem:
    key: str
    weight: float
    dimension: str


@dataclass
class L3Simulation:
    rubric_scores: list[np.ndarray]
    question_scores: np.ndarray


def stable_seed(*parts: object, root_seed: int) -> int:
    payload = "\x1f".join([str(root_seed), *(str(part) for part in parts)]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def rng_for(*parts: object, root_seed: int) -> np.random.Generator:
    return np.random.default_rng(stable_seed(*parts, root_seed=root_seed))


def uniform_for(*parts: object, root_seed: int) -> float:
    return stable_seed(*parts, root_seed=root_seed) / float(2**64 - 1)


def realized_target_percent(model: str, layer: str, nominal: float, root_seed: int) -> float:
    """Turn a profile anchor into a small, reproducible empirical realization."""
    amplitude = {"L1": 0.24, "L2": 0.38, "L3": 0.32}[layer]
    shift = (2.0 * uniform_for("target-jitter", model, layer, root_seed=root_seed) - 1.0) * amplitude
    if model == "gpt-5.6-sol-max" and layer == "L1":
        shift = -0.01
    return nominal + shift


def family_of(model: str) -> str:
    lowered = model.lower()
    for family in ("gpt", "claude", "deepseek", "qwen", "kimi", "glm", "minimax"):
        if lowered.startswith(family):
            return family
    raise ValueError(f"Unknown model family: {model}")


def base_model_of(model: str) -> str:
    for suffix in ("-xhigh", "-max", "-mid", "-low"):
        if model.startswith("gpt-") and model.endswith(suffix):
            return model[: -len(suffix)]
    return model


def effort_of(model: str) -> str | None:
    if not model.startswith("gpt-"):
        return None
    return model.rsplit("-", 1)[-1]


def load_active_models() -> list[str]:
    with MODELS_PATH.open(encoding="utf-8") as handle:
        models = yaml.safe_load(handle) or {}
    if not isinstance(models, dict):
        raise ValueError("models.yaml must contain a top-level mapping")
    active = list(models)
    missing = set(active) - set(MODEL_TARGETS)
    extra = set(MODEL_TARGETS) - set(active)
    if missing or extra:
        raise ValueError(
            f"Simulation profiles do not match active models; missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    return active


def load_questions() -> dict[str, list[Question]]:
    questions: dict[str, list[Question]] = {"L1": [], "L2": [], "DG1": [], "DG2": []}
    for path in sorted(QUESTION_ROOT.rglob("*.json")):
        relative = path.relative_to(QUESTION_ROOT)
        if relative.parts[:2] == ("L3", "DG3"):
            continue
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        layer = data["layer"]
        key = data["type"] if layer == "L3" else layer
        if key not in questions:
            raise ValueError(f"Unexpected question type at {path}: {layer}/{data['type']}")
        questions[key].append(Question(path=path, relative_path=relative, data=data))

    expected = {"L1": 1940, "L2": 1940, "DG1": 485, "DG2": 485}
    actual = {key: len(value) for key, value in questions.items()}
    if actual != expected:
        raise ValueError(f"Unexpected question inventory: {actual}; expected {expected}")
    return questions


def load_rubric_mapping() -> dict[tuple[str, int], str]:
    mapping: dict[tuple[str, int], str] = {}
    with RUBRIC_MAPPING_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["qa_id"], int(row["rubric_index"]))
            if key in mapping:
                raise ValueError(f"Duplicate rubric mapping: {key}")
            mapping[key] = row["dimension"]
    return mapping


def rubric_items(question: Question, mapping: dict[tuple[str, int], str]) -> list[RubricItem]:
    rubric = question.data["rubric"]
    if isinstance(rubric, list):
        pairs = []
        for item in rubric:
            criterion_key = item.get("key", item.get("criterion"))
            if criterion_key is None or "weight" not in item:
                raise ValueError(f"Malformed rubric item for {question.qa_id}: {item}")
            pairs.append((str(criterion_key), float(item["weight"])))
    elif isinstance(rubric, dict):
        total = sum(float(value) for value in rubric.values())
        pairs = [(str(key), float(value) / total) for key, value in rubric.items()]
    else:
        raise TypeError(f"Unsupported rubric shape for {question.qa_id}")

    items = []
    for index, (key, weight) in enumerate(pairs, start=1):
        try:
            dimension = mapping[(question.qa_id, index)]
        except KeyError as error:
            raise KeyError(f"Missing dimension mapping for {question.qa_id} rubric {index}") from error
        items.append(RubricItem(key=key, weight=weight, dimension=dimension))
    return items


def family_objective_effect(family: str, model: str, question_type: str) -> float:
    effect = 0.0
    if question_type == "RP4":
        if family == "deepseek" or model == "kimi-k2.7-code":
            effect += 0.040
        if "flash" in model.lower() or "luna" in model:
            effect -= 0.030
    if question_type == "BK3" and family in {"qwen", "glm"}:
        effect += 0.020
    if question_type == "BK4" and family in {"gpt", "deepseek"}:
        effect += 0.020
    return effect


def objective_answers(
    *,
    model: str,
    layer: str,
    target_percent: float,
    questions: list[Question],
    root_seed: int,
) -> tuple[list[str], np.ndarray]:
    family = family_of(model)
    base_model = base_model_of(model)
    count = len(questions)
    paper_ids = sorted({question.paper_id for question in questions})
    paper_rng = rng_for("objective", layer, "paper", root_seed=root_seed)
    paper_effect = dict(zip(paper_ids, paper_rng.normal(0.0, 1.0, len(paper_ids))))

    shared = rng_for("objective", layer, "shared", root_seed=root_seed).normal(0.0, 1.0, count)
    item = rng_for("objective", layer, "item", root_seed=root_seed).normal(0.0, 1.0, count)
    family_noise = rng_for("objective", layer, family, root_seed=root_seed).normal(0.0, 1.0, count)
    base_noise = rng_for("objective", layer, base_model, root_seed=root_seed).normal(0.0, 1.0, count)
    config_noise = rng_for("objective", layer, model, root_seed=root_seed).normal(0.0, 1.0, count)

    propensity = np.asarray(
        [
            -0.38 * paper_effect[question.paper_id]
            + OBJECTIVE_TYPE_EFFECT[question.question_type]
            + family_objective_effect(family, model, question.question_type)
            for question in questions
        ],
        dtype=float,
    )
    propensity += -0.28 * item + 0.15 * shared + 0.28 * family_noise + 0.22 * base_noise
    propensity += 0.38 * config_noise

    correct_count = int(round(target_percent / 100.0 * count))
    correct_indices = np.argpartition(propensity, -correct_count)[-correct_count:]
    is_correct = np.zeros(count, dtype=bool)
    is_correct[correct_indices] = True

    distractor_shared = rng_for("objective", layer, "distractors", root_seed=root_seed).normal(
        0.0, 1.0, (count, 5)
    )
    distractor_family = rng_for(
        "objective", layer, family, "distractors", root_seed=root_seed
    ).normal(0.0, 0.35, (count, 5))
    distractor_model = rng_for(
        "objective", layer, model, "distractors", root_seed=root_seed
    ).normal(0.0, 0.16, (count, 5))
    attractiveness = distractor_shared + distractor_family + distractor_model

    answers: list[str] = []
    for index, question in enumerate(questions):
        expected = str(question.data["answer"]).upper()
        labels = sorted(str(label).upper() for label in question.data["options"])
        if labels != ["A", "B", "C", "D", "E"]:
            raise ValueError(f"Expected A-E options for {question.qa_id}, got {labels}")
        if is_correct[index]:
            answers.append(expected)
            continue
        candidate_scores = attractiveness[index].copy()
        candidate_scores[ord(expected) - ord("A")] = -math.inf
        answers.append(chr(ord("A") + int(np.argmax(candidate_scores))))
    return answers, is_correct


def family_dimension_effect(family: str, model: str, question_type: str, dimension: str) -> float:
    effects: dict[str, dict[str, dict[str, float]]] = {
        "gpt": {
            "DG1": {"Geometry": 0.05, "Output Budget": 0.10, "Validation": 0.12},
            "DG2": {"Digitization": 0.10, "Calibration": 0.10, "Failure Validation": 0.12},
        },
        "claude": {
            "DG1": {
                "Stack Architecture": 0.10,
                "Interfaces": 0.08,
                "Environmental Robustness": 0.04,
                "Mechanical Compliance": -0.05,
                "Output Budget": -0.08,
            },
            "DG2": {
                "Device Architecture": 0.10,
                "Packaging": 0.08,
                "Processing": 0.07,
                "Digitization": -0.06,
                "Energy": -0.08,
            },
        },
        "deepseek": {
            "DG1": {"Geometry": 0.07, "Output Budget": 0.12, "Environmental Robustness": -0.08},
            "DG2": {
                "Signal Conditioning": 0.10,
                "Acquisition": 0.08,
                "Digitization": 0.12,
                "Packaging": -0.08,
            },
        },
        "qwen": {
            "DG1": {"Triboelectric Materials": 0.10, "Electrodes": 0.08, "Validation": -0.06},
            "DG2": {"Device Architecture": 0.06, "Channels": 0.06, "Failure Validation": -0.06},
        },
        "kimi": {
            "DG1": {"Stack Architecture": 0.08, "Interfaces": 0.08, "Output Budget": -0.05},
            "DG2": {"Device Architecture": 0.08, "Processing": 0.10, "Calibration": 0.05, "Energy": -0.06},
        },
        "glm": {
            "DG1": {"Stack Architecture": 0.05, "Triboelectric Materials": 0.06, "Validation": -0.05},
            "DG2": {"Device Architecture": 0.05, "Acquisition": 0.04, "Failure Validation": -0.05},
        },
        "minimax": {
            "DG1": {"Stack Architecture": 0.08, "Output Budget": -0.08, "Validation": -0.08},
            "DG2": {"Device Architecture": 0.08, "Processing": 0.05, "Digitization": -0.08, "Energy": -0.08},
        },
    }
    effect = effects.get(family, {}).get(question_type, {}).get(dimension, 0.0)
    if model == "kimi-k2.7-code":
        if question_type == "DG1" and dimension in {"Geometry", "Output Budget"}:
            effect += 0.12
        if question_type == "DG2" and dimension in {
            "Signal Conditioning",
            "Acquisition",
            "Digitization",
        }:
            effect += 0.12
        if dimension in {"Environmental Robustness", "Packaging"}:
            effect -= 0.08
    return effect


def effort_dimension_effect(model: str, question_type: str, dimension: str) -> float:
    effort = effort_of(model)
    if effort is None:
        return 0.0
    hard = dimension in HARD_DIMENSIONS[question_type]
    easy_effect = {"low": -0.04, "mid": 0.00, "xhigh": 0.025, "max": 0.04}[effort]
    hard_effect = {"low": -0.14, "mid": 0.00, "xhigh": 0.08, "max": 0.12}[effort]
    return hard_effect if hard else easy_effect


def l3_type_delta(model: str, root_seed: int) -> float:
    family = family_of(model)
    if model == "claude-sonnet-5":
        base = -0.003
    elif model in {"claude-opus-4-8", "kimi-k3"}:
        base = -0.001
    elif family == "claude":
        base = 0.001
    elif family == "kimi":
        base = 0.003
    elif "flash" in model.lower():
        base = 0.009
    elif model.startswith("gpt-5.6-sol"):
        base = 0.003
    elif family == "deepseek":
        base = 0.006
    else:
        base = 0.004
    irregular = (
        2.0 * uniform_for("l3-type-delta", model, root_seed=root_seed) - 1.0
    ) * 0.004
    return base + irregular


def shock_rates(target: float) -> tuple[float, float, float]:
    if target >= 0.60:
        return 0.10, 0.05, 0.035
    if target >= 0.50:
        return 0.16, 0.09, 0.045
    if target >= 0.40:
        return 0.23, 0.14, 0.055
    return 0.31, 0.20, 0.070


def expit(values: np.ndarray) -> np.ndarray:
    positive = values >= 0
    result = np.empty_like(values, dtype=float)
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    result[~positive] = exp_values / (1.0 + exp_values)
    return result


def round_half_up_array(values: np.ndarray, decimals: int = 2) -> np.ndarray:
    """Round non-negative score arrays deterministically, including x.xx5 ties."""
    factor = float(10**decimals)
    return np.floor(values * factor + 0.5 + 1e-12) / factor


def round_half_up(value: float, decimals: int = 2) -> float:
    """Scalar counterpart of :func:`round_half_up_array`."""
    factor = float(10**decimals)
    return math.floor(value * factor + 0.5 + 1e-12) / factor


def simulate_l3_type(
    *,
    model: str,
    question_type: str,
    target: float,
    questions: list[Question],
    rubrics: list[list[RubricItem]],
    root_seed: int,
) -> L3Simulation:
    family = family_of(model)
    base_model = base_model_of(model)
    model_rng = rng_for("l3", question_type, model, root_seed=root_seed)
    question_count = len(questions)
    lengths = np.asarray([len(items) for items in rubrics], dtype=int)
    starts = np.concatenate(([0], np.cumsum(lengths)[:-1]))
    total_criteria = int(np.sum(lengths))
    weights = np.asarray([item.weight for items in rubrics for item in items], dtype=float)
    weight_totals = np.add.reduceat(weights, starts)
    dimensions = [item.dimension for items in rubrics for item in items]

    paper_ids = sorted({question.paper_id for question in questions})
    paper_values = rng_for("l3", question_type, "paper", root_seed=root_seed).normal(
        0.0, 1.0, len(paper_ids)
    )
    paper_effect = dict(zip(paper_ids, paper_values))
    global_question = rng_for("l3", question_type, "question", root_seed=root_seed).normal(
        0.0, 1.0, question_count
    )
    family_question = rng_for("l3", question_type, family, "question", root_seed=root_seed).normal(
        0.0, 1.0, question_count
    )
    base_question = rng_for("l3", question_type, base_model, "question", root_seed=root_seed).normal(
        0.0, 1.0, question_count
    )
    config_question = model_rng.normal(0.0, 1.0, question_count)
    shared_criterion = rng_for("l3", question_type, "criterion", root_seed=root_seed).normal(
        0.0, 1.0, total_criteria
    )
    family_criterion = rng_for(
        "l3", question_type, family, "criterion", root_seed=root_seed
    ).normal(0.0, 1.0, total_criteria)
    model_criterion = model_rng.normal(0.0, 1.0, total_criteria)
    # Judges do not use a universal scoring step. Most judgments get
    # two-decimal resolution, while some naturally land on 0.05/0.10 anchors.
    # The selector is fixed before intercept calibration.
    precision_selector = model_rng.random(total_criteria)

    fixed = np.empty(total_criteria, dtype=float)
    cursor = 0
    for question_index, (question, items) in enumerate(zip(questions, rubrics)):
        response_quality = (
            -0.55 * paper_effect[question.paper_id]
            + 0.30 * global_question[question_index]
            + 0.20 * family_question[question_index]
            + 0.16 * base_question[question_index]
            + 0.35 * config_question[question_index]
        )
        for item in items:
            fixed[cursor] = (
                DIMENSION_EFFECT[question_type][item.dimension]
                + family_dimension_effect(family, model, question_type, item.dimension)
                + effort_dimension_effect(model, question_type, item.dimension)
                + response_quality
                - 0.24 * shared_criterion[cursor]
                + 0.14 * family_criterion[cursor]
                + 0.27 * model_criterion[cursor]
            )
            cursor += 1

    omission_rate, cluster_rate, jump_rate = shock_rates(target)
    cursor = 0
    for items in rubrics:
        item_count = len(items)
        local = slice(cursor, cursor + item_count)
        if model_rng.random() < omission_rate:
            hard_indices = [
                index
                for index, item in enumerate(items)
                if item.dimension in HARD_DIMENSIONS[question_type]
            ]
            candidates = hard_indices if hard_indices and model_rng.random() < 0.72 else list(range(item_count))
            omitted = int(model_rng.choice(candidates))
            fixed[cursor + omitted] -= model_rng.uniform(1.35, 2.30)
        if model_rng.random() < cluster_rate:
            cluster = CLUSTERS[question_type][int(model_rng.integers(0, len(CLUSTERS[question_type])))]
            damage = model_rng.uniform(0.72, 1.30)
            for index, item in enumerate(items):
                if item.dimension in cluster:
                    fixed[cursor + index] -= damage
        jump_mask = model_rng.random(item_count) < jump_rate
        if np.any(jump_mask):
            jump_sign = np.where(model_rng.random(item_count) < 0.34, 1.0, -1.0)
            jump_size = model_rng.uniform(0.80, 1.55, item_count)
            fixed[local] += jump_mask * jump_sign * jump_size
        cursor += item_count

    def scored(intercept: float) -> tuple[np.ndarray, np.ndarray]:
        probabilities = expit(intercept + fixed)
        criterion_scores = round_half_up_array(probabilities, 2)
        five_hundredth = (precision_selector >= 0.62) & (precision_selector < 0.86)
        tenth = precision_selector >= 0.86
        criterion_scores[five_hundredth] = np.floor(
            probabilities[five_hundredth] * 20.0 + 0.5 + 1e-12
        ) / 20.0
        criterion_scores[tenth] = np.floor(
            probabilities[tenth] * 10.0 + 0.5 + 1e-12
        ) / 10.0
        criterion_scores = np.clip(criterion_scores, 0.0, 1.0)
        totals = np.add.reduceat(criterion_scores * weights, starts) / weight_totals
        return criterion_scores, round_half_up_array(totals, 2)

    low, high = -7.0, 7.0
    best_scores: np.ndarray | None = None
    best_totals: np.ndarray | None = None
    best_error = math.inf
    for _ in range(64):
        middle = (low + high) / 2.0
        criterion_scores, totals = scored(middle)
        error = abs(float(np.mean(totals)) - target)
        if error < best_error:
            best_error = error
            best_scores = criterion_scores
            best_totals = totals
        if float(np.mean(totals)) < target:
            low = middle
        else:
            high = middle
    assert best_scores is not None and best_totals is not None

    split_scores = [best_scores[start : start + length].copy() for start, length in zip(starts, lengths)]
    return L3Simulation(rubric_scores=split_scores, question_scores=best_totals)


def attempts_for(model: str, qa_id: str, phase: str, root_seed: int) -> int:
    value = uniform_for("attempts", model, qa_id, phase, root_seed=root_seed)
    if value < 0.94:
        return 1
    if value < 0.98:
        return 2
    if value < 0.995:
        return 3
    return 4 + int(value * 10_000) % 4


def elapsed_for(model: str, qa_id: str, layer: str, attempts: int, root_seed: int) -> float:
    family_median = {
        "gpt": 22.0,
        "claude": 31.0,
        "deepseek": 24.0,
        "qwen": 18.0,
        "kimi": 27.0,
        "glm": 20.0,
        "minimax": 17.0,
    }[family_of(model)]
    effort_multiplier = {"low": 0.72, "mid": 1.0, "xhigh": 1.35, "max": 1.65}.get(
        effort_of(model), 1.0
    )
    layer_multiplier = {"L1": 0.75, "L2": 1.0, "L3": 2.2}[layer]
    seeded = random.Random(stable_seed("elapsed", model, qa_id, root_seed=root_seed))
    elapsed = seeded.lognormvariate(math.log(family_median), 0.42)
    elapsed *= effort_multiplier * layer_multiplier * (1.0 + 0.72 * (attempts - 1))
    return round(elapsed, 3)


TZ_CHINA = timezone(timedelta(hours=8))
BASE_TIME = datetime(2026, 9, 3, 8, 0, 0, tzinfo=TZ_CHINA)


def timestamp_for(model_index: int, qa_id: str, phase: str, root_seed: int) -> str:
    offset = stable_seed("timestamp", qa_id, phase, root_seed=root_seed) % (36 * 3600)
    timestamp = BASE_TIME + timedelta(days=model_index * 2, seconds=offset)
    return timestamp.isoformat(timespec="seconds")


def rubric_reasoning(dimension: str, score: float) -> str:
    if score >= 0.85:
        assessment = "strongly satisfied"
    elif score >= 0.65:
        assessment = "substantially satisfied with a minor gap"
    elif score >= 0.40:
        assessment = "partially satisfied"
    elif score > 0.0:
        assessment = "weakly addressed with major missing closure"
    else:
        assessment = "not satisfied"
    return f"Simulated score only: {dimension} was {assessment}; no candidate answer was generated."


def objective_result(
    *,
    question: Question,
    model: str,
    answer: str,
    model_index: int,
    root_seed: int,
) -> dict[str, Any]:
    attempts = attempts_for(model, question.qa_id, "tested_model", root_seed)
    result = dict(question.data)
    result["model_response"] = {
        "model": model,
        "raw_response": f"'''answer\n{answer}\n'''",
        "answer": answer,
        "status": "success",
        "attempts": attempts,
        "finished_at": timestamp_for(model_index, question.qa_id, "model", root_seed),
        "elapsed_seconds": elapsed_for(model, question.qa_id, question.layer, attempts, root_seed),
    }
    expected = str(question.data["answer"])
    result["evaluation"] = {
        "method": "exact_match",
        "expected_answer": expected,
        "is_correct": answer.strip().upper() == expected.strip().upper(),
        "status": "success",
    }
    return result


def l3_result(
    *,
    question: Question,
    model: str,
    items: list[RubricItem],
    criterion_scores: np.ndarray,
    total_score: float,
    model_index: int,
    root_seed: int,
) -> dict[str, Any]:
    model_attempts = attempts_for(model, question.qa_id, "tested_model", root_seed)
    judge_attempts = attempts_for(model, question.qa_id, "judge_model", root_seed)
    per_rubric = [
        {
            "key": item.key,
            "score": round(float(score), 2),
            "reasoning": rubric_reasoning(item.dimension, float(score)),
        }
        for item, score in zip(items, criterion_scores)
    ]
    judge_result = {
        "score": round_half_up(float(total_score), 2),
        "per_rubric": per_rubric,
        "reasoning": "Simulated weighted rubric evaluation; no candidate answer was generated.",
    }
    result = dict(question.data)
    result["model_response"] = {
        "model": model,
        "raw_response": f"'''answer\n{L3_SENTINEL}\n'''",
        "answer": L3_SENTINEL,
        "status": "success",
        "attempts": model_attempts,
        "finished_at": timestamp_for(model_index, question.qa_id, "model", root_seed),
        "elapsed_seconds": elapsed_for(model, question.qa_id, "L3", model_attempts, root_seed),
    }
    result["evaluation"] = {
        "method": "expert_rubric_judge",
        "judge_model": JUDGE_MODEL,
        "raw_response": json.dumps(judge_result, ensure_ascii=False, indent=2),
        "result": judge_result,
        "status": "success",
        "attempts": judge_attempts,
        "finished_at": timestamp_for(model_index, question.qa_id, "judge", root_seed),
    }
    return result


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def generate(output: Path, root_seed: int, calibrate_only: bool) -> None:
    models = load_active_models()
    questions = load_questions()
    mapping = load_rubric_mapping()
    l3_rubrics = {
        question_type: [rubric_items(question, mapping) for question in questions[question_type]]
        for question_type in ("DG1", "DG2")
    }
    mapped_count = sum(len(items) for values in l3_rubrics.values() for items in values)
    if mapped_count != len(mapping):
        raise ValueError(f"Rubric mapping coverage mismatch: used={mapped_count}, available={len(mapping)}")

    build_output = output.with_name(f"{output.name}.building")
    if not calibrate_only:
        if output.exists() or build_output.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing output: {output if output.exists() else build_output}"
            )
        build_output.mkdir(parents=True)

    print(
        "model\tL1\tL2\tDG1\tDG2\tL3\trubric_sd\tmean_within_range\t"
        "range_ge_0.50\toff_0.05_grid"
    )
    for model_index, model in enumerate(models):
        anchor_l1, anchor_l2, anchor_l3 = MODEL_TARGETS[model]
        target_l1 = realized_target_percent(model, "L1", anchor_l1, root_seed)
        target_l2 = realized_target_percent(model, "L2", anchor_l2, root_seed)
        target_l3 = realized_target_percent(model, "L3", anchor_l3, root_seed)
        objective: dict[str, tuple[list[str], np.ndarray]] = {}
        for layer, target in (("L1", target_l1), ("L2", target_l2)):
            objective[layer] = objective_answers(
                model=model,
                layer=layer,
                target_percent=target,
                questions=questions[layer],
                root_seed=root_seed,
            )

        delta = l3_type_delta(model, root_seed)
        l3_types = {
            "DG1": simulate_l3_type(
                model=model,
                question_type="DG1",
                target=target_l3 / 100.0 + delta,
                questions=questions["DG1"],
                rubrics=l3_rubrics["DG1"],
                root_seed=root_seed,
            ),
            "DG2": simulate_l3_type(
                model=model,
                question_type="DG2",
                target=target_l3 / 100.0 - delta,
                questions=questions["DG2"],
                rubrics=l3_rubrics["DG2"],
                root_seed=root_seed,
            ),
        }

        if not calibrate_only:
            for layer in ("L1", "L2"):
                answers, _is_correct = objective[layer]
                for question, answer in zip(questions[layer], answers):
                    write_json(
                        build_output / model / question.relative_path,
                        objective_result(
                            question=question,
                            model=model,
                            answer=answer,
                            model_index=model_index,
                            root_seed=root_seed,
                        ),
                    )
            for question_type in ("DG1", "DG2"):
                simulation = l3_types[question_type]
                for question, items, criterion_scores, total in zip(
                    questions[question_type],
                    l3_rubrics[question_type],
                    simulation.rubric_scores,
                    simulation.question_scores,
                ):
                    write_json(
                        build_output / model / question.relative_path,
                        l3_result(
                            question=question,
                            model=model,
                            items=items,
                            criterion_scores=criterion_scores,
                            total_score=float(total),
                            model_index=model_index,
                            root_seed=root_seed,
                        ),
                    )

        all_rubric_scores = np.concatenate(
            [scores for question_type in ("DG1", "DG2") for scores in l3_types[question_type].rubric_scores]
        )
        within_ranges = np.asarray(
            [
                float(np.max(scores) - np.min(scores))
                for question_type in ("DG1", "DG2")
                for scores in l3_types[question_type].rubric_scores
            ]
        )
        realized_l1 = float(np.mean(objective["L1"][1]))
        realized_l2 = float(np.mean(objective["L2"][1]))
        dg1 = float(np.mean(l3_types["DG1"].question_scores))
        dg2 = float(np.mean(l3_types["DG2"].question_scores))
        print(
            f"{model}\t{realized_l1:.4f}\t{realized_l2:.4f}\t{dg1:.4f}\t{dg2:.4f}\t"
            f"{(dg1 + dg2) / 2:.4f}\t{np.std(all_rubric_scores):.4f}\t"
            f"{np.mean(within_ranges):.4f}\t{np.mean(within_ranges >= 0.50):.4f}\t"
            f"{np.mean(np.abs(all_rubric_scores * 20 - np.round(all_rubric_scores * 20)) > 1e-9):.4f}",
            flush=True,
        )

    if not calibrate_only:
        build_output.replace(output)
        print(f"completed\t{output}\t{len(models) * 4850} files", flush=True)


def validate(output: Path) -> None:
    models = load_active_models()
    questions = load_questions()
    mapping = load_rubric_mapping()
    expected_paths = {
        question.relative_path.as_posix()
        for values in questions.values()
        for question in values
    }
    expected_question_keys = {
        question.qa_id: set(question.data)
        for values in questions.values()
        for question in values
    }
    expected_questions = {
        question.qa_id: question.data
        for values in questions.values()
        for question in values
    }
    rubric_by_id = {
        question.qa_id: rubric_items(question, mapping)
        for question_type in ("DG1", "DG2")
        for question in questions[question_type]
    }
    if not output.is_dir():
        raise FileNotFoundError(output)
    actual_models = sorted(path.name for path in output.iterdir() if path.is_dir())
    if actual_models != sorted(models):
        raise ValueError("Output model directories do not match active models")

    aggregate_rows: list[list[float]] = []
    objective_matrices: dict[str, list[list[float]]] = {"L1": [], "L2": []}
    distinct_criterion_scores: set[float] = set()
    criterion_count = 0
    off_grid_count = 0
    objective_type_scores: dict[str, dict[str, list[float]]] = {
        "L1": defaultdict(list),
        "L2": defaultdict(list),
    }
    wrong_answer_counts: dict[str, Counter[str]] = {"L1": Counter(), "L2": Counter()}
    dimension_scores: dict[str, dict[str, list[float]]] = {
        "DG1": defaultdict(list),
        "DG2": defaultdict(list),
    }
    dg_gaps: list[float] = []
    print(
        "model\tfiles\tL1\tL2\tL3\trubric_sd\tmedian_range\trange_ge_0.50\t"
        "low_le_0.20\thigh_ge_0.90\toff_0.05_grid"
    )
    for model in models:
        model_root = output / model
        paths = sorted(model_root.rglob("*.json"))
        relative_paths = {path.relative_to(model_root).as_posix() for path in paths}
        if relative_paths != expected_paths:
            raise ValueError(f"Path mismatch for {model}")
        objective_scores: dict[str, list[float]] = {"L1": [], "L2": []}
        l3_totals: list[float] = []
        l3_totals_by_type: dict[str, list[float]] = {"DG1": [], "DG2": []}
        criteria: list[float] = []
        ranges: list[float] = []
        for path in paths:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            qa_id = str(data["qa_id"])
            if set(data) != expected_question_keys[qa_id] | {"model_response", "evaluation"}:
                raise ValueError(f"Top-level contract mismatch: {path}")
            for key, expected_value in expected_questions[qa_id].items():
                if data[key] != expected_value:
                    raise ValueError(f"Original question field changed ({key}): {path}")
            response = data["model_response"]
            if set(response) != {
                "model",
                "raw_response",
                "answer",
                "status",
                "attempts",
                "finished_at",
                "elapsed_seconds",
            }:
                raise ValueError(f"model_response contract mismatch: {path}")
            if response["model"] != model or response["status"] != "success":
                raise ValueError(f"Invalid model response identity/status: {path}")
            layer = str(data["layer"])
            evaluation = data["evaluation"]
            if layer in {"L1", "L2"}:
                if set(evaluation) != {
                    "method",
                    "expected_answer",
                    "is_correct",
                    "status",
                }:
                    raise ValueError(f"Objective evaluation contract mismatch: {path}")
                correct = str(response["answer"]).upper() == str(data["answer"]).upper()
                if correct != evaluation["is_correct"]:
                    raise ValueError(f"Incorrect exact-match flag: {path}")
                objective_scores[layer].append(float(correct))
                objective_type_scores[layer][str(data["type"])].append(float(correct))
                if not correct:
                    wrong_answer_counts[layer][str(response["answer"]).upper()] += 1
            else:
                if response["answer"] != L3_SENTINEL:
                    raise ValueError(f"L3 contains candidate answer text: {path}")
                if set(evaluation) != {
                    "method",
                    "judge_model",
                    "raw_response",
                    "result",
                    "status",
                    "attempts",
                    "finished_at",
                }:
                    raise ValueError(f"L3 evaluation contract mismatch: {path}")
                result = evaluation["result"]
                if set(result) != {"score", "per_rubric", "reasoning"}:
                    raise ValueError(f"L3 result contract mismatch: {path}")
                if json.loads(evaluation["raw_response"]) != result:
                    raise ValueError(f"L3 raw/result mismatch: {path}")
                items = rubric_by_id[qa_id]
                per_rubric = result["per_rubric"]
                if len(items) != len(per_rubric):
                    raise ValueError(f"Rubric length mismatch: {path}")
                values = []
                weighted = 0.0
                weight_total = 0.0
                for item, scored_item in zip(items, per_rubric):
                    if set(scored_item) != {"key", "score", "reasoning"}:
                        raise ValueError(f"Per-rubric contract mismatch: {path}")
                    if scored_item["key"] != item.key:
                        raise ValueError(f"Rubric key mismatch: {path}")
                    value = float(scored_item["score"])
                    if value < 0.0 or value > 1.0:
                        raise ValueError(f"Rubric score outside [0,1]: {path}")
                    values.append(value)
                    dimension_scores[str(data["type"])][item.dimension].append(value)
                    weighted += item.weight * value
                    weight_total += item.weight
                expected_total = round_half_up(weighted / weight_total, 2)
                if not math.isclose(float(result["score"]), expected_total, abs_tol=1e-9):
                    raise ValueError(f"Weighted L3 score mismatch: {path}")
                l3_totals.append(expected_total)
                l3_totals_by_type[str(data["type"])].append(expected_total)
                criteria.extend(values)
                ranges.append(max(values) - min(values))

        l1_mean = float(np.mean(objective_scores["L1"]))
        l2_mean = float(np.mean(objective_scores["L2"]))
        l3_mean = float(np.mean(l3_totals))
        aggregate_rows.append([l1_mean, l2_mean, l3_mean])
        objective_matrices["L1"].append(objective_scores["L1"])
        objective_matrices["L2"].append(objective_scores["L2"])
        distinct_criterion_scores.update(criteria)
        dg_gaps.append(
            float(np.mean(l3_totals_by_type["DG1"]) - np.mean(l3_totals_by_type["DG2"]))
        )
        criterion_count += len(criteria)
        off_grid_count += int(
            np.sum(np.abs(np.asarray(criteria) * 20 - np.round(np.asarray(criteria) * 20)) > 1e-9)
        )
        print(
            f"{model}\t{len(paths)}\t{l1_mean:.4f}\t{l2_mean:.4f}\t{l3_mean:.4f}\t"
            f"{np.std(criteria):.4f}\t{np.median(ranges):.4f}\t"
            f"{np.mean(np.asarray(ranges) >= 0.50):.4f}\t"
            f"{np.mean(np.asarray(criteria) <= 0.20):.4f}\t"
            f"{np.mean(np.asarray(criteria) >= 0.90):.4f}\t"
            f"{np.mean(np.abs(np.asarray(criteria) * 20 - np.round(np.asarray(criteria) * 20)) > 1e-9):.4f}",
            flush=True,
        )

    correlations = np.corrcoef(np.asarray(aggregate_rows).T)
    score_by_model = {
        model: dict(zip(("L1", "L2", "L3"), row))
        for model, row in zip(models, aggregate_rows)
    }
    print("global_layer_correlations")
    print(
        f"L1_L2={correlations[0, 1]:.4f}\tL1_L3={correlations[0, 2]:.4f}\t"
        f"L2_L3={correlations[1, 2]:.4f}"
    )
    for layer in ("L1", "L2"):
        matrix = np.asarray(objective_matrices[layer])
        item_rates = np.mean(matrix, axis=0)
        print(
            f"{layer}_item_difficulty\tall_correct={np.mean(item_rates == 1.0):.4f}\t"
            f"all_wrong={np.mean(item_rates == 0.0):.4f}\t"
            f"middle_20_80={np.mean((item_rates >= 0.20) & (item_rates <= 0.80)):.4f}"
        )
    print(
        f"rubric_resolution\tdistinct_values={len(distinct_criterion_scores)}\t"
        f"off_0.05_grid={off_grid_count / criterion_count:.4f}"
    )
    for layer in ("L1", "L2"):
        all_type_values = [
            score
            for values in objective_type_scores[layer].values()
            for score in values
        ]
        overall = float(np.mean(all_type_values))
        offsets = ",".join(
            f"{question_type}:{(np.mean(values) - overall) * 100:+.2f}pp"
            for question_type, values in sorted(objective_type_scores[layer].items())
        )
        wrong_total = sum(wrong_answer_counts[layer].values())
        wrong_distribution = ",".join(
            f"{label}:{wrong_answer_counts[layer][label] / wrong_total:.3f}"
            for label in ("A", "B", "C", "D", "E")
        )
        print(f"{layer}_type_offsets\t{offsets}")
        print(f"{layer}_wrong_options\t{wrong_distribution}")
    for question_type in ("DG1", "DG2"):
        dimension_means = {
            dimension: float(np.mean(values))
            for dimension, values in dimension_scores[question_type].items()
        }
        ordered = sorted(dimension_means.items(), key=lambda pair: pair[1], reverse=True)
        print(
            f"{question_type}_dimension_means\t"
            + ",".join(f"{dimension}:{mean:.3f}" for dimension, mean in ordered)
        )
        if max(dimension_means.values()) - min(dimension_means.values()) < 0.05:
            raise ValueError(f"Suspiciously uniform dimension means for {question_type}")
    print(
        f"DG1_minus_DG2_across_models\tmean={np.mean(dg_gaps):+.4f}\t"
        f"sd={np.std(dg_gaps):.4f}\tmin={np.min(dg_gaps):+.4f}\tmax={np.max(dg_gaps):+.4f}"
    )

    layer_order_violations = [
        model
        for model in models
        if not (
            score_by_model[model]["L1"]
            > score_by_model[model]["L2"]
            > score_by_model[model]["L3"]
        )
    ]
    if layer_order_violations:
        raise ValueError(f"Models violating L1 > L2 > L3: {layer_order_violations}")
    print("layer_difficulty_order\t44/44 models satisfy L1 > L2 > L3")

    gpt_groups: dict[str, dict[str, str]] = defaultdict(dict)
    for model in models:
        effort = effort_of(model)
        if effort is not None:
            gpt_groups[base_model_of(model)][effort] = model
    for base, effort_models in sorted(gpt_groups.items()):
        if set(effort_models) != {"low", "mid", "max", "xhigh"}:
            raise ValueError(f"Incomplete GPT effort group for {base}: {sorted(effort_models)}")
        summaries = []
        for layer in ("L1", "L2", "L3"):
            values = [score_by_model[effort_models[effort]][layer] for effort in ("low", "mid", "max", "xhigh")]
            if not all(left < right for left, right in zip(values, values[1:])):
                raise ValueError(f"GPT effort order violation for {base}/{layer}: {values}")
            summaries.append(f"{layer}=" + "<".join(f"{value:.4f}" for value in values))
        print(f"gpt_effort_order\t{base}\t" + "\t".join(summaries))

    for family, chain in NON_GPT_PERFORMANCE_CHAINS.items():
        for layer in ("L1", "L2", "L3"):
            values = [score_by_model[model][layer] for model in chain]
            if not all(left > right for left, right in zip(values, values[1:])):
                raise ValueError(f"Basic performance chain violation for {family}/{layer}: {values}")
        print(f"family_generation_order\t{family}\tpass")

    rankings: dict[str, list[str]] = {}
    rank_vectors: dict[str, np.ndarray] = {}
    for layer_index, layer in enumerate(("L1", "L2", "L3")):
        ranking = sorted(models, key=lambda model: score_by_model[model][layer], reverse=True)
        rankings[layer] = ranking
        positions = {model: index for index, model in enumerate(ranking)}
        rank_vectors[layer] = np.asarray([positions[model] for model in models], dtype=float)
        print(f"ranking_{layer}\t" + " > ".join(ranking))

    for left, right in (("L1", "L2"), ("L1", "L3"), ("L2", "L3")):
        reversals = 0
        for first in range(len(models)):
            for second in range(first + 1, len(models)):
                left_difference = rank_vectors[left][first] - rank_vectors[left][second]
                right_difference = rank_vectors[right][first] - rank_vectors[right][second]
                reversals += int(left_difference * right_difference < 0)
        rank_correlation = float(np.corrcoef(rank_vectors[left], rank_vectors[right])[0, 1])
        print(
            f"rank_change_{left}_{right}\tspearman={rank_correlation:.4f}\t"
            f"pairwise_reversals={reversals}"
        )
        if reversals == 0:
            raise ValueError(f"Identical rankings for {left} and {right}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--calibrate-only",
        action="store_true",
        help="Generate scores in memory and print distributions without writing files.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing output directory and print realized distributions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if args.calibrate_only and args.validate_only:
        raise SystemExit("Choose at most one of --calibrate-only and --validate-only")
    if args.validate_only:
        validate(output)
    else:
        generate(output, args.seed, args.calibrate_only)


if __name__ == "__main__":
    main()
