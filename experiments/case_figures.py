#!/usr/bin/env python3
"""Two figures for the case study, from the recorded runs beyond the six.

    python experiments/case_figures.py [--out results/figures]

  lives.png       the forty-day development run (results/development/runs.txt).
                  Above, Maja's first five years: born, at school, and taken on
                  as a farmer by the elder who taught there most. Below, the
                  day Gisla qualified and married Dunn, and the house the
                  village's crafters built for them by the next morning.
  town.png        the 300-villager run (results/scale_runs.txt). A traveler's
                  news through the town, on four afternoons, each villager
                  where it stood.

Everything is read from the runs' events, frames and knowledge, so a figure
cannot disagree with the run it came from. The story in the first is one
family's and one couple's. It draws no births but Maja's, and no genes.
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from figures import (ACCENT, GRID, INK, INK_SOFT, NEUTRAL, STAGE_COLOR,  # noqa: E402
                     SURFACE, titled)
from hearthwick.config import ROOT  # noqa: E402
from hearthwick.follow import world_for  # noqa: E402

RUNS = ROOT / "runs"
RESULTS = ROOT / "results"
DATA = ROOT / "data"
INFANT = "#f3b99f"          # the child slot's tint: the stage before it
PLACE_LABEL = {"forest": "forest edge"}
FELL, BUILD = "#eb6834", "#2a78d6"
MINUTES_PER_TICK = 10
WAKE = 6 * 60


def day_of(tick: int) -> float:
    return (WAKE + tick * MINUTES_PER_TICK) / (24 * 60)


def tick_at(day: int, hour: float) -> int:
    return int((day * 24 * 60 + hour * 60 - WAKE) / MINUTES_PER_TICK)


def first_run(listing: str) -> str:
    return next(line.split()[0] for line in (RESULTS / listing).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#"))


def read_events(run: Path, types: set[str]) -> list[dict]:
    out = []
    with open(run / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e["type"] in types:
                out.append(e)
    return out


def frames_between(run: Path, first: int, last: int):
    """Frames from tick ``first`` to ``last``. A frame line starts
    ``{"t":<tick>,``, so only the tick is read until then."""
    with open(run / "frames.jsonl", encoding="utf-8") as f:
        for line in f:
            t = int(line[5:line.index(",")])
            if t > last:
                return
            if t >= first:
                yield json.loads(line)


def nudge(cid: str) -> tuple[float, float]:
    """Several villagers share a tile, so each is drawn at its own spot in it,
    the same spot every time the figure is drawn."""
    return ((zlib.crc32(cid.encode()) % 7) / 7 - 0.43,
            (zlib.crc32(cid[::-1].encode()) % 7) / 7 - 0.43)


# --- a career, and a house ------------------------------------------------

def fig_lives(run: Path, out: Path) -> None:
    ev = read_events(run, {"roster", "born", "stage_change", "apprenticed", "took_up_trade",
                           "proposed", "married", "place_added", "house_built", "decision"})
    names = {c["id"]: c["name"] for e in ev if e["type"] == "roster" for c in e["characters"]}
    born = next(e for e in ev if e["type"] == "born" and e["character"] == "maja")
    stages = [(day_of(born["t"]), "infant")] + [
        (day_of(e["t"]), e["now"]) for e in ev
        if e["type"] == "stage_change" and e["character"] == "maja"]
    taken = next(e for e in ev if e["type"] == "apprenticed" and e["character"] == "maja")
    school = defaultdict(set)
    for e in ev:
        if e["type"] == "decision" and (e["character"], e.get("chosen")) in (
                ("maja", "child-school"), (taken["master"], "elder-teach")):
            school[e["character"]].add(int(day_of(e["t"])))
    end_day = max(day_of(e["t"]) for e in ev)

    fig, (a, b) = plt.subplots(2, 1, figsize=(9.5, 7.6), height_ratios=[1, 1.35])

    # Above: Maja's first five years.
    edges = [d for d, _ in stages] + [end_day]
    for (start, stage), stop in zip(stages, edges[1:]):
        a.barh(2, stop - start, left=start, height=0.5, color=INFANT if stage == "infant"
               else STAGE_COLOR[stage], edgecolor=SURFACE, linewidth=2)
        a.text(start + 0.4, 2, stage, va="center", fontsize=8.5,
               color=INK if stage == "infant" else SURFACE)
    master = names.get(taken["master"], taken["master"])
    for row, who, label in ((1, "maja", "Maja at school"),
                            (0, taken["master"], f"{master} teaching there")):
        days = sorted(school[who])
        a.scatter([d + 0.5 for d in days], [row] * len(days), s=26, marker="s",
                  color=ACCENT if who == "maja" else NEUTRAL, edgecolors=SURFACE, zorder=3)
    a.set_yticks([2, 1, 0], ["Maja", "Maja at school", f"{master} teaching there"])
    a.tick_params(axis="y", length=0)
    a.annotate(f"born to {names['rosa']}, a storyteller,\nand {names['osric']}, a farmer",
               xy=(day_of(born["t"]), 2.25), xytext=(0.2, 2.75), fontsize=8.5, color=INK,
               arrowprops=dict(arrowstyle="-", color=INK_SOFT, lw=0.8))
    took = day_of(taken["t"])
    a.annotate(f"chooses farming, under {master}\n(fondness {taken['fondness']:.1f})",
               xy=(took, 2.25), xytext=(took - 9.5, 2.75), fontsize=8.5, color=INK,
               arrowprops=dict(arrowstyle="-", color=INK_SOFT, lw=0.8))
    a.set_ylim(-0.6, 3.3)
    a.set_xlim(0, end_day)
    a.set_xlabel("in-game day (eight days a year)")
    a.grid(axis="x", color=GRID, linewidth=0.8)
    a.set_axisbelow(True)
    a.spines["left"].set_visible(False)
    a.set_title("Maja's first five years", loc="left", fontsize=10.5, fontweight="bold")

    # Below: from Gisla qualifying to the house she and Dunn moved into.
    proposed = next(e for e in ev if e["type"] == "proposed")
    married = next(e for e in ev if e["type"] == "married" and e["asker"] == proposed["asker"])
    site = next(e for e in ev if e["type"] == "place_added" and e["place"]["kind"] == "site")
    built = next(e for e in ev if e["type"] == "house_built")
    qualified = next(e for e in ev if e["type"] == "took_up_trade"
                     and e["character"] == proposed["asker"])
    day0 = int(day_of(qualified["t"]))
    first, last = tick_at(day0, 6), built["t"] + 3
    work = defaultdict(list)
    for frame in frames_between(run, first, last):
        for row in frame["c"]:
            if row[3] in ("fell", "build"):
                work[row[0]].append((frame["t"], row[3]))
    hours = lambda t: (t - tick_at(day0, 0)) * MINUTES_PER_TICK / 60  # noqa: E731
    couple = [proposed["asker"], proposed["asked"]]
    crafters = couple + sorted((c for c in work if c not in couple), key=lambda c: names[c])
    for y, who in enumerate(reversed(crafters)):
        for t, kind in work[who]:
            b.barh(y, MINUTES_PER_TICK / 60, left=hours(t), height=0.55,
                   color=FELL if kind == "fell" else BUILD, linewidth=0)
    b.set_yticks(range(len(crafters)), [names[c] for c in reversed(crafters)])
    b.tick_params(axis="y", length=0)
    # Gisla qualified at midnight, before anyone was up, which the caption
    # says, so the panel starts with the morning.
    moments = [(proposed["t"], 2, "left",
                f"{names[couple[0]]} asks {names[couple[1]]}\n"
                f"(fondness {proposed['affinity']:.1f})"),
               (married["t"], 1, "left", "they marry"),
               (site["t"], 0, "left", f"{names[site['by']]} lays out a plot"),
               (built["t"], 2, "right", "the house\nis finished")]
    top = len(crafters) - 0.3
    for t, level, side, label in moments:
        x = hours(t)
        b.axvline(x, color=INK_SOFT, linewidth=0.8, linestyle=(0, (2, 2)), zorder=0)
        b.text(x + (0.2 if side == "left" else -0.2), top + 1.1 * level, label,
               fontsize=8, color=INK, va="bottom", ha=side, zorder=4,
               bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))
    b.set_ylim(-0.6, len(crafters) + 3.3)
    b.set_xlim(hours(first) - 0.5, hours(last) + 0.5)
    ticks = list(range(6, int(hours(last)) + 2, 3))
    b.set_xticks(ticks, [f"{h % 24:02d}:00" + ("" if h < 24 else "\nnext day")
                         if h % 12 == 0 or h == 6 else f"{h % 24:02d}:00" for h in ticks])
    b.set_xlabel(f"day {day0} into day {day0 + 1}, by the clock")
    b.grid(axis="x", color=GRID, linewidth=0.8)
    b.set_axisbelow(True)
    b.spines["left"].set_visible(False)
    b.legend(handles=[Patch(color=FELL, label="felling timber"),
                      Patch(color=BUILD, label="building")],
             loc="lower left", bbox_to_anchor=(0.62, 0.0), frameon=False, fontsize=8.5)
    b.set_title("A house in a day", loc="left", fontsize=10.5, fontweight="bold")

    titled(fig, "Growing up, marrying, building",
           f"{run.name} · 40 in-game days · the greater village",
           note="every mark is from the run's log, of what each villager was doing "
                "and what it chose")
    # Room for the first panel's own title under the figure's.
    fig.subplots_adjust(top=fig.subplotpars.top - 0.35 / fig.get_figheight(),
                        left=0.16, right=0.97, bottom=0.08, hspace=0.62)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out.name}: Maja taken on by {master}, {len(crafters)} crafters at the house")


# --- a town of three hundred ---------------------------------------------

def fig_town(run: Path, out: Path) -> None:
    knowledge = json.loads((run / "knowledge.json").read_text(encoding="utf-8"))
    by_root = defaultdict(dict)
    for holder, facts in knowledge.items():
        for f in facts:
            if f["root"].startswith("traveler:"):
                by_root[f["root"]][holder] = min(by_root[f["root"]].get(holder, 1 << 30),
                                                 f["tick"])
    root = max(by_root, key=lambda r: (len(by_root[r]), -min(by_root[r].values())))
    held = by_root[root]
    hops = max(f["hop"] for facts in knowledge.values() for f in facts if f["root"] == root)
    world = world_for(run, DATA)
    start = int(day_of(min(held.values())))
    moments = [tick_at(start + i, 14) for i in range(4)]
    frames = {f["t"]: f for f in frames_between(run, moments[0], moments[-1])
              if f["t"] in moments}
    everyone = len(frames[moments[0]]["c"])

    xs = [p.rect[0] for p in world.places.values()] + [p.rect[0] + p.rect[2] for p in world.places.values()]
    ys = [p.rect[1] for p in world.places.values()] + [p.rect[1] + p.rect[3] for p in world.places.values()]
    box = (min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)

    fig, axes = plt.subplots(2, 2, figsize=(9.5, 8.2))
    for ax, t in zip(axes.flat, moments):
        for b in world.blocked:
            x, y, w, h = b["rect"]
            ax.add_patch(Rectangle((x, y), w, h, color="#cfe0f3", linewidth=0))
        for p in world.places.values():
            x, y, w, h = p.rect
            home = p.kind == "home"
            ax.add_patch(Rectangle((x, y), w, h, facecolor=GRID if home else "#efeee9",
                                   edgecolor=SURFACE if home else "#c9c7bf", linewidth=0.6))
            if p.kind == "road":
                ax.text(x + w / 2, y + h + 0.4, "east road", fontsize=6.5,
                        ha="center", va="top", color=INK_SOFT)
            elif not home:
                ax.text(x + w / 2, y - 0.4, PLACE_LABEL.get(p.kind, p.kind), fontsize=6.5,
                        ha="center", va="bottom", color=INK_SOFT)
        rows = frames[t]["c"]
        knows = [r for r in rows if held.get(r[0], 1 << 30) <= t]
        others = [r for r in rows if held.get(r[0], 1 << 30) > t]
        for group, color, z in ((others, NEUTRAL, 2), (knows, ACCENT, 3)):
            ax.scatter([r[1] + 0.5 + nudge(r[0])[0] for r in group],
                       [r[2] + 0.5 + nudge(r[0])[1] for r in group],
                       s=9, color=color, edgecolors="none", zorder=z)
        ax.set_xlim(box[0], box[1])
        ax.set_ylim(box[3], box[2])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ax.spines.values():
            side.set_visible(False)
        ax.set_title(f"day {int(day_of(t))}, 2 pm: {len(knows)} of {everyone} hold it",
                     loc="left", fontsize=10, fontweight="bold" if len(knows) else "normal")
    last = max(held.values())
    seen = sum(1 for v in held.values() if v == min(held.values()))
    words = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    titled(fig, f"A traveler's news through a town of {everyone}",
           f"{run.name} · 10 in-game days · town300 · each dot a villager where it stood",
           note=f"{words[seen] if seen < 10 else seen} saw the traveler on the road, "
                f"and the rest were told, each keeping "
                f"it in its own words, up to {hops} tellings on. All {len(held)} held it by "
                f"the evening of day {int(day_of(last))}.")
    fig.legend(handles=[Line2D([], [], marker="o", linestyle="", markersize=5, color=ACCENT,
                               label="holds the news"),
                        Line2D([], [], marker="o", linestyle="", markersize=5, color=NEUTRAL,
                               label="not yet")],
               loc="upper right", bbox_to_anchor=(0.985, 1 - 0.8 / fig.get_figheight()),
               ncol=2, frameon=False, fontsize=8.5)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, hspace=0.12, wspace=0.05)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out.name}: {root}, {len(held)} holders")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(RESULTS / "figures"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_lives(RUNS / first_run("development/runs.txt"), out / "lives.png")
    fig_town(RUNS / first_run("scale_runs.txt"), out / "town.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
