"""PCA biplot of model-relative capability profiles across ten subtasks."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from matplotlib.legend_handler import HandlerPatch
from matplotlib.patches import Ellipse, FancyArrowPatch, Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import ARIAL, ARIAL_BOLD, GRID, INK, SLATE, FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt  # noqa: E402
from result_utils import MODEL_META, display_name, read_csv  # noqa: E402
from supplement_utils import FAMILY_COLORS, LAYER_COLORS, TASK_TYPES, TYPE_LABELS, export_figure, open_axes, set_tick_font, write_rows  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
WIDTH_MM, HEIGHT_MM = 190, 130
PROVIDER_COLORS = dict(FAMILY_COLORS)
PROVIDER_COLORS["minimax"] = "#5F6470"


class HandlerArrow(HandlerPatch):
    """Draw a full legend arrow with its triangular head at the line end."""

    def create_artists(self, legend, orig_handle, xdescent, ydescent,
                       width, height, fontsize, trans):
        center_y = ydescent + 0.5 * height
        arrow = FancyArrowPatch(
            (xdescent, center_y), (xdescent + width, center_y),
            arrowstyle="-|>", mutation_scale=0.86 * fontsize,
            linewidth=orig_handle.get_linewidth(),
            color=orig_handle.get_edgecolor(),
            shrinkA=0, shrinkB=0, transform=trans,
        )
        return [arrow]


def minimum_volume_enclosing_ellipse(points: np.ndarray,
                                     tolerance: float = 1e-7):
    """Compute the 2-D minimum-volume enclosing ellipse (Khachiyan method)."""
    point_count, dimension = points.shape
    q = np.vstack([points.T, np.ones(point_count)])
    weights = np.full(point_count, 1.0 / point_count)
    for _ in range(20000):
        x_matrix = (q * weights) @ q.T
        leverage = np.einsum(
            "ij,jk,ki->i", q.T, np.linalg.pinv(x_matrix), q,
        )
        maximum_index = int(np.argmax(leverage))
        maximum = float(leverage[maximum_index])
        step = (maximum - dimension - 1.0) / (
            (dimension + 1.0) * (maximum - 1.0)
        )
        if step <= tolerance:
            break
        updated = (1.0 - step) * weights
        updated[maximum_index] += step
        if np.linalg.norm(updated - weights) <= tolerance:
            weights = updated
            break
        weights = updated

    center = weights @ points
    covariance = ((points.T * weights) @ points
                  - np.outer(center, center))
    shape = dimension * covariance
    eigenvalues, eigenvectors = np.linalg.eigh(shape)
    order = np.argsort(eigenvalues)[::-1]
    radii = np.sqrt(np.maximum(eigenvalues[order], 1e-12))
    principal = eigenvectors[:, order[0]]
    angle = np.degrees(np.arctan2(principal[1], principal[0]))
    return center, radii, angle

rows = read_csv("type_summary.csv")
lookup = {(row["model"], row["question_type"]): float(row["score"]) for row in rows}
PROVIDER_LABELS = {
    "chatgpt": "OpenAI", "claude": "Anthropic",
    "deepseek": "DeepSeek", "qwen": "Alibaba Cloud",
    "kimi": "Moonshot AI", "glm": "Zhipu AI", "minimax": "MiniMax",
}
mean_capability = {
    model: float(np.mean([lookup[(model, task)] for task in TASK_TYPES]))
    for model in MODEL_META
}
models = sorted(
    MODEL_META,
    key=lambda model: (
        PROVIDER_LABELS[MODEL_META[model].family], mean_capability[model]
    ),
    reverse=True,
)
matrix = np.asarray([[lookup[(model, task)] for task in TASK_TYPES] for model in models])
standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0, ddof=1)
# Remove each model's mean standardized score before PCA.  This suppresses the
# dominant general-performance factor and reveals relative task strengths.
profile_matrix = standardized - standardized.mean(axis=1, keepdims=True)
u, singular, vt = np.linalg.svd(profile_matrix, full_matrices=False)
coordinates = u[:, :2] * singular[:2]
loadings = vt[:2].T
explained = singular ** 2 / np.sum(singular ** 2)

# Fix arbitrary PCA signs so the axes keep a stable semantic orientation.
if np.mean(loadings[8:, 0]) < 0:  # engineering design points right
    coordinates[:, 0] *= -1
    loadings[:, 0] *= -1
if loadings[2, 1] < loadings[1, 1]:  # polarity points above modes
    coordinates[:, 1] *= -1
    loadings[:, 1] *= -1

fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), facecolor="white")
ax = fig.add_axes([0.075, 0.125, 0.650, 0.845])
key_ax = fig.add_axes([0.755, 0.055, 0.240, 0.915])
key_ax.axis("off")
ax.axhline(0, color=GRID, linewidth=0.55, zorder=0)
ax.axvline(0, color=GRID, linewidth=0.55, zorder=0)

xspan = np.ptp(coordinates[:, 0])
yspan = np.ptp(coordinates[:, 1])
POINT_AREA = 60

for family in sorted({MODEL_META[model].family for model in models}):
    index = [i for i, model in enumerate(models) if MODEL_META[model].family == family]
    points = coordinates[index]

    # A lightly padded minimum-volume enclosing ellipse follows the observed
    # provider range without implying a confidence interval.  Degenerate
    # two-point or nearly collinear groups use a rounded capsule instead.
    centered = points - points.mean(axis=0)
    if len(points) >= 3 and np.linalg.matrix_rank(centered) == 2:
        center, radii, angle = minimum_volume_enclosing_ellipse(points)
        padding = 1.12
        ax.add_patch(Ellipse(
            center, width=2 * padding * radii[0],
            height=2 * padding * radii[1], angle=angle,
            facecolor=PROVIDER_COLORS[family], edgecolor="none",
            alpha=0.082, zorder=0.7,
        ))
    else:
        pairwise = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
        first, second = np.unravel_index(np.argmax(pairwise), pairwise.shape)
        ax.plot(
            points[[first, second], 0], points[[first, second], 1],
            color=PROVIDER_COLORS[family], alpha=0.082,
            linewidth=24.0, solid_capstyle="round",
            zorder=0.7,
        )

    ax.scatter(points[:, 0], points[:, 1], s=POINT_AREA,
               facecolor=PROVIDER_COLORS[family],
               edgecolor="white", linewidth=0.60, zorder=4)

arrow_scale = min(0.48 * xspan / max(np.max(np.abs(loadings[:, 0])), 1e-9),
                  0.48 * yspan / max(np.max(np.abs(loadings[:, 1])), 1e-9))
for task_index, (task, loading) in enumerate(zip(TASK_TYPES, loadings)):
    endpoint = loading * arrow_scale
    layer = "L1" if task_index < 4 else "L2" if task_index < 8 else "L3"
    arrow_color = LAYER_COLORS[layer]
    ax.annotate("", xy=endpoint, xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color=arrow_color, lw=0.72,
                                shrinkA=0, shrinkB=0, mutation_scale=6), zorder=2)

xmin, xmax = coordinates[:, 0].min() - 0.15 * xspan, coordinates[:, 0].max() + 0.15 * xspan
ymin, ymax = coordinates[:, 1].min() - 0.18 * yspan, coordinates[:, 1].max() + 0.18 * yspan
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
for number, point in enumerate(coordinates, start=1):
    ax.annotate(str(number), xy=point, xytext=(0, -0.45),
                textcoords="offset points", ha="center", va="center",
                fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_DETAIL,
                color="white", zorder=5)

ax.set_xlabel(f"PC1 ({100 * explained[0]:.1f}%)", fontproperties=ARIAL_BOLD,
              fontsize=FONT_SIZE_KEY, color=INK, labelpad=3)
ax.set_ylabel(f"PC2 ({100 * explained[1]:.1f}%)", fontproperties=ARIAL_BOLD,
              fontsize=FONT_SIZE_KEY, color=INK, labelpad=3)
open_axes(ax, terminal_ticks=False)
# Keep the two terminal ticks inside the plotting area: the x-axis cap rises
# from its right endpoint, while the y-axis cap extends right from its top.
ax.plot([1, 1], [0, 0.018], transform=ax.transAxes, color=SLATE,
        linewidth=0.55, clip_on=False, zorder=10)
ax.plot([0, 0.018], [1, 1], transform=ax.transAxes, color=SLATE,
        linewidth=0.55, clip_on=False, zorder=10)
set_tick_font(ax, FONT_SIZE_DETAIL)

horizontal_axis_blend = ax.get_yaxis_transform()
ax.annotate(
    "Reasoning-Dominant", xy=(0.015, 0), xycoords=horizontal_axis_blend,
    xytext=(0, -3), textcoords="offset points",
    ha="left", va="top", fontproperties=ARIAL,
    fontsize=FONT_SIZE_DETAIL, color=SLATE,
)
ax.annotate(
    "Design-Dominant", xy=(0.985, 0), xycoords=horizontal_axis_blend,
    xytext=(0, -3), textcoords="offset points",
    ha="right", va="top", fontproperties=ARIAL,
    fontsize=FONT_SIZE_DETAIL, color=SLATE,
)
axis_blend = ax.get_xaxis_transform()
ax.annotate(
    "Attribute-Dominant", xy=(0, 0.985), xycoords=axis_blend,
    xytext=(-3, 0), textcoords="offset points",
    ha="right", va="bottom", rotation=90, rotation_mode="anchor",
    fontproperties=ARIAL,
    fontsize=FONT_SIZE_DETAIL, color=SLATE,
)
ax.annotate(
    "Process-Dominant", xy=(0, 0.015), xycoords=axis_blend,
    xytext=(-3, 0), textcoords="offset points",
    ha="left", va="bottom", rotation=90, rotation_mode="anchor",
    fontproperties=ARIAL,
    fontsize=FONT_SIZE_DETAIL, color=SLATE,
)
provider_order = tuple(sorted(
    PROVIDER_COLORS, key=lambda family: PROVIDER_LABELS[family], reverse=True
))
provider_handles = [
    Patch(facecolor=PROVIDER_COLORS[family], edgecolor="none", alpha=0.18,
          label=PROVIDER_LABELS[family])
    for family in provider_order
]
provider_font = ARIAL.copy()
provider_font.set_size(FONT_SIZE_DETAIL)
provider_legend = ax.legend(
    handles=provider_handles, title="Model Provider", loc="lower right",
    bbox_to_anchor=(0.992, 0.012), ncol=2, frameon=False,
    handlelength=1.05, handleheight=0.72, handletextpad=0.35,
    columnspacing=0.75, borderaxespad=0.0, prop=provider_font,
)
provider_legend.get_title().set_fontproperties(ARIAL_BOLD)
provider_legend.get_title().set_fontsize(FONT_SIZE_LABEL)
ax.add_artist(provider_legend)

loading_handles = [
    FancyArrowPatch(
        (0, 0), (1, 0), arrowstyle="-|>", mutation_scale=6,
        linewidth=0.9, color=LAYER_COLORS[layer], label=label,
    )
    for layer, label in (
        ("L1", "Fundamentals"),
        ("L2", "Applied Reasoning"),
        ("L3", "Engineering Design"),
    )
]
loading_legend = ax.legend(
    handles=loading_handles, title="Loading Vector", loc="lower left",
    bbox_to_anchor=(0.012, 0.012), frameon=False, ncol=1,
    handlelength=1.35, handletextpad=0.45, labelspacing=0.25,
    borderaxespad=0.0, prop=provider_font,
    handler_map={FancyArrowPatch: HandlerArrow()},
)
loading_legend.get_title().set_fontproperties(ARIAL_BOLD)
loading_legend.get_title().set_fontsize(FONT_SIZE_LABEL)

key_ax.text(0.02, 0.988, "Model", ha="left", va="top",
            fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_LABEL, color=INK)
key_y = np.linspace(0.950, 0.025, len(models))
for number, model, y in zip(range(1, len(models) + 1), models, key_y):
    color = PROVIDER_COLORS[MODEL_META[model].family]
    key_ax.scatter([0.055], [y], s=POINT_AREA, facecolor=color,
                   edgecolor="white", linewidth=0.45)
    key_ax.annotate(str(number), xy=(0.055, y), xytext=(0, -0.45),
                    textcoords="offset points", ha="center", va="center",
                    fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_DETAIL,
                    color="white")
    key_ax.text(0.125, y, display_name(model), ha="left", va="center",
                fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL, color=INK)
key_ax.set_xlim(0, 1)
key_ax.set_ylim(0, 1)

output = [{"record_type": "model", "name": model, "label": display_name(model),
           "family": MODEL_META[model].family, "pc1": f"{coordinates[i,0]:.8f}",
           "pc2": f"{coordinates[i,1]:.8f}", "explained_variance": ""}
          for i, model in enumerate(models)]
output.extend({"record_type": "loading", "name": task, "label": TYPE_LABELS[task],
               "family": "", "pc1": f"{loadings[i,0]:.8f}",
               "pc2": f"{loadings[i,1]:.8f}", "explained_variance": ""}
              for i, task in enumerate(TASK_TYPES))
write_rows(OUTPUT_DIR / "model_capability_space.csv",
           ["record_type", "name", "label", "family", "pc1", "pc2", "explained_variance"], output)
export_figure(fig, OUTPUT_DIR, "model_capability_space")
plt.close(fig)
print(f"Models: {len(models)}; capability dimensions: {len(TASK_TYPES)}")
print(f"PC1+PC2 explained variance: {100*(explained[0]+explained[1]):.1f}%")
print(f"Canvas: {WIDTH_MM} x {HEIGHT_MM} mm")
