"""Plot paired DG1/DG2 scores with integrated rubric-dimension profiles."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, CORAL, GRID, INK, PALE_GREY, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from result_utils import display_name, read_csv  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 175
FIGURE_HEIGHT_MM = 138.2
DPI = 500

summary = {row["model"]: row for row in read_csv("model_summary.csv")}
rows = read_csv("type_summary.csv")
scores = {(row["model"], row["question_type"]): float(row["score"]) for row in rows}
rubric_rows = read_csv("rubric_summary.csv")
rubric_scores: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
for model in summary:
    for question_type in ("DG1", "DG2"):
        selected = [
            row for row in rubric_rows
            if row["model"] == model and row["question_type"] == question_type
        ]
        rubric_scores[(model, question_type)] = (
            np.asarray([float(row["score"]) for row in selected]),
            np.asarray([float(row["total_weight"]) for row in selected]),
        )
models = sorted(
    summary,
    key=lambda model: (-np.mean([scores[(model, "DG1")], scores[(model, "DG2")]]), display_name(model)),
)
dg1 = np.asarray([scores[(model, "DG1")] for model in models])
dg2 = np.asarray([scores[(model, "DG2")] for model in models])
y = np.arange(len(models))
rubric_min = min(values.min() for values, _ in rubric_scores.values())
rubric_max = max(values.max() for values, _ in rubric_scores.values())
lower = np.floor((min(dg1.min(), dg2.min(), rubric_min) - 0.015) * 20) / 20
upper = np.ceil((max(dg1.max(), dg2.max(), rubric_max) + 0.015) * 20) / 20


def weighted_density(
    values: np.ndarray, weights: np.ndarray, grid: np.ndarray,
) -> np.ndarray:
    """Small weighted Gaussian KDE, normalized to a consistent row height."""
    weights = weights / weights.sum()
    spread = float(np.sqrt(np.sum(weights * (values - np.sum(weights * values)) ** 2)))
    bandwidth = float(np.clip(0.72 * spread * len(values) ** (-0.2), 0.018, 0.042))
    density = np.sum(
        weights[:, None]
        * np.exp(-0.5 * ((grid[None, :] - values[:, None]) / bandwidth) ** 2),
        axis=0,
    )
    peak = density.max()
    return density / peak if peak > 0 else density

fig, ax = plt.subplots(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4), facecolor="white"
)
for row_index in range(len(models)):
    if row_index % 2:
        ax.axhspan(row_index - 0.5, row_index + 0.5, color=PALE_GREY,
                   alpha=0.38, linewidth=0, zorder=0)

# Each model row carries its real ten-dimensional rubric profile on the same
# score scale as the aggregate endpoints.  DG1 occupies the upper half of the
# row and DG2 the lower half, so the extra information remains part of one
# visual system instead of becoming a detached inset.
density_grid = np.linspace(lower, upper, 360)
ridge_height = 0.31
for row_index, model in enumerate(models):
    dg1_values, dg1_weights = rubric_scores[(model, "DG1")]
    dg2_values, dg2_weights = rubric_scores[(model, "DG2")]
    dg1_density = weighted_density(dg1_values, dg1_weights, density_grid)
    dg2_density = weighted_density(dg2_values, dg2_weights, density_grid)
    dg1_support = dg1_density >= 0.015
    dg2_support = dg2_density >= 0.015
    ax.fill_between(
        density_grid, row_index, row_index - ridge_height * dg1_density,
        where=dg1_support, interpolate=True,
        color=BLUE, alpha=0.16, linewidth=0, zorder=0.55,
    )
    ax.plot(
        density_grid,
        np.where(dg1_support, row_index - ridge_height * dg1_density, np.nan),
        color=BLUE, alpha=0.62, linewidth=0.48, zorder=0.9,
    )
    ax.fill_between(
        density_grid, row_index, row_index + ridge_height * dg2_density,
        where=dg2_support, interpolate=True,
        color=CORAL, alpha=0.15, linewidth=0, zorder=0.55,
    )
    ax.plot(
        density_grid,
        np.where(dg2_support, row_index + ridge_height * dg2_density, np.nan),
        color=CORAL, alpha=0.62, linewidth=0.48, zorder=0.9,
    )

# The connector is deliberately recessive: individual task scores are the
# primary marks, while paired model identity remains perceptible by row.
for row_index, left, right in zip(y, dg1, dg2):
    ax.hlines(row_index, min(left, right), max(left, right),
              color=SLATE, linewidth=0.58, alpha=0.40, zorder=1)
ax.scatter(dg1, y, s=28, color=BLUE, edgecolor="white", linewidth=0.52,
           label="Layer Design", zorder=3)
ax.scatter(dg2, y, s=28, color=CORAL, edgecolor="white", linewidth=0.52,
           label="System Design", zorder=3)

# Put both values outside the paired endpoints according to their actual
# positions: the leftmost point reads left and the rightmost point reads
# right.  Text color continues to identify the corresponding task.  Three
# decimals retain the small but meaningful differences between the scores.
for row_index, blue_value, red_value in zip(y, dg1, dg2):
    blue_is_left = blue_value < red_value
    ax.annotate(
        f"{red_value:.3f}", xy=(red_value, row_index),
        xytext=((5.0 if blue_is_left else -5.0), 0.0),
        textcoords="offset points",
        ha=("left" if blue_is_left else "right"), va="center",
        fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL, color=CORAL,
        annotation_clip=False, zorder=4,
    )
    ax.annotate(
        f"{blue_value:.3f}", xy=(blue_value, row_index),
        xytext=((-5.0 if blue_is_left else 5.0), 0.0),
        textcoords="offset points",
        ha=("right" if blue_is_left else "left"), va="center",
        fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL, color=BLUE,
        annotation_clip=False, zorder=4,
    )

ax.set_yticks(y)
ax.set_yticklabels([display_name(model) for model in models],
                   fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL)
ax.set_ylim(len(models) - 0.5, -0.5)
ax.set_xlim(lower, upper)
first_tick = np.ceil(lower * 20) / 20
ax.set_xticks(np.arange(first_tick, upper + 0.001, 0.05))
ax.set_xlabel("Score", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY,
              color=INK, labelpad=4)
ax.set_ylabel("Model", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY,
              color=INK, labelpad=5)
ax.grid(axis="x", color=GRID, linewidth=0.45, zorder=0)
ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
for label in ax.get_xticklabels():
    label.set_fontproperties(ARIAL); label.set_fontsize(FONT_SIZE_DETAIL)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(SLATE); ax.spines[side].set_linewidth(0.62)

# Explicit y-axis end caps make the first and last half-row boundaries visible
# and keep every model row—including GPT-5.6 Sol—the same height.
cap_width = (upper - lower) * 0.008
for y_edge in (-0.5, len(models) - 0.5):
    ax.plot([lower, lower + cap_width], [y_edge, y_edge], color=SLATE,
            linewidth=0.62, clip_on=False, zorder=5)

legend_handles = [
    Line2D([], [], linestyle="none", marker="o", markersize=5.2,
           markerfacecolor=BLUE, markeredgecolor="white", markeredgewidth=0.52,
           label="Layer Design Score"),
    Patch(facecolor=BLUE, edgecolor=BLUE, linewidth=0.48, alpha=0.16,
          label="Layer Design Rubric Profile"),
    Line2D([], [], linestyle="none", marker="o", markersize=5.2,
           markerfacecolor=CORAL, markeredgecolor="white", markeredgewidth=0.52,
           label="System Design Score"),
    Patch(facecolor=CORAL, edgecolor=CORAL, linewidth=0.48, alpha=0.15,
          label="System Design Rubric Profile"),
]
legend = ax.legend(
    handles=legend_handles,
    loc="lower right", bbox_to_anchor=(0.992, 0.012),
    bbox_transform=ax.transAxes, frameon=False, ncol=1, prop=ARIAL,
    handletextpad=0.35, columnspacing=0.92, labelspacing=0.42,
    borderaxespad=0.0,
)
for label in legend.get_texts():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
fig.subplots_adjust(left=0.145, right=0.985, bottom=0.095, top=0.970)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
tight_bbox = Bbox.from_extents(
    tight_bbox.x0 - 2.0 / 25.4, tight_bbox.y0,
    tight_bbox.x1, tight_bbox.y1,
)
fig.savefig(OUTPUT_DIR / "l3_type_scores.svg", facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
fig.savefig(OUTPUT_DIR / "l3_type_scores.png", dpi=DPI, facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
fig.savefig(OUTPUT_DIR / "l3_type_scores.pdf", facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
plt.close(fig)

with (OUTPUT_DIR / "dg_type_scores.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader(); writer.writerows(row for row in rows if row["question_type"] in ("DG1", "DG2"))

print(f"Models: {len(models)}; paired DG1/DG2 dumbbell comparison from code/result")
print(
    f"Canvas: {tight_bbox.width * 25.4:.1f} x "
    f"{tight_bbox.height * 25.4:.1f} mm at {DPI} dpi (tight export)"
)
