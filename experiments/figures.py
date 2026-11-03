#!/usr/bin/env python3
"""Figures for the paper, from one run's logs.

    python experiments/figures.py                 # the most recent run
    python experiments/figures.py <run_id>
    python experiments/figures.py --out results/figures

Produces:

  fig1_provenance.png  one event, and how it reached everyone: who told whom,
                       and how many tellings from the event, with the words
                       held along the chains to the villagers named by
                       --follow, or along the deepest chain without it, as
                       the paper-v4 paper draws it (paper-v3's was
                       --follow osric thea)
  fig2_spread.png      how many villagers held each event's news over time
  fig3_usage.png       which instructions were chosen, and what knowing
                       something unlocked
  memories.md          the same news as four villagers kept it, side by side

Everything is read from runs/<id>/{events,frames}.jsonl and knowledge.json, so
a figure can never disagree with the run it came from.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hearthwick.config import ROOT  # noqa: E402
from hearthwick.knowledge import EXPERIENCE_KINDS  # noqa: E402

# Validated categorical slots (dataviz skill, light surface). Life stage is the
# identity here: four categories, each node also labelled by name, which is the
# relief the aqua slot's contrast requires.
# Infants hold news too, as witnesses, once births are on (the illustrative
# profile). Without a colour the first figure stopped on 2026-10-19.
STAGE_COLOR = {"infant": "#b8860b", "child": "#eb6834", "apprentice": "#1baf7a",
               "adult": "#2a78d6", "elder": "#4a3aa7"}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#e3e2dd"
ACCENT = "#2a78d6"
NEUTRAL = "#b9b7ae"

TICKS_PER_DAY = 144
WAKE_HOUR = 6

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.size": 9,
    "text.color": INK, "axes.labelcolor": INK_SOFT, "axes.edgecolor": GRID,
    "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
    "axes.spines.top": False, "axes.spines.right": False,
})


def day_of(tick: int) -> float:
    return (WAKE_HOUR * 60 + tick * 10) / (24 * 60)


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.events = [json.loads(l) for l in
                       (path / "events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.knowledge = json.loads((path / "knowledge.json").read_text(encoding="utf-8"))
        self.meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        self.usage = json.loads((path / "usage.json").read_text(encoding="utf-8"))
        # Every roster line: a visitor adds itself when it arrives.
        self.people = {c["id"]: c for e in self.events if e["type"] == "roster"
                       for c in e["characters"]}

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["type"] == kind]

    def name(self, cid: str) -> str:
        return self.people[cid]["name"] if cid in self.people else cid

    def stage(self, cid: str) -> str:
        return self.people[cid]["stage"] if cid in self.people else "adult"

    def facts_by_root(self) -> dict[str, list[dict]]:
        by_root = defaultdict(list)
        for facts in self.knowledge.values():
            for f in facts:
                # News only. A conversation memory has a root of its own and
                # one holder, so it would read as an event nobody passed on.
                if f["kind"] in EXPERIENCE_KINDS:
                    continue
                by_root[f["root"]].append(f)
        return by_root

    def busiest_root(self) -> str | None:
        """The event that travelled furthest, not the one most people hold.

        Weather and festivals are witnessed village-wide, so everyone holds
        them at hop 0 and they top any count of holders -- while being exactly
        the events that never diffuse. A provenance figure wants the opposite:
        an event that started with a few witnesses and reached the rest by
        being told. Rank by how many tellings deep the chain goes, then by how
        many hold it.
        """
        by_root = self.facts_by_root()
        travelled = {r: fs for r, fs in by_root.items()
                     if max(f["hop"] for f in fs) > 0}
        if travelled:
            return max(travelled,
                       key=lambda r: (max(f["hop"] for f in travelled[r]),
                                      len(travelled[r])))
        if not by_root:
            return None
        return max(by_root, key=lambda r: len(by_root[r]))

    def subtitle(self) -> str:
        speech = (self.meta.get("speech_model") or {}).get("model", "no speech model")
        embedder = (self.meta.get("embedder") or {}).get("model") or "BM25"
        days = self.meta.get("ticks", 0) / TICKS_PER_DAY
        return (f"{self.path.name} · {days:.0f} in-game days · {len(self.people)} villagers · "
                f"{speech} · {embedder.split('/')[-1]}")


def titled(fig, title: str, subtitle: str, note: str = "") -> None:
    """Title block on the figure, sized in inches so it never lands on the marks."""
    height = fig.get_figheight()
    inch = lambda i: i / height          # noqa: E731 - inches as a figure fraction
    x, y = 0.012, 1 - inch(0.30)
    fig.text(x, y, title, fontsize=13.5, fontweight="bold", va="top", color=INK)
    y -= inch(0.34)
    if note:
        fig.text(x, y, note, fontsize=8.8, va="top", color=INK)
        y -= inch(0.26)
    fig.text(x, y, subtitle, fontsize=8, va="top", color=INK_SOFT)
    fig.subplots_adjust(top=y - inch(0.34))


def stage_legend(ax, stages) -> None:
    handles = [Line2D([], [], marker="o", linestyle="", markersize=8,
                      markerfacecolor=STAGE_COLOR[s], markeredgecolor=SURFACE, label=s)
               for s in ("infant", "child", "apprentice", "adult", "elder") if s in stages]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8,
              handletextpad=0.4, borderpad=0.2)


# --- figure 1: one event, and how it reached everyone ---------------------

def chain_to(facts: list[dict], holder: str) -> list[dict]:
    """The tellings that brought an event to one holder, from the witness on."""
    by_holder = {f["holder"]: f for f in facts}
    chain, f = [], by_holder.get(holder)
    while f is not None:
        chain.append(f)
        f = by_holder.get(f["teller"]) if f["teller"] else None
    return chain[::-1]


def fig_provenance(run: Run, root: str, out: Path, follow: list[str] | None = None) -> None:
    """Everyone who came to hold one event, by tellings from it, at the size
    a page prints it. Every villager is a named dot. The chains to the
    holders in ``follow`` are drawn dark, and the words each villager on them
    held are set out below, since thirty sentences cannot be read at a
    page's width (memories.md has them all)."""
    facts = sorted(run.facts_by_root()[root], key=lambda f: (f["hop"], f["tick"]))
    deepest = max(facts, key=lambda f: (f["hop"], -f["tick"]))
    follow = follow or [deepest["holder"]]
    # A holder named for one run may not hold the event in another, such as
    # a fresh reproduction, so the deepest holder stands in for the missing.
    chains = [c for c in (chain_to(facts, h) for h in follow) if c] or \
        [chain_to(facts, deepest["holder"])]
    follow = [c[-1]["holder"] for c in chains]
    dark = {f["holder"] for c in chains for f in c}

    # Columns by tellings from the event. Within a column, a listener sits
    # in its teller's order, so the arrows cross as little as they can.
    by_hop = defaultdict(list)
    for f in facts:
        by_hop[f["hop"]].append(f)
    order: dict[str, int] = {}
    for hop in sorted(by_hop):
        by_hop[hop].sort(key=lambda f: (order.get(f["teller"], 0), f["tick"]))
        order.update({f["holder"]: i for i, f in enumerate(by_hop[hop])})
    rows = max(len(v) for v in by_hop.values())
    pos = {f["holder"]: (hop, (len(group) - 1) / 2 - i)
           for hop, group in by_hop.items() for i, f in enumerate(group)}

    wrap = 104
    quoted = [(f, textwrap.wrap(f["text"], wrap)) for c in chains for f in c]
    text_lines = sum(len(w) for _, w in quoted) + 0.6 * (len(chains) - 1)
    tree_h, text_h = 0.36 * rows + 0.55, 0.165 * text_lines + 0.35
    fig = plt.figure(figsize=(8.0, tree_h + text_h + 1.15))
    grid = fig.add_gridspec(2, 1, height_ratios=[tree_h, text_h], hspace=0.16)
    ax, below = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])

    for f in facts:
        if f["teller"] and f["teller"] in pos:
            (x0, y0), (x1, y1) = pos[f["teller"]], pos[f["holder"]]
            on = f["holder"] in dark and f["teller"] in dark
            ax.add_patch(FancyArrowPatch((x0 + 0.07, y0), (x1 - 0.07, y1),
                                         arrowstyle="-|>", mutation_scale=7,
                                         color=INK if on else NEUTRAL,
                                         linewidth=1.3 if on else 0.8,
                                         connectionstyle="arc3,rad=0.06", zorder=2 if on else 1))
    for f in facts:
        x, y = pos[f["holder"]]
        on = f["holder"] in dark
        ax.scatter([x], [y], s=46 if on else 30, zorder=3,
                   color=STAGE_COLOR[run.stage(f["holder"])], edgecolors=SURFACE, linewidths=1)
        ax.text(x, y + 0.17, run.name(f["holder"]), ha="center", va="bottom", fontsize=8.2,
                fontweight="bold" if on else "normal", color=INK if on else INK_SOFT, zorder=4)
    ax.set_xticks(sorted(by_hop))
    ax.set_xticklabels(["saw it" if h == 0 else f"{h} telling{'s' if h > 1 else ''}"
                        for h in sorted(by_hop)], fontsize=8.2)
    ax.tick_params(axis="x", length=0)
    ax.set_yticks([])
    ax.set_xlim(-0.45, max(by_hop) + 0.45)
    ax.set_ylim(-(rows - 1) / 2 - 0.45, (rows - 1) / 2 + 0.6)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_visible(False)
    stage_legend(ax, {run.stage(f["holder"]) for f in facts})

    # The words along each dark chain, one villager to a line.
    below.axis("off")
    below.set_xlim(0, 1)
    below.set_ylim(text_lines + 0.2, -0.3)
    y = 0.0
    for n, chain in enumerate(chains):
        if n:
            y += 0.6
        for f in chain:
            told = "saw it" if f["hop"] == 0 else f"{f['hop']} telling{'s' if f['hop'] > 1 else ''}"
            below.text(0.0, y, told, fontsize=7.8, color=INK_SOFT, va="top")
            below.scatter([0.098], [y + 0.36], s=22, color=STAGE_COLOR[run.stage(f["holder"])],
                          clip_on=False)
            below.text(0.112, y, run.name(f["holder"]), fontsize=8.2, fontweight="bold", va="top")
            lines = textwrap.wrap(f["text"], wrap)
            below.text(0.215, y, "\n".join(lines), fontsize=8.2, color=INK, va="top",
                       linespacing=1.35)
            y += len(lines)

    event, place, _ = root.split(":")
    titled(fig, "One event, and how it reached the village", run.subtitle(),
           note=f"a {event} at the {place.replace('_', ' ')}: everyone who came to hold it, "
                f"and below, the words along the dark chains")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02)
    fig.savefig(out, dpi=250)
    plt.close(fig)
    print(f"  {out.name}: {len(facts)} holders, {max(by_hop)} hops, "
          f"following {', '.join(run.name(h) for h in follow)}")


