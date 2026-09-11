"""Plot L1/L2/L3 question-length distributions in three separate axes."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chart_utils import (  # noqa: E402
    ARIAL, ARIAL_BOLD, BLUE, BLUE_LIGHT, CORAL, CORAL_LIGHT, INK,
    SLATE, TEAL, TEAL_LIGHT, FONT_SIZE_DETAIL, FONT_SIZE_LABEL, FONT_SIZE_KEY, plt,
)

CODE_ROOT = Path(__file__).resolve().parents[3]
QUESTION_ROOT = CODE_ROOT / "benchmark" / "question"
OUTPUT_DIR = Path(__file__).parent
FIGURE_WIDTH_MM = 95
FIGURE_HEIGHT_MM = 55
DPI = 500
LAYERS = ("L1", "L2", "L3")
FILLS = (BLUE_LIGHT, TEAL_LIGHT, CORAL_LIGHT)
EDGES = (BLUE, TEAL, CORAL)


def stem_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*|[0-9]+(?:\.[0-9]+)?", text))


lengths = {layer: [] for layer in LAYERS}
for path in sorted(QUESTION_ROOT.glob("**/*.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    # L3 length statistics cover the two evaluated design tasks only. DG3 is
    # outside the evaluation scope and must not contribute to this panel.
    if record.get("layer") == "L3" and record.get("type") == "DG3":
        continue
    if record.get("layer") in lengths and isinstance(record.get("question"), str):
        lengths[record["layer"]].append(stem_word_count(record["question"]))

x = np.arange(30, 331)
kernel_x = np.arange(-12, 13)
kernel = np.exp(-0.5 * (kernel_x / 3.2) ** 2)
kernel /= kernel.sum()

fig, axes = plt.subplots(
    3, 1, figsize=(FIGURE_WIDTH_MM / 25.4, FIGURE_HEIGHT_MM / 25.4),
    sharex=True, sharey=False, facecolor="white",
)
for ax, layer, fill, edge in zip(axes, LAYERS, FILLS, EDGES):
    values = np.asarray(lengths[layer])
    counts, _ = np.histogram(values, bins=np.arange(29.5, 331.5, 1))
    density = np.convolve(counts.astype(float), kernel, mode="same")
    density /= density.max()
    ax.fill_between(x, 0, density, color=fill, alpha=0.98, linewidth=0, zorder=2)
    ax.plot(x, density, color=edge, linewidth=0.82, zorder=3)

    q1, median, q3 = np.percentile(values, [25, 50, 75])
    summary_y = 0.10
    ax.hlines(summary_y, q1, q3, color=INK, linewidth=1.20, zorder=5)
    ax.scatter([median], [summary_y], s=18, color=edge, edgecolor="white",
               linewidth=0.48, zorder=6)
    ax.text(median + 5, summary_y + 0.035, f"Median {median:.0f}", ha="left", va="bottom",
            fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL, color=INK)
    ax.text(0.975, 0.965, f"n={len(values):,}", transform=ax.transAxes,
            ha="right", va="top", fontproperties=ARIAL,
            fontsize=FONT_SIZE_LABEL, color=INK)

    ax.text(0.015, 0.94, layer, transform=ax.transAxes, ha="left", va="top",
            fontproperties=ARIAL, fontsize=FONT_SIZE_LABEL, color=INK)
    ax.set_xlim(30, 330); ax.set_ylim(0, 1.08)
    ax.set_xticks([50, 100, 150, 200, 250, 300])
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.set_ylabel("Density", fontproperties=ARIAL_BOLD,
                  fontsize=FONT_SIZE_KEY, color=INK, labelpad=2)
    ax.grid(False)
    ax.tick_params(axis="both", length=2.3, width=0.55, color=SLATE, pad=2)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(ARIAL); label.set_fontsize(FONT_SIZE_DETAIL)
    for spine in ax.spines.values():
        spine.set_visible(True); spine.set_color(SLATE); spine.set_linewidth(0.62)

axes[-1].set_xlabel(
    "Question-Stem Length (Words)", fontproperties=ARIAL_BOLD,
    fontsize=FONT_SIZE_KEY, color=INK, labelpad=1.0,
)
fig.subplots_adjust(left=0.175, right=0.995, bottom=0.185, top=0.995, hspace=0.13)
fig.savefig(OUTPUT_DIR / "question_length_distribution.svg", facecolor="white")
fig.savefig(OUTPUT_DIR / "question_length_distribution.png", dpi=DPI, facecolor="white")
plt.close(fig)

for layer in LAYERS:
    values = np.asarray(lengths[layer])
    print(f"{layer}: n={len(values):,}, median={np.median(values):.0f}, "
          f"IQR={np.percentile(values, 25):.0f}-{np.percentile(values, 75):.0f}")
print(f"Canvas: {FIGURE_WIDTH_MM} x {FIGURE_HEIGHT_MM} mm at {DPI} dpi")
