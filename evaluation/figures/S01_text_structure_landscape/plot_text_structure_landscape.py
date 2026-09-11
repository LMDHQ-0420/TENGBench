"""Plot joint question/excerpt length density for each benchmark layer."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from matplotlib import colors
from matplotlib.ticker import NullLocator
from matplotlib.transforms import Bbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import ARIAL, ARIAL_BOLD, BLUE, BLUE_LIGHT, INK, FONT_SIZE_DETAIL, FONT_SIZE_KEY, plt  # noqa: E402
from supplement_utils import LAYER_LABELS, export_figure, load_questions, open_axes, set_tick_font, write_rows  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
WIDTH_MM, HEIGHT_MM = 110, 185

questions = load_questions()
rows = [{
    "qa_id": record["qa_id"], "layer": record["layer"], "question_type": record["type"],
    "question_words": len(record["question"].split()),
    "excerpt_words": len(record["source_excerpt"].split()),
} for record in questions]

xmax = int(np.ceil(max(row["question_words"] for row in rows) / 25) * 25)
ymax = int(np.ceil(max(row["excerpt_words"] for row in rows) / 50) * 50)
cmap = colors.LinearSegmentedColormap.from_list("text_density", ["#EEF1F5", BLUE_LIGHT, BLUE])

fig, axes = plt.subplots(3, 1, figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4),
                         facecolor="white", sharex=True, sharey=True)
fig.subplots_adjust(left=0.155, right=0.865, bottom=0.105, top=0.965, hspace=0.22)
fig.canvas.draw()
hexagons = []
for ax, layer in zip(axes, ("L1", "L2", "L3")):
    subset = [row for row in rows if row["layer"] == layer]

    # Matplotlib recommends nx / ny ≈ sqrt(3) for square axes.  Correct that
    # ratio by the actual rendered axes aspect so the cells remain regular
    # hexagons after the three panels are stacked on the final 110-mm canvas.
    bbox = ax.get_window_extent()
    display_aspect = bbox.width / bbox.height
    nx = 36
    ny = max(3, round(nx / (np.sqrt(3.0) * display_aspect)))
    hb = ax.hexbin([row["question_words"] for row in subset],
                   [row["excerpt_words"] for row in subset],
                   gridsize=(nx, ny), mincnt=1, cmap=cmap,
                   extent=(0, xmax, 0, ymax),
                   linewidths=0.25, edgecolors="white")
    hexagons.append(hb)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_title(LAYER_LABELS[layer], fontproperties=ARIAL_BOLD,
                 fontsize=FONT_SIZE_KEY, color=INK, pad=4)
    open_axes(ax)
    ax.tick_params(axis="x", labelbottom=True)
    set_tick_font(ax, FONT_SIZE_DETAIL)

maximum = max(float(np.max(item.get_array())) for item in hexagons)
norm = colors.LogNorm(vmin=1, vmax=max(2, maximum))
for item in hexagons:
    item.set_norm(norm)

fig.supxlabel("Question-Stem Length (Words)", x=0.505, y=0.058,
              fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK)
fig.supylabel("Source-Excerpt Length (Words)", x=0.065,
              fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK)
middle_position = axes[1].get_position()
cax = fig.add_axes([0.900, middle_position.y0, 0.018, middle_position.height])
colorbar = fig.colorbar(hexagons[-1], cax=cax)
colorbar.set_ticks([1, maximum])
colorbar.set_ticklabels(["1", f"{int(maximum)}"])
colorbar.minorticks_off()
colorbar.ax.yaxis.set_minor_locator(NullLocator())
colorbar.set_label("Question Density", fontproperties=ARIAL_BOLD,
                   fontsize=7.0, color=INK, labelpad=2)
colorbar.ax.tick_params(labelsize=FONT_SIZE_DETAIL, length=1.8, width=0.5, pad=1)
for label in colorbar.ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
colorbar.outline.set_linewidth(0.5)

write_rows(OUTPUT_DIR / "text_structure.csv",
           ["qa_id", "layer", "question_type", "question_words", "excerpt_words"], rows)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
tight_bbox = Bbox.from_extents(
    tight_bbox.x0 - 2.0 / 25.4, tight_bbox.y0 - 1.5 / 25.4,
    tight_bbox.x1 + 1.5 / 25.4, tight_bbox.y1 + 1.5 / 25.4,
)
export_figure(fig, OUTPUT_DIR, "text_structure_landscape",
              bbox_inches=tight_bbox, pad_inches=0)
plt.close(fig)
print(f"Questions: {len(rows)}; ranges: {xmax} question words, {ymax} excerpt words")
print(f"Canvas: {WIDTH_MM} x {HEIGHT_MM} mm")