# --- figure 2: how fast each piece of news travelled ----------------------

def fig_spread(run: Run, out: Path) -> None:
    by_root = {r: fs for r, fs in run.facts_by_root().items() if len(fs) > 1}
    if not by_root:
        print("  fig2 skipped: no news reached a second villager")
        return
    roots = sorted(by_root, key=lambda r: -len(by_root[r]))[:4]
    world = {f"{e['event']}:{e['place'] or '-'}:{e['t']}": e for e in run.of("world_event")}

    # Colour identifies the event here, not the life stage of figure 1: each
    # line is directly labelled, so the two figures cannot be confused.
    event_colors = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    last_x = 0.0
    for slot, root in enumerate(roots):
        facts = sorted(by_root[root], key=lambda f: f["tick"])
        xs, ys = [day_of(facts[0]["tick"])], [0]
        for i, f in enumerate(facts, start=1):
            xs += [day_of(f["tick"]), day_of(f["tick"])]
            ys += [ys[-1], i]
        color = event_colors[slot % len(event_colors)]
        event = world.get(root)
        place = (event or {}).get("place") or ""
        label = (f"{event['event']} at the {place.replace('_', ' ')}" if event and place
                 else (event["event"] if event else root))
        last_x = max(last_x, xs[-1])
        ax.step(xs, ys, where="post", color=color, linewidth=2, zorder=3)
        ax.text(xs[-1] + 0.05, ys[-1], f"{label}\n{ys[-1]} villagers", va="center",
                fontsize=8.5, color=INK)
        ax.scatter([xs[0]], [0], s=42, color=color, zorder=4, edgecolors=SURFACE,
                   linewidths=1.5)

    ax.set_xlabel("in-game day")
    ax.set_ylabel("villagers holding it")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(-0.4, len(run.people) + 0.4)
    ax.set_xlim(left=None, right=last_x * 1.42)   # room for the direct labels
    titled(fig, "News spreading, one telling at a time", run.subtitle(),
           note="a dot marks the moment the villagers who saw it held it first-hand")
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.13)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out.name}: {len(roots)} events tracked")


