"""Raincloud summary of balanced model scores in each application domain."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import ARIAL, ARIAL_BOLD, INK, PALE_GREY, FONT_SIZE_DETAIL, FONT_SIZE_KEY, plt  # noqa: E402
from result_utils import MODEL_META, display_name  # noqa: E402
from supplement_utils import DOMAIN_COLORS, DOMAIN_LABELS, balanced_domain_scores, export_figure, load_scored_items, open_axes, set_tick_font, write_rows  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
WIDTH_MM, HEIGHT_MM = 150, 125

items = load_scored_items()
scores = balanced_domain_scores(items)
models = sorted(MODEL_META)
domains = sorted(DOMAIN_LABELS, key=lambda domain: (-np.median([scores[(model, domain)] for model in models]), DOMAIN_LABELS[domain]))

fig, ax = plt.subplots(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), facecolor="white")
rng = np.random.default_rng(20260908)
rows: list[dict] = []

for position, domain in enumerate(domains):
    values = np.asarray([scores[(model, domain)] for model in models])
    color = DOMAIN_COLORS[domain]
    if position % 2:
        ax.axhspan(position - 0.5, position + 0.5, color=PALE_GREY, alpha=0.68, zorder=0)
    violin = ax.violinplot(values, positions=[position], orientation="horizontal", widths=0.72,
                           showmeans=False, showmedians=False, showextrema=False,
                           bw_method=0.32)
    for body in violin["bodies"]:
        vertices = body.get_paths()[0].vertices
        vertices[:, 1] = np.minimum(vertices[:, 1], position)
        body.set_facecolor(color)
        body.set_edgecolor("none")
        body.set_alpha(0.28)
        body.set_zorder(1)
    jitter = 0.14 + rng.uniform(0.015, 0.28, size=len(values))
    ax.scatter(values, position + jitter, s=10.5, facecolor=color,
               edgecolor="white", linewidth=0.35, alpha=0.82, zorder=3)
    q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
    ax.plot([q1, q3], [position, position], color=color, linewidth=2.2,
            solid_capstyle="round", zorder=4)
    ax.scatter([median], [position], s=26, facecolor=color, edgecolor="white",
               linewidth=0.55, zorder=5)
    for model, value in zip(models, values):
        rows.append({"domain": domain, "model": model, "display_name": display_name(model),
                     "balanced_domain_score": f"{value:.8f}"})

all_values = np.asarray([float(row["balanced_domain_score"]) for row in rows])
xmin = np.floor((all_values.min() - 0.02) * 20) / 20
xmax = np.ceil((all_values.max() + 0.02) * 20) / 20
ax.set_xlim(xmin, xmax)
ax.set_ylim(len(domains) - 0.45, -0.55)
ax.set_yticks(np.arange(len(domains)))
ax.set_yticklabels([DOMAIN_LABELS[domain] for domain in domains])
ax.set_xlabel("Balanced Domain Score", fontproperties=ARIAL_BOLD,
              fontsize=FONT_SIZE_KEY, color=INK, labelpad=3)
ax.set_ylabel("Application Domain", fontproperties=ARIAL_BOLD,
              fontsize=FONT_SIZE_KEY, color=INK, labelpad=4)
open_axes(ax)
set_tick_font(ax, FONT_SIZE_DETAIL)
fig.subplots_adjust(left=0.245, right=0.985, bottom=0.105, top=0.985)

write_rows(OUTPUT_DIR / "domain_score_distribution.csv",
           ["domain", "model", "display_name", "balanced_domain_score"], rows)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
tight_bbox = Bbox.from_extents(
    tight_bbox.x0 - 2.0 / 25.4, tight_bbox.y0,
    tight_bbox.x1 + 1.5 / 25.4, tight_bbox.y1 + 1.5 / 25.4,
)
export_figure(fig, OUTPUT_DIR, "domain_score_distribution",
              bbox_inches=tight_bbox, pad_inches=0)
plt.close(fig)
print(f"Domains: {len(domains)}; models per domain: {len(models)}")
print(f"Canvas: {WIDTH_MM} x {HEIGHT_MM} mm")
