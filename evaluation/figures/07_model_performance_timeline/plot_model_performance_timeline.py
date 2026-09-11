"""Plot model release date against the measured TENGBench score."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import csv
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
import numpy as np

# CairoSVG is used only after the vector artwork has been assembled.  Homebrew
# supplies Cairo on macOS; setting the fallback before importing keeps the
# TENGBench environment self-contained without rasterising any source logo.
os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
import cairosvg  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE_DARK, BLUE_LIGHT, CORAL, GRID, INK, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from result_utils import MODEL_META, read_csv  # noqa: E402


OUTPUT_DIR = Path(__file__).parent
ASSET_DIR = OUTPUT_DIR / "asset"
FIGURE_WIDTH_MM = 175
FIGURE_HEIGHT_MM = 202.6
DPI = 500
LOGO_MAX_SIDE_PT = 15.0
LABEL_GAP_PT = 2.4
LOESS_FRACTION = 0.60
BOOTSTRAP_REPLICATES = 800
DISPLAY_ERROR_CAP = 0.012
SOTA_RING_DIAMETER_PT = 20.5
SOTA_RED = CORAL
SOTA_DATE_FONT_SIZE = FONT_SIZE_DETAIL + 0.5
SOTA_LINE_WIDTH = 0.82
SOTA_LINE_STYLE = (0, (4.0, 2.6))

# Variant families contribute only their flagship configuration to the trend.
# All model marks remain visible; these exclusions affect the LOESS fit only.
NON_FLAGSHIP_MODELS = {
    "claude-sonnet-4-6",   # Opus 4.6 is the flagship of this generation.
    "deepseek-v4-flash",  # V4 Pro is the flagship V4 configuration.
    "gpt-5.6-luna",       # GPT-5.6 Sol is the flagship 5.6 configuration.
    "gpt-5.6-terra",
    "qwen3.7-flash",      # Max is the flagship within each Qwen generation.
    "qwen3.7-plus",
    "qwen3.8-flash",
}

# Only genuinely coincident logo-label pairs receive a small vertical nudge.
# The logo and its model name always move together and remain on one line.
PAIR_Y_OFFSETS = {
    "claude-sonnet-5": 13,
    "kimi-k3": -13,
    "gpt-5.5": 10,
    "claude-opus-4-7": -10,
    "deepseek-v4-pro-0813": 18,
    "gpt-5.6-terra": -20,
    "kimi-k2.7-code": 9,
    "gpt-5.6-luna": -10,
    "qwen3.7-max": -7,
}

# Date labels sit away from the model names and from neighbouring records.
SOTA_DATE_OFFSETS = {
    "deepseek-v3.1": (0.0, 13.0, "center", "bottom"),
    "deepseek-v3.2": (0.0, -13.0, "center", "top"),
    "claude-opus-4.6": (0.0, 13.0, "center", "bottom"),
    "claude-opus-4-7": (-13.0, 7.0, "right", "bottom"),
    "gpt-5.5": (-13.0, 7.0, "right", "bottom"),
}


def svg_geometry(family: str) -> tuple[Path, float, float]:
    """Return an SVG source and its display size, preserving aspect ratio."""
    svg_path = ASSET_DIR / f"{family}.svg"
    if not svg_path.exists():
        raise FileNotFoundError(f"Missing vector logo: {svg_path}")
    root = ET.parse(svg_path).getroot()
    view_box = root.get("viewBox")
    if view_box:
        _, _, source_width, source_height = map(float, view_box.replace(",", " ").split())
    else:
        source_width = float(re.sub(r"[^0-9.+-]", "", root.get("width", "1")))
        source_height = float(re.sub(r"[^0-9.+-]", "", root.get("height", "1")))
        root.set("viewBox", f"0 0 {source_width} {source_height}")
    scale = LOGO_MAX_SIDE_PT / max(source_width, source_height)
    return svg_path, source_width * scale, source_height * scale


def prefix_svg_identifiers(root: ET.Element, prefix: str) -> None:
    """Namespace IDs and CSS classes so repeated inline SVGs never collide."""
    identifiers = {
        element.get("id"): f"{prefix}{element.get('id')}"
        for element in root.iter() if element.get("id")
    }
    classes = {
        class_name
        for element in root.iter()
        for class_name in element.get("class", "").split()
    }
    for element in root.iter():
        if element.get("id") in identifiers:
            element.set("id", identifiers[element.get("id")])
        if element.get("class"):
            element.set(
                "class", " ".join(f"{prefix}{name}" for name in element.get("class", "").split())
            )
        for key, value in list(element.attrib.items()):
            for old, new in identifiers.items():
                value = value.replace(f"url(#{old})", f"url(#{new})")
                if value == f"#{old}":
                    value = f"#{new}"
            element.set(key, value)
        if element.tag.endswith("style") and element.text:
            for class_name in classes:
                element.text = element.text.replace(
                    f".{class_name}", f".{prefix}{class_name}"
                )


def inline_svg_logos(base_svg: Path, output_svg: Path, placements: list[dict]) -> None:
    """Insert every source SVG as a native nested SVG in the chart artwork."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(base_svg)
    chart_root = tree.getroot()
    for index, placement in enumerate(placements):
        logo_root = deepcopy(ET.parse(placement["path"]).getroot())
        if not logo_root.get("viewBox"):
            source_width = float(
                re.sub(r"[^0-9.+-]", "", logo_root.get("width", "1"))
            )
            source_height = float(
                re.sub(r"[^0-9.+-]", "", logo_root.get("height", "1"))
            )
            logo_root.set("viewBox", f"0 0 {source_width} {source_height}")
        prefix_svg_identifiers(logo_root, f"logo_{index}_")
        logo_root.attrib.pop("class", None)
        logo_root.set("x", f"{placement['x'] - placement['width'] / 2:.5f}")
        logo_root.set("y", f"{placement['y'] - placement['height'] / 2:.5f}")
        logo_root.set("width", f"{placement['width']:.5f}")
        logo_root.set("height", f"{placement['height']:.5f}")
        logo_root.set("preserveAspectRatio", "xMidYMid meet")
        chart_root.append(logo_root)
    tree.write(output_svg, encoding="utf-8", xml_declaration=True)


