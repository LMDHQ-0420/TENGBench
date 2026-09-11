"""Plot the publisher-to-journal structure of the TENGBench paper sources."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, CORAL, GREEN, INK, ORANGE, PURPLE, SLATE,
    TEAL, FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)
from journal_metadata import JIF_2024, PUBLISHER_BY_JOURNAL, display_journal  # noqa: E402

OUTPUT_DIR = Path(__file__).parent
CODE_ROOT = Path(__file__).resolve().parents[3]
PAPER_ROOT = CODE_ROOT / "papers" / "qualified"
FIGURE_WIDTH_MM = 80
FIGURE_HEIGHT_MM = 110
DPI = 500

PUBLISHER_COLORS = {
    "Wiley": BLUE,
    "Elsevier": CORAL,
    "ACS": TEAL,
    "Springer Nature": PURPLE,
    "Tsinghua UP": ORANGE,
    "Cambridge UP": SLATE,
    "AAAS": GREEN,
}


journal_counts: Counter[str] = Counter()
for path in PAPER_ROOT.glob("**/index.json"):
    record = json.loads(path.read_text(encoding="utf-8"))
    venue = "Nature" if record["venue"] == "Unpublished manuscript" else record["venue"]
    journal_counts[venue] += 1

missing_publishers = journal_counts.keys() - PUBLISHER_BY_JOURNAL.keys()
if missing_publishers:
    raise KeyError(f"Missing publisher metadata for: {sorted(missing_publishers)}")

publisher_journals: dict[str, list[str]] = defaultdict(list)
for journal in journal_counts:
    publisher_journals[PUBLISHER_BY_JOURNAL[journal]].append(journal)
publishers = sorted(
    publisher_journals,
    key=lambda publisher: (-len(publisher_journals[publisher]), publisher),
)
for publisher in publishers:
    publisher_journals[publisher].sort(
        key=lambda journal: (-journal_counts[journal], journal)
    )

# Allocate compact source blocks on the left. Destination journals are placed
# independently by paper count on the right, producing a genuine fan-out flow
# rather than a grouped line list.
top, bottom = 0.988, 0.012
group_gap = 0.017
label_units = {"AAAS": 2.6, "Tsinghua UP": 2.1}
block_units = {
    publisher: max(
        float(len(publisher_journals[publisher])),
        label_units.get(publisher, 1.0),
    )
    for publisher in publishers
}
available_block_height = (top - bottom) - group_gap * (len(publishers) - 1)
unit_height = available_block_height / sum(block_units.values())
cursor = top
group_bounds: dict[str, tuple[float, float]] = {}
for publisher in publishers:
    group_top = cursor
    group_bottom = group_top - block_units[publisher] * unit_height
    group_bounds[publisher] = (group_top, group_bottom)
    cursor = group_bottom - group_gap

target_journals = sorted(
    (journal for journal in journal_counts if journal != "Nature Sensors"),
    key=lambda journal: (-float(JIF_2024[journal]), journal),
)
if "Nature Sensors" in journal_counts:
    nature_position = target_journals.index("Nature")
    target_journals.insert(nature_position + 1, "Nature Sensors")
journal_y = {
    journal: float(position)
    for journal, position in zip(
        target_journals, np.linspace(top, bottom, len(target_journals))
    )
}
maximum_count = max(journal_counts.values())
ribbon_height = {
    journal: 0.008 + 0.014 * np.sqrt(journal_counts[journal] / maximum_count)
    for journal in journal_counts
}

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)
ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

publisher_left, publisher_right = 0.005, 0.055
journal_node_x, journal_label_x = 0.665, 0.690

for publisher in publishers:
    color = PUBLISHER_COLORS[publisher]
    journals = sorted(publisher_journals[publisher], key=journal_y.get, reverse=True)
    group_top, group_bottom = group_bounds[publisher]
    node_height = group_top - group_bottom
    node_bottom = group_bottom
    node = Rectangle(
        (publisher_left, node_bottom), publisher_right - publisher_left, node_height,
        facecolor=color, edgecolor="none", linewidth=0.0, alpha=1.0,
        zorder=2,
    )
    ax.add_patch(node)
    if publisher == "Tsinghua UP":
        publisher_label = "TUP"
    elif publisher == "Springer Nature":
        publisher_label = "Springer"
    else:
        publisher_label = publisher
    ax.text(
        (publisher_left + publisher_right) / 2,
        node_bottom + node_height / 2,
        publisher_label,
        rotation=90, rotation_mode="anchor",
        ha="center", va="center",
        fontproperties=ARIAL_BOLD, fontsize=FONT_SIZE_DETAIL,
        color="white", zorder=4,
    )

    source_available = node_height - 0.008
    source_scale = source_available / sum(ribbon_height[journal] for journal in journals)
    source_cursor = group_top - 0.004
    for journal in journals:
        source_height = ribbon_height[journal] * source_scale
        source_y = source_cursor - source_height / 2
        source_cursor -= source_height
        target_y = journal_y[journal]
        target_height = ribbon_height[journal]
        vertices = [
            (publisher_right, source_y + source_height / 2),
            (0.300, source_y + source_height / 2),
            (0.470, target_y + target_height / 2),
            (journal_node_x, target_y + target_height / 2),
            (journal_node_x, target_y - target_height / 2),
            (0.470, target_y - target_height / 2),
            (0.300, source_y - source_height / 2),
            (publisher_right, source_y - source_height / 2),
            (publisher_right, source_y + source_height / 2),
        ]
        path = MplPath(
            vertices,
            [
                MplPath.MOVETO,
                MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                MplPath.LINETO,
                MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                MplPath.CLOSEPOLY,
            ],
        )
        ax.add_patch(PathPatch(
            path, facecolor=color, edgecolor=color,
            linewidth=0.42, alpha=0.22, zorder=1,
        ))
        ax.scatter(
            [journal_node_x], [target_y], s=11, marker="D",
            facecolor=color, edgecolor="white", linewidth=0.45, zorder=3,
        )
        ax.text(
            journal_label_x, target_y, display_journal(journal),
            ha="left", va="center", fontproperties=ARIAL,
            fontsize=FONT_SIZE_DETAIL, color=INK, zorder=4,
        )

fig.savefig(OUTPUT_DIR / "publisher_journal_flow.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "publisher_journal_flow.png", dpi=DPI, facecolor="white")
plt.close(fig)

print(f"Publishers: {len(publishers)}; journals: {len(journal_counts)}")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
