"""Visualize GPT scores and gains across ordered reasoning-effort categories."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

from matplotlib.lines import Line2D
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, GRID, INK, PALE_GREY, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_KEY, plt,
)
from gpt_effort_utils import (  # noqa: E402
    EFFORT_LABELS, EFFORTS, MODELS, collect_effort_scores,
)

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 190
FIGURE_WIDTH_MM = 100
FIGURE_HEIGHT_MM = 75
DPI = 500
scores, summary_rows, expected_counts = collect_effort_scores()

with (OUTPUT_DIR / "gpt_reasoning_effort_scores.csv").open(
    "w", encoding="utf-8", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_rows[0].keys())
    writer.writeheader()
    writer.writerows(summary_rows)

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)

# Reasoning effort is ordinal, not a continuous numerical variable.  Equal
# x-spacing is therefore used only to position the four observed categories;
# no interpolation, regression, or continuous-effort scale is implied.
ax = fig.add_axes([0.125, 0.155, 0.855, 0.820])
# Shift every observed effort position by the same amount.  This preserves the
# ordinal spacing while reserving enough right margin for centered X-high labels.
x = np.arange(len(EFFORTS), dtype=float) - 0.12
model_values = {
    model: np.asarray([scores[(model, effort, "Overall")] for effort in EFFORTS])
    for model, _, _ in MODELS
}

# A compact range rail at each category summarizes cross-model dispersion and
# makes the categorical sampling positions visually explicit.
all_values = np.vstack([model_values[model] for model, _, _ in MODELS])
for index in range(len(EFFORTS)):
    low = float(np.min(all_values[:, index]))
    high = float(np.max(all_values[:, index]))
    ax.plot(
        [x[index], x[index]], [low, high], color=PALE_GREY, linewidth=10.0,
        solid_capstyle="round", zorder=1,
    )

legend_handles: dict[str, Line2D] = {}
for model, model_label, color in MODELS:
    values = model_values[model]
    ax.plot(
        x, values, color=color, linewidth=1.25,
        marker="o", markersize=4.8, markerfacecolor=color,
        markeredgecolor="white", markeredgewidth=0.65,
        solid_capstyle="round", zorder=3,
    )
    legend_handles[model] = Line2D(
        [], [], color=color, linewidth=1.25, marker="o", markersize=4.0,
        markerfacecolor=color, markeredgecolor="white", markeredgewidth=0.5,
        label=model_label,
    )
    baseline = float(values[0])
    for index in range(len(EFFORTS)):
        difference = float(values[index]) - baseline
        below = model in {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}
        text_offset = (0.0, -5.2 if below else 5.2)
        value_label = f"{values[index]:.3f}" if index == 0 else f"{difference:+.3f}"
        ax.annotate(
            value_label.replace("-", "−"),
            xy=(x[index], values[index]),
            xytext=text_offset,
            textcoords="offset points",
            ha="center",
            va="top" if below else "bottom",
            fontproperties=ARIAL_BOLD,
            fontsize=FONT_SIZE_DETAIL,
            color=color,
            annotation_clip=True,
            zorder=5,
        )

ax.set_xlim(-0.40, len(EFFORTS) - 0.90)
ax.set_ylim(0.50, 0.76)
ax.set_xticks(x)
ax.set_xticklabels(EFFORT_LABELS)
ax.set_yticks(np.arange(0.50, 0.751, 0.05))
ax.set_xlabel(
    "Reasoning Effort", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.set_ylabel(
    "Overall Score", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=4,
)
ax.grid(axis="y", color=GRID, linewidth=0.38, alpha=0.72, zorder=0)
ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
for label in ax.get_xticklabels() + ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
for spine in ax.spines.values():
    spine.set_visible(True)
    spine.set_color(SLATE)
    spine.set_linewidth(0.62)

legend_font = ARIAL.copy()
legend_font.set_size(FONT_SIZE_DETAIL)
ax.legend(
    # Matplotlib fills legend columns top-to-bottom.  This ordering yields
    # Luna / Terra / Sol on row 1 and GPT-5.5 / GPT-5.2 on row 2.
    handles=[legend_handles[key] for key in (
        "gpt-5.6-luna", "gpt-5.5", "gpt-5.6-terra", "gpt-5.2", "gpt-5.6-sol"
    )],
    loc="lower right", bbox_to_anchor=(0.985, 0.018),
    frameon=False, ncol=3, columnspacing=0.70, handletextpad=0.26,
    borderaxespad=0.0, prop=legend_font,
)

fig.savefig(OUTPUT_DIR / "gpt_reasoning_effort.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "gpt_reasoning_effort.png", dpi=DPI, facecolor="white")
fig.savefig(OUTPUT_DIR / "gpt_reasoning_effort.pdf", facecolor="white")
plt.close(fig)

print(
    f"GPT models: {len(MODELS)}; efforts: {len(EFFORTS)}; "
    f"per configuration: {sum(expected_counts.values()) if expected_counts else 0:,} results"
)
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
