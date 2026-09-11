"""Plot L1 mechanism-subtype question counts as a compact dot-track chart."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

from matplotlib.lines import Line2D
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, INK, PALE_GREY, SLATE,
    FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, display_label,
    load_questions, plt,
)

OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 95
FIGURE_HEIGHT_MM = 70
DPI = 500


def compact_name(label: str) -> str:
    overrides = {
        "contact_separation": "Contact separation",
        "displacement_current": "Displacement current",
        "electrostatic_induction": "Electrostatic induction",
        "impedance_matching": "Impedance matching",
        "output_coupling": "Output coupling",
        "single_electrode": "Single electrode",
        "surface_modification": "Surface modification",
        "triboelectric_mechanism": "Tribo. mechanism",
        "triboelectric_series": "Tribo. series",
    }
    return overrides.get(label, display_label(label))


questions = load_questions()
counts = Counter(q["subcategory"] for q in questions if q["layer"] == "L1")
items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
values = np.asarray([value for _, value in items])
y = np.arange(len(items))
xmax = float(values.max()) * 1.22

fig = plt.figure(
    figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    facecolor="white",
)
ax = fig.add_axes([0.345, 0.170, 0.625, 0.800])

# Draw the grey track and endpoint with the same point diameter.  The rounded
# cap at x=0 is clipped by the axes boundary, leaving a clean square end on the
# coordinate axis; the value-side cap is exactly covered by the data circle.
band_diameter_pt = 5.0
for row, value in zip(y, values):
    ax.plot(
        [0, value], [row, row], color=PALE_GREY,
        linewidth=band_diameter_pt, solid_capstyle="round",
        clip_on=True, zorder=1,
    )
ax.scatter(
    values, y, s=band_diameter_pt**2, color=BLUE,
    edgecolor="white", linewidth=0.55, zorder=3,
)
for row, value in zip(y, values):
    ax.annotate(
        str(value), xy=(value, row), xytext=(5.5, 0),
        textcoords="offset points", ha="left", va="center",
        fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL, color=BLUE,
    )

ax.set_yticks(y)
ax.set_yticklabels(
    [compact_name(label) for label, _ in items],
    fontproperties=ARIAL, fontsize=FONT_SIZE_DETAIL,
)
ax.invert_yaxis()
ax.set_xlim(0, xmax)
ax.set_xlabel(
    "Number of Questions", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=3,
)
ax.set_ylabel(
    "Mechanism Subtype", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=4,
)
ax.grid(False)
ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
for label in ax.get_xticklabels() + ax.get_yticklabels():
    label.set_fontproperties(ARIAL)
    label.set_fontsize(FONT_SIZE_DETAIL)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color(SLATE)
    ax.spines[side].set_linewidth(0.62)
# Explicit terminal ticks make the finite ends of both axes unambiguous.
ax.plot([1, 1], [0, -0.010], transform=ax.transAxes, color=SLATE,
        linewidth=0.62, clip_on=False, zorder=6)
ax.plot([-0.010, 0], [1, 1], transform=ax.transAxes, color=SLATE,
        linewidth=0.62, clip_on=False, zorder=6)

legend_font = ARIAL.copy()
legend_font.set_size(FONT_SIZE_DETAIL)
ax.legend(
    handles=[
        Line2D(
            [], [], linestyle="none", marker="o", markersize=4.2,
            markerfacecolor=BLUE, markeredgecolor="white",
            markeredgewidth=0.45, label="Fundamentals (L1)",
        )
    ],
    loc="lower right", bbox_to_anchor=(0.985, 0.025),
    frameon=False, ncol=1, handletextpad=0.35,
    borderaxespad=0.2, prop=legend_font,
)

fig.savefig(OUTPUT_DIR / "l1_mechanism_distribution.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "l1_mechanism_distribution.png", dpi=DPI, facecolor="white")
plt.close(fig)

print(f"L1 questions: {int(values.sum()):,}; subtypes: {len(values)}")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
