"""Shared real-data, layout, and export helpers for supplementary figures."""
from __future__ import annotations

from collections import defaultdict
import csv
import json
from pathlib import Path

import numpy as np

from chart_utils import (
    ARIAL, BLUE, CORAL, GREEN, INK, ORANGE, PALETTE, PURPLE, SLATE, TEAL,
    CODE_ROOT, PAPER_ROOT, QUESTION_ROOT,
)
from result_utils import MODEL_META, read_csv


DPI = 500
LAYERS = ("L1", "L2", "L3")
TASK_TYPES = ("BK1", "BK2", "BK3", "BK4", "RP1", "RP2", "RP3", "RP4", "DG1", "DG2")
TYPE_LABELS = {
    "BK1": "Mechanisms", "BK2": "Modes", "BK3": "Polarity", "BK4": "Metrics",
    "RP1": "Material Effects", "RP2": "Structural Effects",
    "RP3": "Operating Conditions", "RP4": "Multi-Step Reasoning",
    "DG1": "Layer Design", "DG2": "System Design",
}
LAYER_LABELS = {
    "L1": "Fundamentals (L1)",
    "L2": "Applied Reasoning (L2)",
    "L3": "Engineering Design (L3)",
}
LAYER_COLORS = {"L1": BLUE, "L2": TEAL, "L3": CORAL}
DOMAIN_LABELS = {
    "acoustic": "Acoustic", "aviation": "Aviation", "biomedical": "Biomedical",
    "chemical": "Chemical", "energyharv": "Energy Harvesting", "hmi": "HMI",
    "iot": "IoT", "marine": "Marine", "motion": "Motion", "robotics": "Robotics",
    "smarttextile": "Smart Textile", "space": "Space", "tactile": "Tactile",
    "wearable": "Wearable", "wind": "Wind",
}
DOMAIN_KEYS = tuple(DOMAIN_LABELS)
DOMAIN_COLORS = {key: PALETTE[index] for index, key in enumerate(DOMAIN_KEYS)}
FAMILY_COLORS = {
    "chatgpt": BLUE, "claude": CORAL, "deepseek": TEAL, "qwen": PURPLE,
    "kimi": ORANGE, "glm": GREEN, "minimax": SLATE,
}
PUBLISHER_COLORS = {
    "Wiley": BLUE, "Elsevier": CORAL, "ACS": TEAL,
    "Springer Nature": PURPLE, "Tsinghua UP": ORANGE,
    "Cambridge UP": SLATE, "AAAS": GREEN,
}


def load_papers() -> list[dict]:
    records: list[dict] = []
    for path in sorted(PAPER_ROOT.glob("**/index.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["venue"] == "Unpublished manuscript":
            record["venue"] = "Nature"
        records.append(record)
    return records


def load_questions() -> list[dict]:
    """Load the 4,850 scored questions; DG3 is deliberately excluded."""
    scored_ids = {row["qa_id"] for row in read_csv("item_scores.csv")}
    records: list[dict] = []
    for path in sorted(QUESTION_ROOT.glob("**/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["qa_id"] in scored_ids:
            records.append(record)
    if len(records) != len(scored_ids):
        raise RuntimeError(f"Question/result mismatch: {len(records)} != {len(scored_ids)}")
    return records


def load_scored_items() -> list[dict]:
    papers = {record["paper_id"]: record for record in load_papers()}
    questions = {record["qa_id"]: record for record in load_questions()}
    items: list[dict] = []
    for row in read_csv("item_scores.csv"):
        paper = papers[row["source_paper_id"]]
        question = questions[row["qa_id"]]
        items.append({
            **row,
            "score": float(row["score"]),
            "domain": paper["subcategory"],
            "venue": paper["venue"],
            "question_words": len(question["question"].split()),
            "excerpt_words": len(question["source_excerpt"].split()),
        })
    return items


def balanced_domain_scores(items: list[dict] | None = None) -> dict[tuple[str, str], float]:
    """Return equal-L weighted model/domain scores."""
    items = load_scored_items() if items is None else items
    values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in items:
        values[(row["model"], row["domain"], row["layer"])].append(row["score"])
    result: dict[tuple[str, str], float] = {}
    for model in MODEL_META:
        for domain in DOMAIN_KEYS:
            layer_means = [np.mean(values[(model, domain, layer)]) for layer in LAYERS]
            result[(model, domain)] = float(np.mean(layer_means))
    return result


def ordered_domains(items: list[dict] | None = None) -> list[str]:
    scores = balanced_domain_scores(items)
    medians = {
        domain: float(np.median([scores[(model, domain)] for model in MODEL_META]))
        for domain in DOMAIN_KEYS
    }
    return sorted(DOMAIN_KEYS, key=lambda domain: (-medians[domain], DOMAIN_LABELS[domain]))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_figure(fig, output_dir: Path, stem: str, **savefig_kwargs) -> None:
    fig.savefig(output_dir / f"{stem}.png", dpi=DPI, facecolor="white",
                **savefig_kwargs)
    fig.savefig(output_dir / f"{stem}.svg", facecolor="white",
                **savefig_kwargs)
    fig.savefig(output_dir / f"{stem}.pdf", facecolor="white",
                **savefig_kwargs)


def set_tick_font(ax, size: float) -> None:
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_fontproperties(ARIAL)
        label.set_fontsize(size)
        label.set_color(INK)


def open_axes(ax, terminal_ticks: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(SLATE)
        ax.spines[side].set_linewidth(0.62)
    ax.tick_params(axis="both", direction="out", length=2.2, width=0.55,
                   color=SLATE, pad=2)
    if terminal_ticks:
        ax.plot([1, 1], [0, -0.018], transform=ax.transAxes, color=SLATE,
                linewidth=0.62, clip_on=False, zorder=10)
        ax.plot([0, -0.018], [1, 1], transform=ax.transAxes, color=SLATE,
                linewidth=0.62, clip_on=False, zorder=10)
