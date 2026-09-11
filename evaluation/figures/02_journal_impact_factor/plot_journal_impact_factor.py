"""Plot benchmark-paper counts in 0.5-wide journal-impact-factor bins."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, BLUE_DARK, BLUE_LIGHT, CORAL, GRID, INK, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from journal_metadata import JIF_2024  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
CODE_ROOT = Path(__file__).resolve().parents[3]
PAPER_ROOT = CODE_ROOT / "papers" / "qualified"
FIGURE_WIDTH_MM = 70
FIGURE_HEIGHT_MM = 50
DPI = 500
DATA_RESOLUTION = 0.5
BAR_WIDTH = 0.44
INSET_BAR_WIDTH = 0.90


journal_counts: Counter[str] = Counter()
for path in PAPER_ROOT.glob("**/index.json"):
    record = json.loads(path.read_text(encoding="utf-8"))
    venue = "Nature" if record["venue"] == "Unpublished manuscript" else record["venue"]
    journal_counts[venue] += 1

missing_metadata = journal_counts.keys() - JIF_2024.keys()
if missing_metadata:
    raise KeyError(f"Missing impact-factor metadata for: {sorted(missing_metadata)}")

# Every retained JIF is reported to one decimal place. Paper counts are
# aggregated to the nearest 0.5 JIF for a cleaner print-scale distribution.
impact_factors: list[float] = []
paper_counts: list[int] = []
unassigned_papers = 0
for journal, count in journal_counts.items():
    impact_factor = JIF_2024[journal]
    if impact_factor is None:
        unassigned_papers += count
        continue
    impact_factors.append(float(impact_factor))
    paper_counts.append(count)

raw_values = np.asarray(impact_factors, dtype=float)
raw_counts = np.asarray(paper_counts, dtype=int)
order = np.argsort(raw_values)
raw_values = raw_values[order]
raw_counts = raw_counts[order]
paper_level_values = np.repeat(raw_values, raw_counts)
median = float(np.median(paper_level_values))
maximum = float(np.max(raw_values))

rounded_values = (
    np.floor(raw_values / DATA_RESOLUTION + 0.5) * DATA_RESOLUTION
)
aggregated: Counter[float] = Counter()
for value, count in zip(rounded_values, raw_counts):
    aggregated[float(value)] += int(count)
values = np.asarray(sorted(aggregated), dtype=float)
counts = np.asarray([aggregated[float(value)] for value in values], dtype=int)

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)
ax = fig.add_axes([0.185, 0.155, 0.790, 0.785])
main_mask = values <= 30.0
inset_mask = values > 30.0
bars = ax.bar(
    values[main_mask], counts[main_mask], width=BAR_WIDTH, align="center",
    color=BLUE, edgecolor="none", linewidth=0.0,
    alpha=0.82, zorder=2,
)
for bar, count in zip(bars, counts[main_mask]):
    ax.hlines(
        count, bar.get_x(), bar.get_x() + bar.get_width(),
        color=BLUE_DARK, linewidth=0.52, zorder=3,
    )

ax.axvline(median, color=CORAL, linewidth=0.62, linestyle=(0, (3, 2)), zorder=4)
ax.text(
    median + 0.35, counts.max() + 7.0, f"Median {median:.1f}",
    ha="left", va="top", fontproperties=ARIAL,
    fontsize=FONT_SIZE_LABEL, color=CORAL,
)
ax.set_xlim(0, 30)
ax.set_ylim(0, counts.max() + 12.0)
ax.set_xticks([0, 10, 20, 30])
ax.set_yticks(np.arange(0, 101, 20))
ax.set_xlabel(
    "Journal Impact Factor", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.set_ylabel(
    "Paper Count", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
for label in ax.get_xticklabels() + ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
for spine in ax.spines.values():
    spine.set_visible(True)
    spine.set_color(SLATE)
    spine.set_linewidth(0.62)

# The sparse high-JIF tail is shown as a true inset so that the dense 0--30
# distribution retains useful horizontal resolution. The inset sits above
# the low bars at the right and uses the exact same typography as the parent.
inset_ax = fig.add_axes([0.235, 0.690, 0.315, 0.220], facecolor="white", zorder=8)
inset_bars = inset_ax.bar(
    values[inset_mask], counts[inset_mask], width=INSET_BAR_WIDTH, align="center",
    color=BLUE, edgecolor="none", linewidth=0.0, alpha=0.82, zorder=2,
)
for bar, count in zip(inset_bars, counts[inset_mask]):
    inset_ax.hlines(
        count, bar.get_x(), bar.get_x() + bar.get_width(),
        color=BLUE_DARK, linewidth=0.52, zorder=3,
    )
inset_top = max(5.0, float(counts[inset_mask].max()) + 2.0)
inset_ax.axvline(
    maximum, color=CORAL, linewidth=0.62,
    linestyle=(0, (3, 2)), zorder=4,
)
inset_ax.text(
    maximum - 0.45, inset_top - 0.18, f"Maximum {maximum:.1f}",
    ha="right", va="top", fontproperties=ARIAL,
    fontsize=FONT_SIZE_LABEL, color=CORAL, zorder=5,
)
inset_ax.set_xlim(30, 55)
inset_ax.set_ylim(0, inset_top)
inset_ax.set_xticks([30, 40, 50, 55])
inset_ax.set_yticks([0, 2, 4])
inset_ax.tick_params(
    axis="both", length=2.3, width=0.55, color=SLATE, pad=1.2,
)
for label in inset_ax.get_xticklabels() + inset_ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
for spine in inset_ax.spines.values():
    spine.set_visible(True)
    spine.set_color(SLATE)
    spine.set_linewidth(0.62)

fig.savefig(OUTPUT_DIR / "journal_impact_factor.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "journal_impact_factor.png", dpi=DPI, facecolor="white")
plt.close(fig)

print(
    f"JIF bins: {len(values)} occupied at {DATA_RESOLUTION:.1f} resolution; "
    f"represented papers: {int(counts.sum())}; unassigned papers: "
    f"{unassigned_papers}; paper-weighted median: {median:.1f}; "
    f"maximum JIF: {maximum:.1f}"
)
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
