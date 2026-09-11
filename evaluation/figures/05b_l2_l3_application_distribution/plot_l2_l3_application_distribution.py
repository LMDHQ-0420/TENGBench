"""Compare paired L2/L3 application-category coverage without connector rules."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

from matplotlib.lines import Line2D
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, CORAL, INK, PALE_GREY, SLATE, TEAL,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, display_label,
    load_questions, plt,
)

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 95
FIGURE_HEIGHT_MM = 125
DPI = 500

# Only the ten formal TENGBench subtasks are included in the manuscript.
# DG3 is retained in the source question bank but is excluded from evaluation.
FORMAL_TASK_TYPES = {
    "L2": {"RP1", "RP2", "RP3", "RP4"},
    "L3": {"DG1", "DG2"},
}


def compact_name(label: str) -> str:
    overrides = {
        "energyharv": "Energy harvesting",
        "smarttextile": "Smart textile",
        "biomedical": "Biomedical",
    }
    return overrides.get(label, display_label(label))


questions = load_questions()
counts = {
    layer: Counter(
        q["subcategory"]
        for q in questions
        if q["layer"] == layer and q.get("type") in FORMAL_TASK_TYPES[layer]
    )
    for layer in ("L2", "L3")
}
categories = sorted(
    set(counts["L2"]) | set(counts["L3"]),
    key=lambda category: (-(counts["L2"][category] + counts["L3"][category]), category),
)
v2 = np.asarray([counts["L2"][category] for category in categories])
v3 = np.asarray([counts["L3"][category] for category in categories])
y = np.arange(len(categories))
xmax = float(max(v2.max(), v3.max())) * 1.18

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)
ax = fig.add_axes([0.300, 0.095, 0.675, 0.875])

# The neutral band uses the same point diameter as both endpoint circles.  Its
# rounded caps therefore terminate exactly underneath the circle boundaries.
band_diameter_pt = 5.0
for row, left, right in zip(y, v2, v3):
    ax.plot(
        [left, right], [row, row], color=PALE_GREY,
        linewidth=band_diameter_pt, solid_capstyle="round", zorder=1,
    )

ax.scatter(
    v2, y, s=band_diameter_pt**2, facecolor=TEAL,
    edgecolor="white", linewidth=0.50, zorder=3,
)
ax.scatter(
    v3, y, s=band_diameter_pt**2, facecolor=CORAL,
    edgecolor="white", linewidth=0.50, zorder=4,
)
label_gap = 8.5
for row, category, l2_value, l3_value in zip(y, categories, v2, v3):
    if l2_value >= l3_value:
        l2_x, l2_align = l2_value + label_gap, "left"
        l3_x, l3_align = l3_value - label_gap, "right"
    else:
        l2_x, l2_align = l2_value - label_gap, "right"
        l3_x, l3_align = l3_value + label_gap, "left"
    if category == "space":
        l3_x = l3_value - 4.5
    ax.text(
        l2_x, row, str(l2_value), ha=l2_align, va="center",
        fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL, color=TEAL,
    )
    ax.text(
        l3_x, row, str(l3_value), ha=l3_align, va="center",
        fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL, color=CORAL,
    )

ax.set_yticks(y)
ax.set_yticklabels(
    [compact_name(category) for category in categories],
    fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
)
ax.invert_yaxis()
ax.set_xlim(0, xmax)
ax.set_xlabel(
    "Number of Questions", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.set_ylabel(
    "Application Category", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=4,
)
ax.grid(False)
ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
for label in ax.get_xticklabels() + ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(SLATE)
    ax.spines[side].set_linewidth(0.62)
# Explicit terminal ticks at the right end of x and the top end of y.
ax.plot([1, 1], [0, -0.010], transform=ax.transAxes, color=SLATE,
        linewidth=0.62, clip_on=False, zorder=6)
ax.plot([-0.010, 0], [1, 1], transform=ax.transAxes, color=SLATE,
        linewidth=0.62, clip_on=False, zorder=6)

legend_handles = [
    Line2D([], [], linestyle="none", marker="o", markersize=4.2,
           markerfacecolor=TEAL, markeredgecolor="white",
           markeredgewidth=0.45, label="Applied Reasoning (L2)"),
    Line2D([], [], linestyle="none", marker="o", markersize=4.2,
           markerfacecolor=CORAL, markeredgecolor="white",
           markeredgewidth=0.45, label="Engineering Design (L3)"),
]
legend_font = ARIAL.copy()
legend_font.set_size(FONT_SIZE_DETAIL)
ax.legend(
    handles=legend_handles, loc="lower right", bbox_to_anchor=(0.985, 0.025),
    frameon=False, ncol=1,
    labelspacing=0.28, handletextpad=0.35, borderaxespad=0.2,
    prop=legend_font,
)

fig.savefig(OUTPUT_DIR / "l2_l3_application_distribution.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "l2_l3_application_distribution.png", dpi=DPI, facecolor="white")
plt.close(fig)

print(f"L2 questions: {int(v2.sum()):,}; L3 questions: {int(v3.sum()):,}")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
