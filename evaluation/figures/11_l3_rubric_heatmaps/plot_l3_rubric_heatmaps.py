"""Plot rubric-score matrices whose cells contain density area sparklines."""
from __future__ import annotations

from collections import defaultdict
import csv
from pathlib import Path
import sys

from matplotlib import colors
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Rectangle
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, BLUE_DARK, BLUE_LIGHT,
    INK, PALE_GREY, PURPLE, SLATE, TEAL, TEAL_LIGHT,
    FONT_SIZE_DETAIL, FONT_SIZE_KEY, plt,
)
from result_utils import display_name, read_csv  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 190
FIGURE_HEIGHT_MM = 205
DPI = 500
TYPES = ("DG1", "DG2")
TYPE_LABELS = {"DG1": "Layer Design", "DG2": "System Design"}
DIMENSIONS = {
    "DG1": (
        "Stack Architecture", "Triboelectric Materials", "Electrodes", "Substrate",
        "Interfaces", "Geometry", "Mechanical Compliance",
        "Environmental Robustness", "Output Budget", "Validation",
    ),
    "DG2": (
        "Device Architecture", "Channels", "Packaging", "Signal Conditioning",
        "Acquisition", "Digitization", "Energy", "Processing", "Calibration",
        "Failure Validation",
    ),
}
CMAPS = {
    "DG1": colors.LinearSegmentedColormap.from_list(
        "layer_design", [PALE_GREY, BLUE_LIGHT, TEAL_LIGHT, TEAL, BLUE, BLUE_DARK]
    ),
    "DG2": colors.LinearSegmentedColormap.from_list(
        "system_design", [PALE_GREY, "#D9D2EA", "#B3A6D3", "#8C78B9", PURPLE, "#514475"]
    ),
}
AREA_COLORS = {"DG1": "#173B62", "DG2": "#49376B"}
KDE_GRID = np.linspace(0.0, 1.0, 25)
KDE_BANDWIDTH = 0.055


summary = {row["model"]: row for row in read_csv("model_summary.csv")}
models = sorted(
    summary,
    key=lambda model: (-float(summary[model]["l3_score"]), display_name(model)),
)
summary_rows = read_csv("rubric_summary.csv")
score_lookup = {
    (row["model"], row["question_type"], row["dimension"]): float(row["score"])
    for row in summary_rows
}
matrices = {
    question_type: np.asarray([
        [score_lookup[(model, question_type, dimension)] for dimension in DIMENSIONS[question_type]]
        for model in models
    ])
    for question_type in TYPES
}

# Preserve every criterion-level observation so a cell shows a distribution,
# not a synthetic profile reconstructed from its aggregate mean.
distribution_lookup: dict[tuple[str, str, str], list[tuple[float, float]]] = defaultdict(list)
item_rows = read_csv("rubric_item_scores.csv")
for row in item_rows:
    if row["question_type"] not in TYPES:
        continue
    distribution_lookup[(
        row["model"], row["question_type"], row["dimension"],
    )].append((float(row["score"]), float(row["weight"])))

expected_cells = len(models) * sum(len(DIMENSIONS[value]) for value in TYPES)
if len(distribution_lookup) != expected_cells:
    raise RuntimeError(
        f"Incomplete rubric distributions: {len(distribution_lookup)}/{expected_cells} cells"
    )

all_scores = np.concatenate([matrix.ravel() for matrix in matrices.values()])
score_min = np.floor(float(all_scores.min()) * 10) / 10
norm = colors.Normalize(vmin=score_min, vmax=1.0)


def weighted_density(observations: list[tuple[float, float]]) -> np.ndarray:
    """Boundary-corrected weighted Gaussian density on the common 0–1 grid."""
    values = np.asarray([value for value, _ in observations], dtype=float)
    weights = np.asarray([weight for _, weight in observations], dtype=float)
    weights /= weights.sum()
    grid = KDE_GRID[:, None]
    # Reflect samples around 0 and 1 so densities do not collapse where rubric
    # judges frequently assign exact boundary scores.
    kernels = (
        np.exp(-0.5 * ((grid - values[None, :]) / KDE_BANDWIDTH) ** 2)
        + np.exp(-0.5 * ((grid + values[None, :]) / KDE_BANDWIDTH) ** 2)
        + np.exp(-0.5 * ((grid - (2.0 - values[None, :])) / KDE_BANDWIDTH) ** 2)
    )
    density = kernels @ weights
    maximum = float(density.max())
    return density / maximum if maximum > 0 else np.zeros_like(density)


fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)

# A 58-mm, ten-column matrix gives 5.8-mm square cells. Twenty-nine rows
# therefore occupy 168.2 mm. The two panels are separated by only 5 mm;
# the taller canvas accommodates the rotated rubric labels and color scales.
heatmap_width_mm = 58.0
heatmap_width = heatmap_width_mm / FIGURE_WIDTH_MM
heatmap_height = (heatmap_width_mm * len(models) / 10.0) / FIGURE_HEIGHT_MM
heatmap_bottom = 32.0 / FIGURE_HEIGHT_MM
panel_gap = 5.0 / FIGURE_WIDTH_MM
heatmap_lefts = (
    45.0 / FIGURE_WIDTH_MM,
    45.0 / FIGURE_WIDTH_MM + heatmap_width + panel_gap,
)

