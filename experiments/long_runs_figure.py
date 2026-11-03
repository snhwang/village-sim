#!/usr/bin/env python3
"""The paper's figure of the ten-year runs: each village's people, its granary
and its villagers' live memories, year by year, one line a seed.

    python experiments/long_runs_figure.py [--runs results/long_runs_v4] [--out results/figures]

Read from each run's report (experiments/long_run_report.py) and health check
(experiments/health_check.py) in the --runs folder, whose runs.txt names the
runs, one id a line, seeds in order. People are counted at each year's start
and at the end, the granary at each year's end, and the live memory index per
villager at each year's last trim. Births are not drawn: the paper reports
them per family only. Writes ten_years.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figures import GRID, INK_SOFT, SURFACE, titled  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Three of the validated categorical slots of figures.py, in a fixed order,
# one a seed. Each line is also labelled at its end, so no seed is told by
# colour alone.
SEED_COLOR = ["#2a78d6", "#eb6834", "#1baf7a"]


def runs_of(folder: Path) -> list[str]:
    lines = (folder / "runs.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def series(folder: Path, n: int) -> dict:
    report = json.loads((folder / "report" / f"seed{n}" / "long_run_report.json")
                        .read_text(encoding="utf-8"))
    health = json.loads((folder / "health" / f"seed{n}" / "health_check.json")
                        .read_text(encoding="utf-8"))
    years = report["years"]
    people = [(y["year"], y["people"]) for y in years]
    people.append((years[-1]["year"] + 1, report["village"]["end"]))
    granary = [(y["year"] + 1, y["granary"]) for y in years]
    live = next(c for c in health["checks"] if c["check"].startswith("the live memory index"))
    memories = sorted((int(y) + 1, v) for y, v in live["figures"]["per villager"].items())
    return {"people": people, "granary": granary, "memories": memories}


def draw(folder: Path, out: Path) -> None:
    ids = runs_of(folder)
    data = [series(folder, n) for n in range(1, len(ids) + 1)]
    panels = [("people", "People", "at each year's start, and at the end"),
              ("granary", "Food in the granary", "at each year's end"),
              ("memories", "Live memories per villager", "at each year's end")]
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.9))
    for ax, (key, label, when) in zip(axes, panels):
        for n, d in enumerate(data):
            xs, ys = zip(*d[key])
            ax.plot(xs, ys, color=SEED_COLOR[n], linewidth=2, marker="o", markersize=3.5,
                    markeredgecolor=SURFACE, markeredgewidth=0.8)
            if key == "people":
                ax.annotate(f"seed {n + 1}", (xs[-1], ys[-1]), xytext=(5, 0),
                            textcoords="offset points", va="center", fontsize=7.5,
                            color=INK_SOFT)
        ax.set_title(label, fontsize=9.5, loc="left", pad=14)
        ax.text(0, 1.015, when, transform=ax.transAxes, fontsize=7.5, color=INK_SOFT,
                va="bottom")
        ax.set_xlabel("year")
        ax.set_xlim(-0.3, 11.2 if key == "people" else 10.4)
        ax.set_xticks(range(0, 11, 2))
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.tick_params(length=0)
    handles = [Line2D([], [], color=SEED_COLOR[n], linewidth=2, marker="o", markersize=4,
                      label=f"seed {n + 1}") for n in range(len(data))]
    fig.legend(handles=handles, loc="upper right", ncol=len(handles), frameon=False,
               fontsize=8, bbox_to_anchor=(0.99, 0.985))
    stem = ids[0].rsplit("-seed", 1)[0] if ids else ""
    titled(fig, "Three villages over ten years",
           f"{stem}, seeds 1 to {len(ids)} · 280 in-game days each · 28-day years",
           note="each village grows, its granary dips and recovers, and what each villager "
                "holds in mind levels off")
    # Room under the title block for each panel's title and its note.
    top = fig.subplotpars.top - 0.42 / fig.get_figheight()
    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.13, top=top, wspace=0.28)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out.name}: {len(data)} runs, people {[d['people'][-1][1] for d in data]} at the end")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=Path, default=ROOT / "results" / "long_runs_v4")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "figures")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    draw(args.runs, args.out / "ten_years.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
