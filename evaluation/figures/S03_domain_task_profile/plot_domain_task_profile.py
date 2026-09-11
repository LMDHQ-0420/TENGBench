"""In-cell bar matrix of domain performance across ten assessment focuses."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
from matplotlib.patches import Rectangle
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import ARIAL, ARIAL_BOLD, GRID, INK, PALE_GREY, FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt  # noqa: E402
from supplement_utils import DOMAIN_LABELS, LAYER_COLORS, TASK_TYPES, TYPE_LABELS, balanced_domain_scores, export_figure, load_scored_items, open_axes, set_tick_font, write_rows  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
WIDTH_MM, HEIGHT_MM = 190, 120

items = load_scored_items()
scores = balanced_domain_scores(items)
models = sorted({row["model"] for row in items})
domains = sorted(DOMAIN_LABELS, key=lambda domain: (-np.median([scores[(model, domain)] for model in models]), DOMAIN_LABELS[domain]))
groups: dict[tuple[str, str], list[float]] = defaultdict(list)
for row in items:
    groups[(row["domain"], row["question_type"])].append(row["score"])
matrix = np.asarray([[np.mean(groups[(domain, task)]) for task in TASK_TYPES] for domain in domains])
task_layers = ["L1"] * 4 + ["L2"] * 4 + ["L3"] * 2

fig, ax = plt.subplots(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), facecolor="white")
for row_index, domain in enumerate(domains):
    if row_index % 2:
        ax.axhspan(row_index - 0.5, row_index + 0.5, color=PALE_GREY, alpha=0.55, zorder=0)
    for column_index, (task, layer) in enumerate(zip(TASK_TYPES, task_layers)):
        value = matrix[row_index, column_index]
        x0 = column_index - 0.40
        ax.add_patch(Rectangle((x0, row_index - 0.16), 0.80, 0.32,
                               facecolor=GRID, edgecolor="none", alpha=0.62, zorder=1))
        ax.add_patch(Rectangle((x0, row_index - 0.16), 0.80 * value, 0.32,
                               facecolor=LAYER_COLORS[layer], edgecolor="none", zorder=2))
        ax.scatter([x0 + 0.80 * value], [row_index], s=7.5,
                   facecolor=LAYER_COLORS[layer], edgecolor="white",
                   linewidth=0.3, zorder=3)

ax.set_xlim(-0.55, len(TASK_TYPES) - 0.45)
ax.set_ylim(len(domains) - 0.5, -0.5)
ax.set_yticks(np.arange(len(domains)))
ax.set_yticklabels([DOMAIN_LABELS[value] for value in domains])
ax.set_xticks(np.arange(len(TASK_TYPES)))
ax.set_xticklabels([TYPE_LABELS[value] for value in TASK_TYPES], rotation=48,
                   ha="right", rotation_mode="anchor")
ax.tick_params(axis="x", top=False, labeltop=False, bottom=True, labelbottom=True, pad=2)
ax.set_ylabel("Application Domain", fontproperties=ARIAL_BOLD,
              fontsize=FONT_SIZE_KEY, color=INK, labelpad=4)
for center, label, layer in ((1.5, "Fundamentals", "L1"),
                             (5.5, "Applied Reasoning", "L2"),
                             (8.5, "Engineering Design", "L3")):
    ax.text(center, 1.080, label, transform=ax.get_xaxis_transform(), ha="center",
            va="bottom", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_LABEL,
            color=LAYER_COLORS[layer], clip_on=False)
    ax.plot([center - (1.62 if layer != "L3" else 0.62),
             center + (1.62 if layer != "L3" else 0.62)], [1.055, 1.055],
            transform=ax.get_xaxis_transform(), color=LAYER_COLORS[layer],
            linewidth=1.4, solid_capstyle="round", clip_on=False)
open_axes(ax)
set_tick_font(ax, FONT_SIZE_DETAIL)

fig.text(0.560, 0.025, "Assessment Focus", ha="center", va="center",
         fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK)
fig.text(0.975, 0.025, "Bar Length = Score (0–1)", ha="right", va="center",
         fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_LABEL, color=INK)
fig.subplots_adjust(left=0.135, right=0.992, bottom=0.205, top=0.815)

rows = [{"domain": domain, "question_type": task, "focus": TYPE_LABELS[task],
         "mean_score": f"{matrix[i, j]:.8f}"}
        for i, domain in enumerate(domains) for j, task in enumerate(TASK_TYPES)]
write_rows(OUTPUT_DIR / "domain_task_scores.csv",
           ["domain", "question_type", "focus", "mean_score"], rows)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
top_crop_bbox = Bbox.from_extents(
    0, 0, fig.get_figwidth(), tight_bbox.y1 + 1.5 / 25.4,
)
export_figure(fig, OUTPUT_DIR, "domain_task_profile",
              bbox_inches=top_crop_bbox, pad_inches=0)
plt.close(fig)
print(f"Domains: {len(domains)}; task types: {len(TASK_TYPES)}")
print(f"Canvas: {WIDTH_MM} x {HEIGHT_MM} mm")