for panel_index, (question_type, heatmap_left) in enumerate(zip(TYPES, heatmap_lefts)):
    matrix = matrices[question_type]
    ax = fig.add_axes([
        heatmap_left, heatmap_bottom, heatmap_width, heatmap_height,
    ])

    # Draw each cell independently. A very small inset creates a white seam,
    # while the hairline dark edge makes every square a discrete unit.
    cell_inset = 0.060
    for row_index in range(len(models)):
        for column_index in range(len(DIMENSIONS[question_type])):
            ax.add_patch(Rectangle(
                (
                    column_index - 0.5 + cell_inset,
                    row_index - 0.5 + cell_inset,
                ),
                1.0 - 2.0 * cell_inset,
                1.0 - 2.0 * cell_inset,
                facecolor=CMAPS[question_type](
                    norm(matrix[row_index, column_index])
                ),
                edgecolor=INK,
                linewidth=0.22,
                zorder=0,
            ))

    # Every square contains its own density line and filled area. Horizontal
    # position is rubric score (0 left, 1 right); height is within-cell density.
    for row_index, model in enumerate(models):
        for column_index, dimension in enumerate(DIMENSIONS[question_type]):
            density = weighted_density(
                distribution_lookup[(model, question_type, dimension)]
            )
            cell_x = column_index - 0.43 + 0.86 * KDE_GRID
            baseline = row_index + 0.37
            curve_y = baseline - 0.68 * density
            ax.fill_between(
                cell_x, baseline, curve_y,
                color=AREA_COLORS[question_type], alpha=0.24,
                linewidth=0.0, zorder=2,
            )
            ax.plot(
                cell_x, curve_y, color=AREA_COLORS[question_type],
                linewidth=0.34, alpha=0.96, zorder=3,
            )

    ax.set_xlim(-0.5, 9.5)
    ax.set_ylim(len(models) - 0.5, -0.5)
    ax.set_xticks(np.arange(10))
    ax.set_xticklabels(
        DIMENSIONS[question_type], rotation=52, ha="right", va="top",
        rotation_mode="anchor", fontproperties=ARIAL,
        fontsize=FONT_SIZE_DETAIL,
    )
    ax.set_yticks(np.arange(len(models)))
    if panel_index == 0:
        ax.set_yticklabels(
            [display_name(model) for model in models],
            fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
        )
        ax.set_ylabel(
            "Model", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY,
            color=INK, labelpad=5,
        )
    else:
        ax.set_yticklabels([])
        ax.tick_params(axis="y", left=False)
    ax.set_title(
        TYPE_LABELS[question_type], fontproperties=ARIAL_BOLD,
        fontsize=FONT_SIZE_KEY, color=INK, pad=3,
    )
    ax.tick_params(
        axis="both", which="both", length=0, width=0,
        bottom=False, top=False, left=False, right=False, pad=2,
    )
    for spine in ax.spines.values():
        spine.set_visible(False)

# One shared x-axis title serves both matrices and removes duplicated wording.
matrix_group_center = (
    heatmap_lefts[0] + heatmap_lefts[1] + heatmap_width
) / 2.0
fig.text(
    matrix_group_center, 9.7 / FIGURE_HEIGHT_MM, "Rubric Dimension",
    ha="center", va="center", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK,
)

# Each panel has its own full-width horizontal color scale directly below it.
# Its ticks use exactly the same typeface and size as the model names.
colorbar_bottom = 4.8 / FIGURE_HEIGHT_MM
colorbar_height = 1.6 / FIGURE_HEIGHT_MM
colorbar_width = heatmap_width * 0.72
for heatmap_left, question_type in zip(heatmap_lefts, TYPES):
    cax = fig.add_axes([
        heatmap_left + heatmap_width - colorbar_width,
        colorbar_bottom,
        colorbar_width,
        colorbar_height,
    ])
    colorbar = fig.colorbar(
        ScalarMappable(norm=norm, cmap=CMAPS[question_type]),
        cax=cax, orientation="horizontal",
    )
    colorbar.set_ticks([score_min, 0.6, 1.0])
    colorbar.ax.tick_params(
        labelsize=FONT_SIZE_DETAIL, length=1.8, width=0.5, pad=2.0,
    )
    for label in colorbar.ax.get_xticklabels():
        label.set_fontproperties(ARIAL)
        label.set_fontsize(FONT_SIZE_DETAIL)
    # Keep the endpoint labels inside their own bars so the two scales can sit
    # close together without the adjacent 1.0 and 0.2 labels touching.
    colorbar.ax.get_xticklabels()[0].set_ha("left")
    colorbar.ax.get_xticklabels()[-1].set_ha("right")
    colorbar.outline.set_edgecolor(SLATE)
    colorbar.outline.set_linewidth(0.5)

fig.savefig(OUTPUT_DIR / "l3_rubric_heatmaps.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "l3_rubric_heatmaps.png", dpi=DPI, facecolor="white")
fig.savefig(OUTPUT_DIR / "l3_rubric_heatmaps.pdf", facecolor="white")
plt.close(fig)

with (OUTPUT_DIR / "rubric_dimension_scores.csv").open(
    "w", encoding="utf-8", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_rows[0].keys())
    writer.writeheader()
    writer.writerows(summary_rows)

print(
    f"Models: {len(models)}; cells: {expected_cells}; "
    f"criterion-level scores: {len(item_rows):,}"
)
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