# --- figure 3: what the corpus actually did -------------------------------

def fig_usage(run: Run, out: Path) -> None:
    counts = Counter(run.usage["chosen_counts"])
    # The instructions only reachable once a villager knows something are the
    # point of the figure, so they are always shown, not just when they rank.
    # Classified by their knows_ gate, as knowledge_flow.py counts them. By
    # the "knows-" prefix of the id, the most chosen of them, passing on word
    # of coming danger, was drawn as if knowledge did not gate it (paper-v4).
    from knowledge_flow import knowledge_gated
    gated = knowledge_gated()
    knowing = {i: n for i, n in counts.items() if i in gated}
    top = dict(counts.most_common(15))
    top.update(knowing)
    order = sorted(top.items(), key=lambda kv: kv[1])
    labels = [i for i, _ in order]
    values = [n for _, n in order]
    colors = [ACCENT if i in gated else NEUTRAL for i in labels]

    fig, ax = plt.subplots(figsize=(9, 0.32 * len(order) + 2.3))
    ax.barh(range(len(order)), values, color=colors, height=0.68)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels, fontsize=8)
    for i, v in enumerate(values):
        ax.text(v + max(values) * 0.012, i, str(v), va="center", fontsize=8, color=INK_SOFT)
    ax.set_xlabel("times chosen")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.margins(x=0.08)

    share = run.usage["similarity_decided_pct"]
    used = f"{run.usage['instructions_chosen']}/{run.usage['actionable_instructions']}"
    titled(fig, "Which instructions the villagers chose", run.subtitle(),
           note=f"similarity, not priority, decided {share}% of {run.usage['decisions']} decisions · "
                f"{used} actionable instructions used")
    if knowing:
        ax.legend(handles=[Line2D([], [], marker="s", linestyle="", markersize=9,
                                  markerfacecolor=ACCENT, markeredgecolor=SURFACE,
                                  label="only reachable once the villager knows something")],
                  loc="lower right", frameon=False, fontsize=8)
    fig.subplots_adjust(left=0.30, right=0.97, bottom=0.09)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out.name}: {len(order)} instructions shown, {len(knowing)} unlocked by knowledge")


