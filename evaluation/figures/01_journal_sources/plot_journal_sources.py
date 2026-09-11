"""Plot journal coverage as a polar year-bubble and total-count wave chart."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple
from matplotlib.patches import Patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, BLUE_DARK, BLUE_LIGHT, CORAL, GRID, INK,
    ORANGE, PALE_GREY, PURPLE, SLATE, TEAL, FONT_SIZE_DETAIL, FONT_SIZE_LABEL,
    FONT_SIZE_KEY, plt,
)

OUTPUT_DIR = Path(__file__).parent
CODE_ROOT = Path(__file__).resolve().parents[3]
PAPER_ROOT = CODE_ROOT / "papers" / "qualified"
FIGURE_WIDTH_MM = 110
FIGURE_HEIGHT_MM = 110
LEGEND_WIDTH_MM = 140
LEGEND_HEIGHT_MM = 38
DPI = 500

# ISO 4 abbreviations assembled word by word from the ISSN International
# Centre's LTWA.  Conjunctions, articles, and prepositions are omitted in
# accordance with abbreviated-title construction; acronyms, coined titles,
# and unabbreviated LTWA entries retain their registered form.
# Source: https://portal.issn.org/ltwa (verified 2026-09-11).
ABBREVIATIONS = {
    "ACS Applied Materials & Interfaces": "ACS Appl. Mater. Interfaces",
    "ACS Energy Letters": "ACS Energy Lett.",
    "ACS Nano": "ACS Nano",
    "ACS Sensors": "ACS Sens.",
    "Advanced Energy Materials": "Adv. Energy Mater.",
    "Advanced Functional Materials": "Adv. Funct. Mater.",
    "Advanced Materials": "Adv. Mater.",
    "Advanced Materials Technologies": "Adv. Mater. Technol.",
    "Advanced Science": "Adv. Sci.",
    "Biosensors and Bioelectronics": "Biosens. Bioelectron.",
    "Chemical Reviews": "Chem. Rev.",
    "EcoMat": "EcoMat",
    "Energy Storage Materials": "Energy Storage Mater.",
    "eScience": "eScience",
    "InfoMat": "InfoMat",
    "Interdisciplinary Materials": "Interdiscip. Mater.",
    "iScience": "iScience",
    "Journal of the American Chemical Society": "J. Am. Chem. Soc.",
    "Joule": "Joule",
    "Materials Today": "Mater. Today",
    "MRS Bulletin": "MRS Bull.",
    "Nano Energy": "Nano Energy",
    "Nano Letters": "Nano Lett.",
    "Nano Research": "Nano Res.",
    "Nano Today": "Nano Today",
    "Nature": "Nature",
    "Nature Communications": "Nat. Commun.",
    "Nature Sensors": "Nat. Sens.",
    "npj Flexible Electronics": "npj Flex. Electron.",
    "Science Advances": "Sci. Adv.",
    "Science Bulletin": "Sci. Bull.",
    "Small": "Small",
    "Small Methods": "Small Methods",
}


def periodic_catmull_rom(values: np.ndarray, samples_per_segment: int = 18) -> tuple[np.ndarray, np.ndarray]:
    """Return a smooth periodic curve through values at equal angular steps."""
    count = len(values)
    theta_parts: list[np.ndarray] = []
    radius_parts: list[np.ndarray] = []
    for index in range(count):
        p0 = values[(index - 1) % count]
        p1 = values[index]
        p2 = values[(index + 1) % count]
        p3 = values[(index + 2) % count]
        t = np.linspace(0.0, 1.0, samples_per_segment, endpoint=False)
        radius = 0.5 * (
            2.0 * p1
            + (-p0 + p2) * t
            + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t**2
            + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t**3
        )
        theta_parts.append((index + t) * 2.0 * np.pi / count)
        radius_parts.append(radius)
    theta = np.concatenate(theta_parts)
    radius = np.concatenate(radius_parts)
    return np.append(theta, 2.0 * np.pi), np.append(radius, radius[0])


papers: list[dict] = []
for path in sorted(PAPER_ROOT.glob("**/index.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record["venue"] == "Unpublished manuscript":
        record["venue"] = "Nature"
    raw_year = int(record["date"][:4])
    record["plot_year"] = 2024 if raw_year <= 2021 else raw_year
    papers.append(record)

totals = Counter(paper["venue"] for paper in papers)
year_counts = Counter((paper["venue"], paper["plot_year"]) for paper in papers)
years = list(range(min(paper["plot_year"] for paper in papers), max(paper["plot_year"] for paper in papers) + 1))
missing_abbreviations = sorted(set(totals) - set(ABBREVIATIONS))
if missing_abbreviations:
    raise RuntimeError(
        "Missing LTWA journal abbreviations: " + ", ".join(missing_abbreviations)
    )

# Keep the most represented journal at 0 degrees (right), then use a seeded,
# stratified random order. Low-count journals are assigned to gaps between
# larger sources so the arrangement stays dispersed without becoming a rigid
# high-low sequence.
ranked_venues = sorted(totals, key=lambda venue: (-totals[venue], venue))
largest_venue = ranked_venues[0]
rng = np.random.default_rng(31)
larger_venues = [venue for venue in ranked_venues if totals[venue] > 4]
low_venues = [venue for venue in ranked_venues if totals[venue] <= 4]
larger_tail = larger_venues[1:]
rng.shuffle(larger_tail)
rng.shuffle(low_venues)
larger_venues = [largest_venue, *larger_tail]

low_buckets: list[list[str]] = [[] for _ in larger_venues]
for index, venue in enumerate(low_venues[:len(larger_venues)]):
    low_buckets[index].append(venue)
extra_low = low_venues[len(larger_venues):]
for position, venue in zip((3, 8, 13), extra_low):
    low_buckets[position].append(venue)

venues: list[str] = []
for venue, bucket in zip(larger_venues, low_buckets):
    venues.append(venue)
    venues.extend(bucket)

n_venues = len(venues)
# Reserve the exact 180-degree gap for the radial count scale. The two
# least-represented journals flank that gap, so their year bubbles leave the
# scale naturally open while Nano Energy remains fixed at 0 degrees.
left_flank_positions = (n_venues // 2, n_venues // 2 + 1)
# Short, low-count labels keep the count scale legible at the left cardinal
# axis. Longer LTWA forms are placed on diagonals below so no standard word or
# terminal period is clipped by the fixed 110-mm square canvas.
left_flank_venues = ["ACS Energy Letters", "eScience"]
for position, venue in zip(left_flank_positions, left_flank_venues):
    current_position = venues.index(venue)
    venues[position], venues[current_position] = venues[current_position], venues[position]

for venue, position in (
    ("ACS Applied Materials & Interfaces", 4),
    ("Biosensors and Bioelectronics", 19),
    ("Energy Storage Materials", 29),
):
    current_position = venues.index(venue)
    venues[position], venues[current_position] = venues[current_position], venues[position]

theta_nodes = np.arange(n_venues) * 2.0 * np.pi / n_venues
total_values = np.asarray([totals[venue] for venue in venues], dtype=float)
maximum_total = float(total_values.max())

wave_base = 30.0
center_radius = 23.5
outer_ring = 100.0
frame_radius = 107.0
label_radius = 109.0


def count_radius(values: np.ndarray) -> np.ndarray:
    """Strongly expand 0-10 and 10-20 counts on a piecewise radial scale."""
    values = np.clip(np.asarray(values, dtype=float), 0.0, 100.0)
    radii = np.empty_like(values)

    low = values <= 10.0
    middle = (values > 10.0) & (values <= 20.0)
    high = values > 20.0

    radii[low] = wave_base + 28.0 * (values[low] / 10.0) ** 0.42
    radii[middle] = 58.0 + 15.0 * ((values[middle] - 10.0) / 10.0) ** 0.72
    radii[high] = 73.0 + 27.0 * ((values[high] - 20.0) / 80.0) ** 0.78
    return radii


wave_radius = count_radius(total_values)
theta_wave, smooth_wave = periodic_catmull_rom(wave_radius)
smooth_wave = np.clip(smooth_wave, wave_base, outer_ring)

year_colors = {
    year: color for year, color in zip(years, (BLUE, TEAL, CORAL, PURPLE, ORANGE))
}
year_radii = {
    year: radius for year, radius in zip(years, np.linspace(44.0, 88.0, len(years)))
}
JOURNAL_LABEL_SIZE = 6.6
WAVE_LINE_COLOR = "#8EA6D1"


def bubble_area(value: int) -> float:
    # Scatter size is an area in points squared, so it directly represents
    # annual paper count rather than bubble diameter.
    # Keep the complete annual encoding but reduce every bubble area by 20%
    # for cleaner separation at manuscript scale.
    return 7.2 if value == 0 else 18.4 + 20.8 * np.sqrt(value)


fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4), facecolor="white"
)
ax = fig.add_axes([0.140, 0.190, 0.720, 0.620], projection="polar")
ax.set_theta_zero_location("E")
ax.set_theta_direction(1)
ax.set_ylim(0.0, frame_radius)
ax.set_xticks([])
ax.set_yticks([])
ax.grid(False)
ax.spines["polar"].set_color(SLATE)
ax.spines["polar"].set_linewidth(0.70)

dense_theta = np.linspace(0.0, 2.0 * np.pi, 900)

# Journal spokes establish the angular positions. The 0-degree spoke is
# omitted because it reads as an unintended horizontal rule beside Nano Energy.
for index, theta in enumerate(theta_nodes):
    if index == 0:
        continue
    ax.plot([theta, theta], [wave_base, outer_ring], color=GRID, linewidth=0.42, zorder=0)
# The odd number of journals creates an exact inter-journal gap at 180
# degrees, allowing a clean cardinal count axis with no bubble stack on it.
tick_axis_theta = np.pi
ax.plot([tick_axis_theta, tick_axis_theta], [wave_base, outer_ring],
        color=SLATE, linewidth=0.62, zorder=1)
for tick_index, tick in enumerate((0, 5, 10, 15, 20, 30, 40, 60, 80, 100)):
    radius = float(count_radius(np.asarray([tick]))[0])
    ax.plot(
        [tick_axis_theta - 0.012, tick_axis_theta + 0.012],
        [radius, radius], color=SLATE, linewidth=0.60, zorder=2,
    )
    label_side = 1.0 if tick_index % 2 == 0 else -1.0
    # The 15-paper radius coincides with the sole upper-flank year bubble;
    # place this one label below the axis while retaining the alternating key.
    if tick == 15:
        label_side = 1.0
    ax.text(
        tick_axis_theta + label_side * 0.030, radius, str(tick),
        ha="center", va="top" if label_side > 0 else "bottom",
        fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL, color=SLATE,
        zorder=7,
    )

# The total-count area supplies a visible background. Years use five fixed
# radii, but the bubbles are intentionally not joined by lines.
ax.fill_between(
    theta_wave, center_radius, smooth_wave,
    color=BLUE_LIGHT, edgecolor="none", linewidth=0.0,
    antialiased=False, alpha=0.30, zorder=1,
)
# Some polar backends expose the closed polygon's 0-degree raster seam even
# with no edge. Cover it with the exact white-background blend of the fill.
ax.plot(
    [0.0, 0.0], [center_radius, wave_radius[0]],
    color="#E7ECF6", linewidth=1.4, solid_capstyle="butt", zorder=1.1,
)
for year in years:
    counts = np.asarray([year_counts[(venue, year)] for venue in venues], dtype=float)
    radius = year_radii[year]
    absent = counts == 0
    ax.scatter(
        theta_nodes[absent], np.full(absent.sum(), radius),
        s=bubble_area(0), facecolor="white", edgecolor=year_colors[year],
        linewidth=0.46, alpha=0.42, zorder=2,
    )
    present = counts > 0
    ax.scatter(
        theta_nodes[present], np.full(present.sum(), radius),
        s=[bubble_area(int(value)) for value in counts[present]],
        color=year_colors[year], edgecolor="white", linewidth=0.72,
        alpha=0.94, zorder=3,
    )

# The total wave is a clean, pale boundary over the unchanged filled area.
ax.plot(theta_wave, smooth_wave, color=WAVE_LINE_COLOR, linewidth=0.90, zorder=5)

# Radially oriented journal names form the outermost label ring. Standard
# abbreviations preserve journal identity while remaining manuscript-safe.
for theta, venue in zip(theta_nodes, venues):
    angle = np.degrees(theta)
    if 90 < angle < 270:
        rotation = angle + 180
        horizontal_alignment = "right"
    else:
        rotation = angle
        horizontal_alignment = "left"
    ax.text(
        theta, label_radius, ABBREVIATIONS[venue],
        rotation=rotation, rotation_mode="anchor",
        ha=horizontal_alignment, va="center",
        fontproperties=ARIAL, fontsize=JOURNAL_LABEL_SIZE, color=INK,
        clip_on=False, zorder=7,
    )

# A compact white centre gives the compound plot a clear reading anchor.
ax.fill_between(dense_theta, 0.0, center_radius, color="white", zorder=7)
ax.plot(dense_theta, np.full_like(dense_theta, center_radius), color=INK,
        linewidth=0.62, zorder=8)
ax.text(0.5, 0.507, "Journals", transform=ax.transAxes,
        ha="center", va="bottom", fontproperties=ARIAL_BOLD,
        fontsize=8.0, color=INK, zorder=9)
ax.text(0.5, 0.493, f"{len(papers):,} papers", transform=ax.transAxes,
        ha="center", va="top", fontproperties=ARIAL,
        fontsize=FONT_SIZE_LABEL, color=INK, zorder=9)

# Scientific keys for the two quantitative encodings. They are exported as a
# separate artwork file so the main polar panel remains publication-ready.
bubble_levels = (0, 1, 10, 30)
bubble_handles = [
    Line2D(
        [], [], linestyle="none", marker="o",
        markerfacecolor="white", markeredgecolor=SLATE,
        markeredgewidth=0.70, markersize=np.sqrt(bubble_area(level)),
        label=str(level),
    )
    for level in bubble_levels
]
wave_handle = (
    Patch(facecolor=BLUE_LIGHT, edgecolor="none", alpha=0.30),
    Line2D([0], [0], color=WAVE_LINE_COLOR, linewidth=0.90),
)
year_handles = [
    Line2D(
        [0], [0], linestyle="none", color=year_colors[year],
        marker="o", markersize=4.0, label=str(year),
    )
    for year in years
]

fig.savefig(OUTPUT_DIR / "journal_sources_rose.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "journal_sources_rose.png", dpi=DPI, facecolor="white")
plt.close(fig)

legend_fig = plt.figure(
    figsize=(LEGEND_WIDTH_MM / 25.4, LEGEND_HEIGHT_MM / 25.4),
    facecolor="white",
)
legend_ax = legend_fig.add_axes([0.0, 0.0, 1.0, 1.0])
legend_ax.axis("off")

bubble_legend = legend_fig.legend(
    handles=bubble_handles, title="Papers per Year", loc="center left",
    bbox_to_anchor=(0.015, 0.50), frameon=False, ncol=4,
    prop=ARIAL, title_fontproperties=ARIAL_BOLD,
    handletextpad=0.30, columnspacing=0.58, borderaxespad=0.0,
)
bubble_legend.get_title().set_fontsize(FONT_SIZE_LABEL)
for label in bubble_legend.get_texts():
    label.set_fontsize(JOURNAL_LABEL_SIZE)

year_legend = legend_fig.legend(
    handles=year_handles, loc="center", bbox_to_anchor=(0.555, 0.50),
    title="Year", title_fontproperties=ARIAL_BOLD,
    frameon=False, ncol=1, prop=ARIAL,
    handlelength=1.0, handletextpad=0.30, labelspacing=0.24,
    borderaxespad=0.0,
)
year_legend.get_title().set_fontsize(FONT_SIZE_LABEL)
for label in year_legend.get_texts():
    label.set_fontsize(JOURNAL_LABEL_SIZE)

total_legend = legend_fig.legend(
    handles=[wave_handle], labels=["Total Papers"],
    handler_map={tuple: HandlerTuple(ndivide=1, pad=0.0)},
    loc="center right", bbox_to_anchor=(0.985, 0.50),
    frameon=False, prop=ARIAL,
    handlelength=1.8, handletextpad=0.45, borderaxespad=0.0,
)
for label in total_legend.get_texts():
    label.set_fontsize(JOURNAL_LABEL_SIZE)

legend_fig.savefig(OUTPUT_DIR / "journal_sources_legend.svg", facecolor="white")
legend_fig.savefig(OUTPUT_DIR / "journal_sources_legend.png", dpi=DPI, facecolor="white")
plt.close(legend_fig)

print(f"Papers: {len(papers)}; journals: {len(totals)}; years: {years[0]}-{years[-1]}")
print(f"Largest journal at 0 degrees: {largest_venue} ({totals[largest_venue]} papers)")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
print(f"Legend: {LEGEND_WIDTH_MM} x {LEGEND_HEIGHT_MM} mm at {DPI} dpi")
