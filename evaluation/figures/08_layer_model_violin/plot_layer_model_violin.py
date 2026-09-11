"""Plot model scores and 95% intervals across the three benchmark layers."""
from __future__ import annotations

from collections import defaultdict
import csv
from pathlib import Path
import sys

import numpy as np
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, CORAL, GRID, INK, PALE_GREY, SLATE, TEAL,
    FONT_SIZE_DETAIL, FONT_SIZE_KEY, plt,
)
from result_utils import display_name, read_csv  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 175
FIGURE_HEIGHT_MM = 175
DPI = 500
LAYERS = ("L1", "L2", "L3")
LAYER_LABELS = {
    "L1": "Fundamentals (L1)",
    "L2": "Applied Reasoning (L2)",
    "L3": "Engineering Design (L3)",
}
COLORS = {"L1": BLUE, "L2": TEAL, "L3": CORAL}


def wilson_interval(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


summary = {row["model"]: row for row in read_csv("model_summary.csv")}
models = sorted(summary, key=lambda model: (-float(summary[model]["l3_score"]), display_name(model)))
item_rows = read_csv("item_scores.csv")
scores = defaultdict(list)
for row in item_rows:
    scores[(row["model"], row["layer"])].append(float(row["score"]))

statistics = {}
for model in models:
    for layer in LAYERS:
        values = np.asarray(scores[(model, layer)], dtype=float)
        mean = float(values.mean())
        if layer in ("L1", "L2"):
            low, high = wilson_interval(float(values.sum()), len(values))
        else:
            half = 1.96 * float(values.std(ddof=1)) / np.sqrt(len(values))
            low, high = max(0.0, mean - half), min(1.0, mean + half)
        statistics[(model, layer)] = (mean, low, high)

fig, axes = plt.subplots(
    1, 3, figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    sharey=True, facecolor="white",
)
y = np.arange(len(models))
for column, (ax, layer) in enumerate(zip(axes, LAYERS)):
    means = np.asarray([statistics[(model, layer)][0] for model in models])
    lows = np.asarray([statistics[(model, layer)][1] for model in models])
    highs = np.asarray([statistics[(model, layer)][2] for model in models])
    for row_index in range(len(models)):
        if row_index % 2:
            ax.axhspan(row_index - 0.5, row_index + 0.5, color=PALE_GREY, alpha=0.58, linewidth=0)
    ax.errorbar(
        means, y, xerr=np.vstack((means - lows, highs - means)), fmt="o",
        markersize=3.7, markerfacecolor=COLORS[layer], markeredgecolor="white",
        markeredgewidth=0.55, ecolor=COLORS[layer], elinewidth=0.85,
        capsize=1.8, capthick=0.65, zorder=4,
    )
    ax.set_xlim(0.2, 1.0)
    ax.set_xticks(np.arange(0.2, 1.01, 0.2))
    ax.set_xlabel("Score", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK, labelpad=4)
    ax.set_title(LAYER_LABELS[layer], fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK, pad=5)
    # Keep the score axis clean: ticks remain, but their full-height guide
    # lines are omitted.  Extrema are labelled at the model points where they
    # occur.  The across-model mean has no model row, so it is keyed to its
    # true x-coordinate with a compact upward marker on the bottom axis.
    max_index = int(np.argmax(means))
    min_index = int(np.argmin(means))
    mean_value = float(means.mean())
    for stat_name, stat_index in (("Max", max_index), ("Min", min_index)):
        stat_value = float(means[stat_index])
        if stat_name == "Min":
            text_offset = 6.0 if layer == "L3" else -6.0
            text_alignment = "left" if layer == "L3" else "right"
            stat_text = f"Min {stat_value:.3f}"
        else:
            text_offset = 6.0
            text_alignment = "left"
            stat_text = f"Max\n{stat_value:.3f}" if layer == "L1" else f"Max {stat_value:.3f}"
        ax.annotate(
            stat_text,
            xy=(stat_value, y[stat_index]), xytext=(text_offset, 0.0),
            textcoords="offset points", ha=text_alignment, va="center",
            linespacing=0.90,
            fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
            color=CORAL, annotation_clip=False, zorder=6,
        )
    ax.axvline(
        mean_value, color=CORAL, linewidth=0.62,
        linestyle=(0, (3, 2)), zorder=2,
    )
    bottom_edge = len(models) - 0.5
    ax.annotate(
        f"Mean {mean_value:.3f}", xy=(mean_value, bottom_edge),
        xytext=(4.0, 5.0), textcoords="offset points",
        ha="left", va="bottom", fontproperties=ARIAL,
        fontsize=FONT_SIZE_DETAIL, color=CORAL,
        annotation_clip=False, zorder=7,
    )
    ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
    for label in ax.get_xticklabels():
        label.set_fontproperties(ARIAL); label.set_fontsize(FONT_SIZE_DETAIL)
    for spine in ax.spines.values():
        spine.set_visible(True); spine.set_color(SLATE); spine.set_linewidth(0.62)

axes[0].set_yticks(y)
axes[0].set_yticklabels([display_name(model) for model in models], fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL)
axes[0].set_ylim(len(models) - 0.5, -0.5)
axes[0].set_ylabel("Model", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK, labelpad=5)
for ax in axes[1:]:
    ax.tick_params(axis="y", left=False, labelleft=False)

fig.subplots_adjust(left=0.145, right=0.985, bottom=0.075, top=0.955, wspace=0.075)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
tight_bbox = Bbox.from_extents(
    tight_bbox.x0 - 2.0 / 25.4, tight_bbox.y0,
    tight_bbox.x1, tight_bbox.y1,
)
fig.savefig(OUTPUT_DIR / "layer_model_violin.svg", facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
fig.savefig(OUTPUT_DIR / "layer_model_violin.png", dpi=DPI, facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
fig.savefig(OUTPUT_DIR / "layer_model_violin.pdf", facecolor="white",
            bbox_inches=tight_bbox, pad_inches=0)
plt.close(fig)

with (OUTPUT_DIR / "layer_model_scores.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=item_rows[0].keys())
    writer.writeheader(); writer.writerows(item_rows)

print(f"Models: {len(models)}; real item-level scores; GPT xhigh only")
print(
    f"Canvas: {tight_bbox.width * 25.4:.1f} x "
    f"{tight_bbox.height * 25.4:.1f} mm at {DPI} dpi (tight export)"
)
