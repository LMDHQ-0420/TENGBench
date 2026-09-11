"""Plot L1/L2 subtype accuracies with binomial confidence intervals."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, CORAL, GRID, INK, SLATE, TEAL,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from result_utils import display_name, read_csv  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 190
FIGURE_HEIGHT_MM = 190
DPI = 500
LAYOUT = (
    (("L1", "BK1"), ("L2", "RP1")),
    (("L1", "BK2"), ("L2", "RP2")),
    (("L1", "BK3"), ("L2", "RP3")),
    (("L1", "BK4"), ("L2", "RP4")),
)
LAYER_LABELS = {"L1": "Fundamentals (L1)", "L2": "Applied Reasoning (L2)"}
TYPE_LABELS = {
    "BK1": "Mechanisms", "BK2": "Modes",
    "BK3": "Polarity", "BK4": "Metrics",
    "RP1": "Material Effects", "RP2": "Structural Effects",
    "RP3": "Operating Conditions", "RP4": "Multi-Step Reasoning",
}
LAYER_COLORS = {"L1": BLUE, "L2": TEAL}


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


summary = {row["model"]: row for row in read_csv("model_summary.csv")}
models = sorted(summary, key=lambda model: (-float(summary[model]["l3_score"]), display_name(model)))
rows = read_csv("type_summary.csv")
records = {(row["model"], row["question_type"]): row for row in rows}
positions = np.arange(len(models))

fig, axes = plt.subplots(
    4, 2, figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    sharex=True, sharey=False, facecolor="white",
)
for row_index, panel_row in enumerate(LAYOUT):
    for column_index, (layer, question_type) in enumerate(panel_row):
        ax = axes[row_index, column_index]
        values = np.asarray([float(records[(model, question_type)]["score"]) for model in models])
        ns = np.asarray([int(records[(model, question_type)]["question_count"]) for model in models])
        intervals = np.asarray([wilson(value, int(n)) for value, n in zip(values, ns)])
        color = LAYER_COLORS[layer]
        ax.errorbar(
            positions, values,
            yerr=np.vstack((values - intervals[:, 0], intervals[:, 1] - values)),
            fmt="o", markersize=2.9, markerfacecolor=color, markeredgecolor="white",
            markeredgewidth=0.45, ecolor=color, elinewidth=0.60,
            capsize=1.25, capthick=0.5, zorder=4,
        )
        mean = float(values.mean())
        ax.axhline(mean, color=CORAL, linewidth=0.48, linestyle=(0, (3, 2)), zorder=2)
        ax.text(0.992, mean + 0.012, f"Mean {mean:.2f}", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontproperties=ARIAL,
                fontsize=FONT_SIZE_LABEL, color=CORAL)
        ax.set_xlim(-0.55, len(models) - 0.45)
        ax.set_ylim(0.3, 1.0)
        ticks = np.arange(0.3, 1.01, 0.1)
        ax.set_yticks(ticks)
        ax.set_yticklabels([
            "" if row_index < 3 and np.isclose(tick, 0.3) else f"{tick:.1f}"
            for tick in ticks
        ])
        ax.set_ylabel(TYPE_LABELS[question_type], fontproperties=ARIAL_BOLD,
                      fontsize=FONT_SIZE_LABEL, color=INK, labelpad=6)
        ax.grid(axis="y", color=GRID, linewidth=0.42, zorder=0)
        ax.tick_params(axis="y", direction="out", length=2.1, width=0.55,
                       color=SLATE, pad=2, left=True, labelleft=True)
        ax.tick_params(axis="x", bottom=row_index == 3, labelbottom=row_index == 3,
                       direction="out", length=2.2, width=0.55, color=SLATE, pad=2)
        for label in ax.get_yticklabels():
            label.set_fontproperties(ARIAL); label.set_fontsize(FONT_SIZE_DETAIL)
        for spine in ax.spines.values():
            spine.set_visible(True); spine.set_color(SLATE); spine.set_linewidth(0.60)

for ax in axes[-1]:
    ax.set_xticks(positions)
    ax.set_xticklabels([display_name(model) for model in models], rotation=90,
                       ha="center", va="top", fontproperties=ARIAL,
                       fontsize=FONT_SIZE_DETAIL)
    ax.set_xlabel("Model", fontproperties=ARIAL_BOLD,
                  fontsize=FONT_SIZE_KEY, color=INK, labelpad=2)
for column, layer in enumerate(("L1", "L2")):
    axes[0, column].set_title(LAYER_LABELS[layer], fontproperties=ARIAL_BOLD,
                              fontsize=FONT_SIZE_KEY, color=INK, pad=5)

fig.subplots_adjust(left=0.078, right=0.997, bottom=0.155, top=0.965, wspace=0.16, hspace=0.0)
fig.savefig(OUTPUT_DIR / "model_subtype_accuracy.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "model_subtype_accuracy.png", dpi=DPI, facecolor="white")
plt.close(fig)

with (OUTPUT_DIR / "subtype_accuracy.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader(); writer.writerows(rows)

print(f"Models: {len(models)}; panels: 8; scores from code/result (GPT xhigh)")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