# --- the same news, side by side (a table, not a chart) -------------------

def write_memories(run: Run, root: str, out: Path) -> None:
    facts = sorted(run.facts_by_root()[root], key=lambda f: (f["hop"], f["holder"]))
    lines = ["# The same news, as each villager kept it", "",
             f"Run `{run.path.name}`, event `{root}`.", "",
             "| Villager | | How they heard it | What they hold |", "|---|---|---|---|"]
    for f in facts:
        who = run.people.get(f["holder"], {})
        traits = ", ".join(sorted(who.get("temperament", {}).values())) if who else ""
        heard = "saw it happen" if not f["teller"] else \
            f"told by {run.name(f['teller'])} ({f['hop']} telling{'s' if f['hop'] != 1 else ''} from the event)"
        lines.append(f"| **{run.name(f['holder'])}** | {who.get('stage','')}"
                     f"{', ' + who['role'] if who.get('role') else ''}<br><sub>{traits}</sub> "
                     f"| {heard} | {f['text']} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {out.name}: {len(facts)} villagers")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id", nargs="?", default=None)
    parser.add_argument("--out", default=str(ROOT / "results" / "figures"))
    parser.add_argument("--root", default=None, help="which event to trace (default: the most spread)")
    parser.add_argument("--follow", nargs="*", default=None, metavar="VILLAGER",
                        help="holders whose chains Figure 1 draws dark and quotes "
                             "(default: the one furthest from the event)")
    args = parser.parse_args()

    runs_dir = ROOT / "runs"
    path = (runs_dir / args.run_id) if args.run_id else max(
        (p for p in runs_dir.iterdir() if (p / "knowledge.json").exists()),
        key=lambda p: p.stat().st_mtime)
    run = Run(path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"figures from {path.name}")

    root = args.root or run.busiest_root()
    if root is None:
        print("  no knowledge in this run; nothing to draw")
        return 1
    fig_provenance(run, root, out / "fig1_provenance.png", args.follow)
    fig_spread(run, out / "fig2_spread.png")
    fig_usage(run, out / "fig3_usage.png")
    write_memories(run, root, out / "memories.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
