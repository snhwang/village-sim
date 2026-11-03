#!/usr/bin/env python3
"""Figure 1 of the case study: one retrieval step and its three uses.

    python experiments/pipeline_figure.py

A diagram, not data, so it reads nothing from a run. It draws what §3 of the
paper describes: a villager's situation becomes tags and a query, one gated
retrieval step ranks its instructions, and the same step serves acting,
speaking and absorbing. What a villager keeps becomes a tag, which changes
what it can retrieve next.

Writes results/figures/fig0_pipeline.png.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "figures" / "fig0_pipeline.png"

# The palette the other figures use (experiments/figures.py).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#c9c7bf"
ACCENT = "#2a78d6"
ACCENT_FILL = "#e8f1fc"
BOX_FILL = "#ffffff"


def box(ax, x, y, w, h, title, lines, fill=BOX_FILL, edge=GRID, title_color=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                linewidth=1.2, edgecolor=edge, facecolor=fill))
    ax.text(x + 1.4, y + h - 1.6, title, fontsize=9.5, fontweight="bold",
            color=title_color, va="top", ha="left")
    ax.text(x + 1.4, y + h - 5.0, "\n".join(lines), fontsize=8.2, color=INK_SOFT,
            va="top", ha="left", linespacing=1.35)


def arrow(ax, start, end, color=INK_SOFT, rad=0.0, lw=1.2):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=11,
                                 color=color, linewidth=lw,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))


def main() -> int:
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "font.size": 9})
    fig = plt.figure(figsize=(10.4, 5.6))
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.84])
    ax.set_xlim(0, 104)
    ax.set_ylim(-6, 57)
    ax.axis("off")

    fig.text(0.015, 0.965, "One retrieval step, three uses", fontsize=14,
             fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.912, "what a villager does, what it says, and what it makes of "
             "what it is told", fontsize=10, color=INK, ha="left", va="top")

    # the situation
    box(ax, 1, 13, 22, 33, "A villager's situation",
        ["stage, role, temperament", "time and weather", "where it stands",
         "who is near", "whether it is tired", "one tag for each", "thing it knows",
         "", "becomes tags and", "a query sentence"])

    # the one step
    box(ax, 27.5, 21.5, 20.5, 16, "One retrieval step",
        ["hard gates admit", "instructions, and", "similarity with", "priority ranks them"],
        fill=ACCENT_FILL, edge=ACCENT, title_color=ACCENT)
    ax.text(37.75, 19.2, "the world decides by the\nsame step, with its own\ninstructions",
            fontsize=7.8, color=INK_SOFT, ha="center", va="top", style="italic")
    arrow(ax, (23, 29.5), (27.5, 29.5))

    # three lanes from the same step
    lanes = [
        (43, "Act", ["resolve markers down the", "ranking, and choose among",
                     "the first four that can act"],
         "Markers dispatched", ["go, work, rest, talk,", "warn, avoid, and more",
                                "no model call"]),
        (25.5, "Speak (tagged talking)", ["the retrieved instructions", "compose the prompt"],
         "The model speaks", ["one call for each", "line of a conversation"]),
        (8, "Absorb (tagged absorbing)", ["the lens: the model rewrites",
                                          "what was heard in the",
                                          "listener's terms, or refuses it"],
         "Kept in its own words", ["with a tag of the form", "knows_<kind>_<place>"]),
    ]
    for y, t1, l1, t2, l2 in lanes:
        box(ax, 54, y, 25, 13, t1, l1)
        box(ax, 82, y, 21, 13, t2, l2)
        arrow(ax, (79, y + 6.5), (82, y + 6.5))
        arrow(ax, (48, 29.5), (54, y + 6.5))

    # what is kept feeds back into the situation
    arrow(ax, (92.5, 8), (12, 13), color=ACCENT, rad=-0.2, lw=1.4)
    ax.text(52, -5.6, "what a villager keeps becomes a tag, so it can retrieve "
            "instructions it could not before", fontsize=8.4, color=ACCENT, ha="center",
            va="bottom")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
