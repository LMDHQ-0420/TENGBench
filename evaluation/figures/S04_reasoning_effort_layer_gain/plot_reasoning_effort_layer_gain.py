"""Show GPT layer scores across four reasoning-effort settings."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

from matplotlib.patches import Patch
from matplotlib.transforms import Bbox
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE_DARK, BLUE_LIGHT, CORAL, INK, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from gpt_effort_utils import (  # noqa: E402
    LAYERS, MODELS, collect_effort_scores,
)


OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 100
FIGURE_HEIGHT_MM = 92
DPI = 500
DISPLAY_EFFORTS = ("low", "mid", "max", "xhigh")
DISPLAY_LABELS = ("Low", "Mid", "Max", "X-high")

scores, _, expected_counts = collect_effort_scores()

detail_rows: list[dict[str, str]] = []
for layer_index, layer in enumerate(LAYERS):
    for effort_index, effort in enumerate(DISPLAY_EFFORTS):
        for model, model_label, _ in MODELS:
            gain = scores[(model, effort, layer)] - scores[(model, "low", layer)]
            detail_rows.append({
                "model": model,
                "model_label": model_label,
                "layer": layer,
                "reasoning_effort": effort,
                "low_score": f"{scores[(model, 'low', layer)]:.8f}",
                "effort_score": f"{scores[(model, effort, layer)]:.8f}",
                "gain_over_low": f"{gain:.8f}",
            })

with (OUTPUT_DIR / "reasoning_effort_layer_gain.csv").open(
    "w", encoding="utf-8", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=detail_rows[0].keys())
    writer.writeheader()
    writer.writerows(detail_rows)

fig, axes = plt.subplots(
    nrows=len(LAYERS), ncols=1, sharex=True, sharey=True,
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)

# Restored grouped-bar design from the approved earlier version.
effort_colors = {
    "low": SLATE,
    "mid": BLUE_LIGHT,
    "max": BLUE_DARK,
    "xhigh": CORAL,
}
text_colors = {
    "low": "white",
    "mid": INK,
    "max": "white",
    "xhigh": "white",
}
model_x = np.arange(len(MODELS), dtype=float)
bar_width = 0.185
offsets = (np.arange(len(DISPLAY_EFFORTS)) - 1.5) * bar_width

for panel_index, (layer, ax) in enumerate(zip(LAYERS, axes)):
    for effort_index, effort in enumerate(DISPLAY_EFFORTS):
        values = np.asarray([
            scores[(model, effort, layer)] for model, _, _ in MODELS
        ])
        low_values = np.asarray([
            scores[(model, "low", layer)] for model, _, _ in MODELS
        ])
        bars = ax.bar(
            model_x + offsets[effort_index], values,
            width=bar_width * 0.96,
            color=effort_colors[effort], edgecolor="white",
            linewidth=0.35, zorder=2,
        )
        for bar, value, low_value in zip(bars, values, low_values):
            label = (
                f"{value:.3f}" if effort == "low"
                else f"+{value - low_value:.3f}"
            )
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                max(0.045, value - 0.025), label,
                ha="center", va="top", rotation=90,
                color=text_colors[effort],
                fontproperties=ARIAL_BOLD,
                fontsize=FONT_SIZE_DETAIL - 0.15,
                zorder=3,
            )

    ax.text(
        0.018, 0.90, layer, transform=ax.transAxes,
        ha="left", va="top", color=INK,
        fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL,
    )
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.set_yticklabels(
        ["0", "0.5", "1.0"],
        fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
    )
    ax.set_xticks(model_x)
    if panel_index == len(LAYERS) - 1:
        model_labels = [
            label.replace("GPT-5.6 ", "GPT-5.6\n")
            for _, label, _ in MODELS
        ]
        ax.set_xticklabels(
            model_labels, fontproperties=ARIAL,
            fontsize=FONT_SIZE_DETAIL, linespacing=0.92,
        )
    else:
        ax.set_xticklabels([])
    for side in ("left", "right", "top", "bottom"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color(SLATE)
        ax.spines[side].set_linewidth(0.78)
    ax.tick_params(
        axis="both", which="major", direction="out",
        length=2.4, width=0.72, color=SLATE,
        labelcolor=INK, pad=1.8,
    )
    ax.grid(False)

axes[-1].set_xlabel(
    "Model", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, labelpad=2.4,
)
fig.text(
    0.027, 0.48, "Layer Score", rotation=90,
    ha="center", va="center", color=INK,
    fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY,
)

legend_font = ARIAL.copy()
legend_font.set_size(FONT_SIZE_DETAIL)
legend_handles = [
    Patch(facecolor=effort_colors[effort], edgecolor="none", label=label)
    for effort, label in zip(DISPLAY_EFFORTS, DISPLAY_LABELS)
]
legend = fig.legend(
    handles=legend_handles,
    loc="lower right", bbox_to_anchor=(0.995, 0.035), frameon=False,
    ncol=4, handlelength=1.9125, handleheight=0.85,
    handletextpad=0.28, columnspacing=0.72,
    borderaxespad=0.0, prop=legend_font,
)

fig.subplots_adjust(left=0.115, right=0.995, top=0.985, bottom=0.175, hspace=0.105)

fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
bottom_crop_bbox = Bbox.from_extents(
    0, tight_bbox.y0 - 1.5 / 25.4,
    fig.get_figwidth(), fig.get_figheight(),
)
fig.savefig(OUTPUT_DIR / "reasoning_effort_layer_gain.svg", facecolor="white",
            bbox_inches=bottom_crop_bbox, pad_inches=0)
fig.savefig(
    OUTPUT_DIR / "reasoning_effort_layer_gain.png", dpi=DPI, facecolor="white",
    bbox_inches=bottom_crop_bbox, pad_inches=0,
)
fig.savefig(OUTPUT_DIR / "reasoning_effort_layer_gain.pdf", facecolor="white",
            bbox_inches=bottom_crop_bbox, pad_inches=0)
plt.close(fig)

print(
    f"GPT models: {len(MODELS)}; layer gains: {len(LAYERS)} x "
    f"{len(DISPLAY_EFFORTS)}; baseline: low; "
    f"per configuration: {sum(expected_counts.values()):,} results"
)
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
