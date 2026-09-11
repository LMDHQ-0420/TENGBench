"""Shared data, typography, and palette utilities for TENGBench figures."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CODE_ROOT = Path(__file__).resolve().parents[2]
QUESTION_ROOT = CODE_ROOT / "benchmark" / "question"
PAPER_ROOT = CODE_ROOT / "papers" / "qualified"
RESULT_ROOT = CODE_ROOT / "result"

ARIAL = font_manager.FontProperties(
    fname="/System/Library/Fonts/Supplemental/Arial.ttf"
)
ARIAL_BOLD = font_manager.FontProperties(
    fname="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
)
FONT_SIZE_DETAIL = 5.8
FONT_SIZE_LABEL = 7.0
FONT_SIZE_KEY = 8.5

# Unified publication palette.  The cobalt/charcoal core follows the visual
# language of the workflow reference supplied for the figures; the restrained
# secondary hues keep dense categorical plots legible without changing style.
INK = "#20242A"
CHARCOAL = "#74777B"
BLUE = "#526FB4"
BLUE_DARK = "#304F8C"
BLUE_LIGHT = "#AFC0E1"
SLATE = "#71869C"
TEAL = "#3F929C"
TEAL_LIGHT = "#A8D0D3"
CORAL = "#D46B5F"
CORAL_LIGHT = "#E8B3AD"
ORANGE = "#D4934B"
PURPLE = "#7968A8"
ROSE = "#B66B87"
GREEN = "#618E79"
PALE_GREY = "#EEF1F5"
GRID = "#D9DEE6"

PALETTE = [
    BLUE, TEAL, CORAL, PURPLE, ORANGE, SLATE, ROSE, GREEN,
    "#6D88C5", "#55A6B1", "#DD8173", "#8D7AB8", "#DDA45F",
    "#8798AA", "#C27B96",
]
LABEL_OVERRIDES = {
    "hmi": "HMI",
    "iot": "IoT",
    "energyharv": "Energy Harvesting",
    "smarttextile": "Smart Textile",
}


def load_questions() -> list[dict]:
    venues: dict[str, str] = {}
    for index_path in PAPER_ROOT.glob("**/index.json"):
        paper = json.loads(index_path.read_text(encoding="utf-8"))
        venues[paper["paper_id"]] = paper["venue"]
    questions: list[dict] = []
    for question_path in QUESTION_ROOT.glob("**/*.json"):
        question = json.loads(question_path.read_text(encoding="utf-8"))
        if question["source_paper_id"] in venues:
            question["venue"] = venues[question["source_paper_id"]]
        questions.append(question)
    return questions


def display_label(label: str) -> str:
    return LABEL_OVERRIDES.get(label, label.replace("_", " ").title())
