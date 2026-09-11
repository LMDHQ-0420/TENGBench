"""Plot the application-category/year matrix as a count-encoded dot map."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

from matplotlib import colors
from matplotlib.cm import ScalarMappable
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, BLUE_DARK, BLUE_LIGHT, GRID, INK, PALE_GREY,
    SLATE, FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)

CODE_ROOT = Path(__file__).resolve().parents[3]
PAPER_ROOT = CODE_ROOT / "papers" / "qualified"
OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 120
FIGURE_HEIGHT_MM = 50
DPI = 500
LABEL_OVERRIDES = {
    "energyharv": "Energy Harv.", "hmi": "HMI", "iot": "IoT",
    "smarttextile": "Smart Tex.", "biomedical": "Biomed.",
}


papers: list[dict] = []
for path in sorted(PAPER_ROOT.glob("**/index.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    raw_year = int(record["date"][:4])
    record["plot_year"] = 2024 if raw_year <= 2021 else raw_year
    papers.append(record)

category_totals = Counter(paper["subcategory"] for paper in papers)
categories = [name for name, _ in category_totals.most_common()]
years = list(range(
    min(paper["plot_year"] for paper in papers),
    max(paper["plot_year"] for paper in papers) + 1,
))
matrix = np.zeros((len(years), len(categories)), dtype=int)
year_index = {year: index for index, year in enumerate(years)}
category_index = {category: index for index, category in enumerate(categories)}
for paper in papers:
    matrix[year_index[paper["plot_year"]], category_index[paper["subcategory"]]] += 1

cmap = colors.LinearSegmentedColormap.from_list(
    "paper_dots", ["#E7ECF6", BLUE_LIGHT, "#7189C2", BLUE, BLUE_DARK]
)
norm = colors.PowerNorm(gamma=0.58, vmin=0, vmax=float(matrix.max()))

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)
ax = fig.add_axes([0.105, 0.330, 0.785, 0.628])
cax = fig.add_axes([0.910, 0.505, 0.012, 0.300])

columns, rows = np.meshgrid(np.arange(len(categories)), np.arange(len(years)))
flat_values = matrix.ravel()
present = flat_values > 0
size = 34.0 + 270.0 * (flat_values / matrix.max()) ** 0.72

ax.scatter(
    columns.ravel()[~present], rows.ravel()[~present],
    s=24, facecolor="white", edgecolor=GRID, linewidth=0.45, zorder=2,
)
ax.scatter(
    columns.ravel()[present], rows.ravel()[present],
    s=size[present], c=flat_values[present], cmap=cmap, norm=norm,
    edgecolor="white", linewidth=0.45, zorder=3,
)

ax.set_xlim(-0.5, len(categories) - 0.5)
ax.set_ylim(len(years) - 0.5, -0.5)
ax.set_aspect("equal", adjustable="box")
ax.set_xticks(np.arange(len(categories)))
ax.set_yticks(np.arange(len(years)))
ax.set_xticklabels(
    [LABEL_OVERRIDES.get(value, value.replace("_", " ").title()) for value in categories],
    rotation=55, ha="right", rotation_mode="anchor",
    fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
)
ax.set_yticklabels(years, fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL)
ax.set_xlabel(
    "Application Category", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=4,
)
ax.set_ylabel(
    "Publication Year", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.tick_params(
    which="major", axis="both", direction="out",
    length=2.3, width=0.55, color=SLATE, pad=2,
)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_visible(True)
    ax.spines[side].set_color(SLATE)
    ax.spines[side].set_linewidth(0.62)

# Explicit terminal ticks make the two open axes read as complete coordinate
# axes without reintroducing a surrounding box.
terminal_length = 0.018
ax.plot(
    [1.0, 1.0], [0.0, -terminal_length], transform=ax.transAxes,
    color=SLATE, linewidth=0.62, clip_on=False, zorder=5,
)
ax.plot(
    [0.0, -terminal_length], [1.0, 1.0], transform=ax.transAxes,
    color=SLATE, linewidth=0.62, clip_on=False, zorder=5,
)

# Match the colour scale to the actual square-cell matrix height after the
# equal-aspect constraint has adjusted the axes box.
fig.canvas.draw()
matrix_box = ax.get_position()
cax.set_position([0.910, matrix_box.y0, 0.012, matrix_box.height])

colorbar = fig.colorbar(
    ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="vertical",
)
colorbar.set_ticks([0, int(matrix.max())])
colorbar.set_label(
    "Paper Count", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_LABEL, labelpad=2,
)
colorbar.ax.tick_params(labelsize=FONT_SIZE_DETAIL, length=1.8, width=0.5, pad=1)
for label in colorbar.ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
colorbar.outline.set_edgecolor(SLATE)
colorbar.outline.set_linewidth(0.5)

fig.savefig(OUTPUT_DIR / "category_year_dotmap.png", dpi=DPI, facecolor="white")
fig.savefig(OUTPUT_DIR / "category_year_dotmap.svg", facecolor="white")
plt.close(fig)

print(f"Papers: {len(papers)}; categories: {len(categories)}; years: {years[0]}-{years[-1]}")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm; square dot-map cells")
