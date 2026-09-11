#!/usr/bin/env python3
"""Aggregate every persisted result into compact tables for Figures 07--12.

For each GPT base model, only its ``xhigh`` result directory is selected;
``max``, ``mid``, and ``low`` are deliberately excluded. Other result
directories map one-to-one to a displayed model. No synthetic values are
generated here.
"""
from __future__ import annotations

from collections import defaultdict
import csv
import json
from pathlib import Path

from chart_utils import RESULT_ROOT
from result_utils import CACHE_ROOT, MODEL_META, canonical_model


MAPPING_PATH = (
    Path(__file__).resolve().parent
    / "11_l3_rubric_heatmaps"
    / "rubric_dimension_mapping.csv"
)


def write_csv(path: Path, header: tuple[str, ...], rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def build_cache() -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    dimension_map: dict[tuple[str, int], tuple[str, float]] = {}
    with MAPPING_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            dimension_map[(row["qa_id"], int(row["rubric_index"]))] = (
                row["dimension"], float(row["weight"])
            )

    item_sum: dict[tuple[str, str], float] = defaultdict(float)
    item_count: dict[tuple[str, str], int] = defaultdict(int)
    question_meta: dict[str, tuple[str, str, str, str]] = {}
    rubric_sum: dict[tuple[str, str, str], float] = defaultdict(float)
    rubric_weight: dict[tuple[str, str, str], float] = defaultdict(float)
    rubric_item_rows: list[tuple] = []
    configs_by_model: dict[str, set[str]] = defaultdict(set)
    result_files = 0
    missing_scores = 0
    missing_dimensions = 0

    config_dirs = sorted(path for path in RESULT_ROOT.iterdir() if path.is_dir())
    for config_dir in config_dirs:
        if config_dir.name.startswith("gpt-") and not config_dir.name.endswith("-xhigh"):
            continue
        model = canonical_model(config_dir.name)
        if model not in MODEL_META:
            raise KeyError(f"No model metadata for result directory {config_dir.name!r}")
        configs_by_model[model].add(config_dir.name)
        for path in config_dir.rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            qa_id = str(data["qa_id"])
            layer = str(data["layer"])
            question_type = str(data["type"])
            paper_id = str(data["source_paper_id"])
            subcategory = str(data["subcategory"])
            question_meta.setdefault(
                qa_id, (layer, question_type, paper_id, subcategory)
            )
            evaluation = data.get("evaluation", {})
            score: float | None = None
            if layer in {"L1", "L2"}:
                correct = evaluation.get("is_correct")
                if isinstance(correct, bool):
                    score = float(correct)
            elif layer == "L3":
                result = evaluation.get("result")
                value = result.get("score") if isinstance(result, dict) else None
                if isinstance(value, (int, float)):
                    score = float(value)
            if score is None:
                missing_scores += 1
                continue
            item_sum[(model, qa_id)] += score
            item_count[(model, qa_id)] += 1
            result_files += 1

            if layer == "L3":
                result = evaluation.get("result", {})
                judged = result.get("per_rubric", []) if isinstance(result, dict) else []
                for index, judged_item in enumerate(judged, start=1):
                    criterion_score = judged_item.get("score") if isinstance(judged_item, dict) else None
                    if not isinstance(criterion_score, (int, float)):
                        continue
                    mapped = dimension_map.get((qa_id, index))
                    if mapped is None:
                        missing_dimensions += 1
                        continue
                    dimension, weight = mapped
                    key = (model, question_type, dimension)
                    rubric_sum[key] += float(criterion_score) * weight
                    rubric_weight[key] += weight
                    rubric_item_rows.append(
                        (
                            model, qa_id, question_type, dimension,
                            f"{float(criterion_score):.8f}", f"{weight:.6f}",
                        )
                    )

    expected_models = set(MODEL_META)
    if set(configs_by_model) != expected_models:
        raise RuntimeError(
            f"Result/model mismatch: missing={sorted(expected_models-set(configs_by_model))}, "
            f"extra={sorted(set(configs_by_model)-expected_models)}"
        )

    item_rows: list[tuple] = []
    layer_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    type_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    paper_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for (model, qa_id), total in sorted(item_sum.items()):
        layer, question_type, paper_id, subcategory = question_meta[qa_id]
        count = item_count[(model, qa_id)]
        score = total / count
        expected_count = len(configs_by_model[model])
        if count != expected_count:
            raise RuntimeError(
                f"Incomplete configuration aggregation for {model}/{qa_id}: {count}/{expected_count}"
            )
        item_rows.append(
            (model, qa_id, layer, question_type, subcategory, paper_id, f"{score:.8f}", count)
        )
        layer_values[(model, layer)].append(score)
        type_values[(model, question_type)].append(score)
        paper_values[(model, layer, paper_id)].append(score)

    write_csv(
        CACHE_ROOT / "item_scores.csv",
        ("model", "qa_id", "layer", "question_type", "subcategory", "source_paper_id", "score", "configuration_count"),
        item_rows,
    )

    summary_rows = []
    for model in sorted(MODEL_META):
        layer_means = {}
        for layer in ("L1", "L2", "L3"):
            values = layer_values[(model, layer)]
            if not values:
                raise RuntimeError(f"No {layer} scores for {model}")
            layer_means[layer] = sum(values) / len(values)
        overall = sum(layer_means.values()) / 3.0
        summary_rows.append(
            (
                model,
                MODEL_META[model].label,
                MODEL_META[model].family,
                MODEL_META[model].release_date.isoformat(),
                len(configs_by_model[model]),
                f"{layer_means['L1']:.8f}",
                f"{layer_means['L2']:.8f}",
                f"{layer_means['L3']:.8f}",
                f"{overall:.8f}",
            )
        )
    write_csv(
        CACHE_ROOT / "model_summary.csv",
        ("model", "display_name", "family", "release_date", "configuration_count", "l1_score", "l2_score", "l3_score", "overall_score"),
        summary_rows,
    )

    type_rows = []
    for (model, question_type), values in sorted(type_values.items()):
        type_rows.append((model, question_type, f"{sum(values)/len(values):.8f}", len(values)))
    write_csv(
        CACHE_ROOT / "type_summary.csv",
        ("model", "question_type", "score", "question_count"),
        type_rows,
    )

    paper_rows = []
    for (model, layer, paper_id), values in sorted(paper_values.items()):
        paper_rows.append((model, layer, paper_id, f"{sum(values)/len(values):.8f}", len(values)))
    write_csv(
        CACHE_ROOT / "paper_scores.csv",
        ("model", "layer", "source_paper_id", "score", "question_count"),
        paper_rows,
    )

    rubric_rows = []
    for key in sorted(rubric_sum):
        model, question_type, dimension = key
        total_weight = rubric_weight[key]
        rubric_rows.append(
            (model, question_type, dimension, f"{rubric_sum[key]/total_weight:.8f}", f"{total_weight:.6f}")
        )
    write_csv(
        CACHE_ROOT / "rubric_summary.csv",
        ("model", "question_type", "dimension", "score", "total_weight"),
        rubric_rows,
    )
    write_csv(
        CACHE_ROOT / "rubric_item_scores.csv",
        ("model", "qa_id", "question_type", "dimension", "score", "weight"),
        rubric_item_rows,
    )

    provenance = {
        "source": str(RESULT_ROOT),
        "result_files_scored": result_files,
        "missing_scores": missing_scores,
        "missing_rubric_dimensions": missing_dimensions,
        "displayed_models": len(MODEL_META),
        "source_configurations": sum(len(value) for value in configs_by_model.values()),
        "gpt_selection": "xhigh only; max, mid, and low excluded",
        "configurations_by_model": {
            key: sorted(value) for key, value in sorted(configs_by_model.items())
        },
    }
    (CACHE_ROOT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build_cache()