def loess_predict(
    x: np.ndarray,
    y: np.ndarray,
    evaluation_x: np.ndarray,
    fraction: float = LOESS_FRACTION,
    robust_iterations: int = 2,
) -> np.ndarray:
    """Robust local-linear LOESS with tricube distance weighting."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    evaluation_x = np.asarray(evaluation_x, dtype=float)
    neighbourhood = max(3, min(len(x), int(np.ceil(fraction * len(x)))))
    robust_weights = np.ones(len(x), dtype=float)

    def local_fit(targets: np.ndarray, residual_weights: np.ndarray) -> np.ndarray:
        predictions = np.empty(len(targets), dtype=float)
        for index, target in enumerate(targets):
            distances = np.abs(x - target)
            bandwidth = np.partition(distances, neighbourhood - 1)[neighbourhood - 1]
            if bandwidth <= np.finfo(float).eps:
                positive = distances[distances > np.finfo(float).eps]
                bandwidth = positive.min() if len(positive) else 1.0
            scaled = np.clip(distances / bandwidth, 0.0, 1.0)
            weights = (1.0 - scaled**3) ** 3 * residual_weights
            design = np.column_stack((np.ones(len(x)), x - target))
            weighted_design = design * np.sqrt(weights)[:, None]
            weighted_y = y * np.sqrt(weights)
            if np.count_nonzero(weights) < 2:
                predictions[index] = np.average(y, weights=np.maximum(weights, 1e-12))
            else:
                coefficients, *_ = np.linalg.lstsq(weighted_design, weighted_y, rcond=None)
                predictions[index] = coefficients[0]
        return predictions

    for _ in range(robust_iterations):
        fitted_observations = local_fit(x, robust_weights)
        residuals = y - fitted_observations
        median_absolute_residual = float(np.median(np.abs(residuals)))
        if median_absolute_residual <= np.finfo(float).eps:
            break
        scaled_residuals = residuals / (6.0 * median_absolute_residual)
        robust_weights = np.where(
            np.abs(scaled_residuals) < 1.0,
            (1.0 - scaled_residuals**2) ** 2,
            0.0,
        )
    return local_fit(evaluation_x, robust_weights)


def bootstrap_loess_standard_error(
    x: np.ndarray,
    y: np.ndarray,
    evaluation_x: np.ndarray,
) -> np.ndarray:
    """Return deterministic pointwise paired-bootstrap standard errors."""
    rng = np.random.default_rng(20260905)
    curves = np.empty((BOOTSTRAP_REPLICATES, len(evaluation_x)), dtype=float)
    for replicate in range(BOOTSTRAP_REPLICATES):
        indices = rng.integers(0, len(x), size=len(x))
        curves[replicate] = loess_predict(
            x[indices], y[indices], evaluation_x, robust_iterations=1,
        )
    return np.std(curves, axis=0, ddof=1)


rows = read_csv("model_summary.csv")
if {row["model"] for row in rows} != set(MODEL_META):
    raise RuntimeError("Real-result summary and model metadata do not match")
rows.sort(key=lambda row: (date.fromisoformat(row["release_date"]), row["display_name"]))
logos = {family: svg_geometry(family) for family in {row["family"] for row in rows}}

# A SOTA event is the best model released on a date whose score exceeds the
# record established on all earlier dates. This avoids inventing an ordering
# among models released on the same day.
sota_rows: list[dict[str, str]] = []
running_best = -np.inf
for release_date in sorted({row["release_date"] for row in rows}):
    daily_rows = [row for row in rows if row["release_date"] == release_date]
    daily_best = max(daily_rows, key=lambda row: float(row["overall_score"]))
    daily_score = float(daily_best["overall_score"])
    if daily_score > running_best:
        sota_rows.append(daily_best)
        running_best = daily_score
sota_models = {row["model"] for row in sota_rows}

fig, ax = plt.subplots(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)

release_dates = [date.fromisoformat(row["release_date"]) for row in rows]
scores = [float(row["overall_score"]) for row in rows]
ax.set_xlim(min(release_dates) - timedelta(days=28), max(release_dates) + timedelta(days=73))
# The taller canvas and tighter data limits create physical separation without
# moving labels away from their measured points.
y_min, y_max = 0.38, 0.77
ax.set_ylim(y_min, y_max)

# Robust LOESS describes the flagship-model trajectory without allowing
# lighter siblings from the same generation to pull that trajectory downward.
# A paired-bootstrap band reports uncertainty in the fitted mean trajectory.
flagship_rows = [row for row in rows if row["model"] not in NON_FLAGSHIP_MODELS]
fit_release_numbers = np.asarray(
    mdates.date2num([date.fromisoformat(row["release_date"]) for row in flagship_rows]),
    dtype=float,
)
fit_score_values = np.asarray(
    [float(row["overall_score"]) for row in flagship_rows], dtype=float,
)
# Extend the descriptive curve and its uncertainty band to the exact plotting
# limits so the visual trend spans the complete time axis.  The outer portions
# are boundary extrapolations from the same flagship-only local fits.
x_axis_left, x_axis_right = ax.get_xlim()
fit_x = np.linspace(x_axis_left, x_axis_right, 400)
fit_y = loess_predict(fit_release_numbers, fit_score_values, fit_x)
fit_standard_error = bootstrap_loess_standard_error(
    fit_release_numbers, fit_score_values, fit_x,
)
# The bootstrap error expands sharply at the sparsely sampled/extrapolated
# boundaries.  Cap the displayed half-width to keep the uncertainty encoding
# subordinate to the model data while retaining its local variation.
display_error = np.minimum(fit_standard_error, DISPLAY_ERROR_CAP)
ax.plot(
    mdates.num2date(fit_x), fit_y,
    color=BLUE_DARK, linewidth=0.82, linestyle=(0, (4.0, 2.6)),
    alpha=0.96, zorder=1, label="Mean Flagship Score",
)
ax.fill_between(
    mdates.num2date(fit_x), fit_y - display_error, fit_y + display_error,
    color=BLUE_LIGHT, alpha=0.18, edgecolor="none", linewidth=0.0,
    zorder=0.7, label="Error in Mean Flagship Score",
)

logo_placements = []
for row in rows:
    when = date.fromisoformat(row["release_date"])
    score = float(row["overall_score"])
    x = float(mdates.date2num(when))
    dy = PAIR_Y_OFFSETS.get(row["model"], 0)
    _, logo_width_pt, logo_height_pt = logos[row["family"]]
    mark_half_width = (
        SOTA_RING_DIAMETER_PT / 2
        if row["model"] in sota_models
        else logo_width_pt / 2
    )
    dx = mark_half_width + LABEL_GAP_PT
    ax.annotate(
        row["display_name"], xy=(x, score), xytext=(dx, dy),
        textcoords="offset points", ha="left", va="center",
        fontsize=FONT_SIZE_LABEL, fontproperties=ARIAL_BOLD, color=INK, zorder=6,
    )
    logo_placements.append((row, x, score, dy, logo_width_pt, logo_height_pt))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
y_ticks = [0.40 + 0.05 * i for i in range(8)]
ax.set_yticks(y_ticks)
ax.set_yticklabels([f"{value:.2f}" for value in y_ticks])
ax.tick_params(axis="both", length=2.5, width=0.6, color=SLATE, pad=3)
for label in ax.get_xticklabels() + ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
ax.set_xlabel("Model Release Date", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK, labelpad=6)
ax.set_ylabel("Overall Score", fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_KEY, color=INK, labelpad=7)
ax.grid(axis="y", color=GRID, linewidth=0.48, alpha=0.9, zorder=0)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(SLATE)
    ax.spines[side].set_linewidth(0.65)
ax.plot([1, 1], [0, 0.012], transform=ax.transAxes, color=SLATE, linewidth=0.65, clip_on=False)
# Terminal cap at the top of the y-axis, matching the x-axis end cap.
ax.plot([0, 0.012], [1, 1], transform=ax.transAxes, color=SLATE, linewidth=0.65, clip_on=False)

fig.subplots_adjust(left=0.096, right=0.997, bottom=0.064, top=0.995)
fig.canvas.draw()

# Translate each point's collision-avoidance offset from display points back
# into data coordinates. The SOTA path and rings then align exactly with the
# centres of the shifted SVG logos.
sota_centres: list[tuple[dict[str, str], float, float]] = []
for row, x, score, dy, _, _ in logo_placements:
    if row["model"] not in sota_models:
        continue
    display_x, display_y = ax.transData.transform((x, score))
    display_y += dy * fig.dpi / 72.0
    adjusted_x, adjusted_y = ax.transData.inverted().transform((display_x, display_y))
    sota_centres.append((row, float(adjusted_x), float(adjusted_y)))
sota_centres.sort(key=lambda item: date.fromisoformat(item[0]["release_date"]))

# Draw each SOTA segment from circle edge to circle edge. Trimming is done in
# display coordinates so the gap remains exact despite unequal date/score
# scales and the intentionally tall manuscript canvas.
ring_radius_px = SOTA_RING_DIAMETER_PT / 2.0 * fig.dpi / 72.0
for (_, x_start, y_start), (_, x_end, y_end) in zip(
    sota_centres[:-1], sota_centres[1:]
):
    start_display = np.asarray(ax.transData.transform((x_start, y_start)))
    end_display = np.asarray(ax.transData.transform((x_end, y_end)))
    direction = end_display - start_display
    distance = float(np.linalg.norm(direction))
    if distance <= 2.0 * ring_radius_px:
        continue
    unit = direction / distance
    trimmed_start = ax.transData.inverted().transform(
        start_display + ring_radius_px * unit
    )
    trimmed_end = ax.transData.inverted().transform(
        end_display - ring_radius_px * unit
    )
    ax.plot(
        [trimmed_start[0], trimmed_end[0]],
        [trimmed_start[1], trimmed_end[1]],
        color=SOTA_RED, linewidth=SOTA_LINE_WIDTH,
        linestyle=SOTA_LINE_STYLE, alpha=0.96, zorder=3.5,
    )
ax.scatter(
    [mdates.num2date(x) for _, x, _ in sota_centres],
    [y for _, _, y in sota_centres],
    s=SOTA_RING_DIAMETER_PT**2, facecolors="none", edgecolors=SOTA_RED,
    linewidths=1.0, zorder=5,
)
for row, x, y in sota_centres:
    when = date.fromisoformat(row["release_date"])
    dx, dy, ha, va = SOTA_DATE_OFFSETS.get(
        row["model"], (-13.0, 0.0, "right", "center")
    )
    ax.annotate(
        f"{when.strftime('%b')}. {when.day}\n{when.year}",
        xy=(x, y), xytext=(dx, dy), textcoords="offset points",
        ha=ha, va=va, fontproperties=ARIAL, fontsize=SOTA_DATE_FONT_SIZE,
        color=SOTA_RED, linespacing=0.88, zorder=6,
    )

legend_handles, legend_labels = ax.get_legend_handles_labels()
legend_handles.append(Line2D(
    [0], [0], color=SOTA_RED, linewidth=SOTA_LINE_WIDTH,
    linestyle=SOTA_LINE_STYLE, label="New SOTA",
))
legend_labels.append("New SOTA")
legend = ax.legend(
    handles=legend_handles, labels=legend_labels,
    loc="lower right", bbox_to_anchor=(0.988, 0.015), frameon=False,
    prop=ARIAL, fontsize=FONT_SIZE_DETAIL, handlelength=2.0,
    handletextpad=0.5, labelspacing=0.35, borderaxespad=0.0,
)
for label in legend.get_texts():
    label.set_color(INK)

fig.canvas.draw()
renderer = fig.canvas.get_renderer()
tight_bbox = fig.get_tightbbox(renderer)
tight_bbox = Bbox.from_extents(
    tight_bbox.x0 - 2.0 / 25.4, tight_bbox.y0,
    tight_bbox.x1, tight_bbox.y1,
)
figure_width_pt = fig.get_figwidth() * 72.0
figure_height_pt = fig.get_figheight() * 72.0
left_crop_pt = tight_bbox.x0 * 72.0
top_crop_pt = (fig.get_figheight() - tight_bbox.y1) * 72.0
vector_placements: list[dict] = []
for row, x, score, dy, logo_width_pt, logo_height_pt in logo_placements:
    display_x, display_y = ax.transData.transform((x, score))
    x_pt = display_x * 72.0 / fig.dpi - left_crop_pt
    y_pt = figure_height_pt - display_y * 72.0 / fig.dpi - dy - top_crop_pt
    vector_placements.append({
        "path": logos[row["family"]][0],
        "x": x_pt,
        "y": y_pt,
        "width": logo_width_pt,
        "height": logo_height_pt,
    })

base_svg = OUTPUT_DIR / "_model_performance_timeline_base.svg"
output_svg = OUTPUT_DIR / "model_performance_timeline.svg"
output_png = OUTPUT_DIR / "model_performance_timeline.png"
output_pdf = OUTPUT_DIR / "model_performance_timeline.pdf"
fig.savefig(
    base_svg, format="svg", facecolor="white",
    bbox_inches=tight_bbox, pad_inches=0,
)
plt.close(fig)
inline_svg_logos(base_svg, output_svg, vector_placements)
base_svg.unlink()
cairosvg.svg2png(
    url=str(output_svg), write_to=str(output_png),
    output_width=round(tight_bbox.width * DPI),
    output_height=round(tight_bbox.height * DPI),
    background_color="white",
)
cairosvg.svg2pdf(
    url=str(output_svg), write_to=str(output_pdf),
)

with (OUTPUT_DIR / "model_scores.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Models: {len(rows)}; source configurations: {sum(int(row['configuration_count']) for row in rows)} (GPT xhigh only)")
print(
    f"Canvas: {tight_bbox.width * 25.4:.1f} x "
    f"{tight_bbox.height * 25.4:.1f} mm at {DPI} dpi (tight export)"
)
print("Scores: aggregated directly from code/result")
observed_fit = loess_predict(
    fit_release_numbers, fit_score_values, fit_release_numbers,
)
fit_rmse = float(np.sqrt(np.mean((fit_score_values - observed_fit) ** 2)))
print(
    f"Flagship LOESS: n={len(flagship_rows)}; fraction={LOESS_FRACTION:.2f}; "
    f"bootstrap={BOOTSTRAP_REPLICATES}; in-sample RMSE={fit_rmse:.3f}; "
    f"displayed error capped at +/-{DISPLAY_ERROR_CAP:.3f}"
)
