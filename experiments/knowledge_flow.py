#!/usr/bin/env python3
"""How news travels, and what happens to it on the way.

The quantitative backbone for the knowledge-flow case study, pooled across
seeds. Four things, each answering a question a reader will ask:

  reach      how much of the village ends up holding an event's news, and in
             how many tellings
  drift      how far the wording has moved from the first-hand account, as a
             function of how many tellings away from it the holder is. This is
             the one that needs the lens: a system that copied facts around
             would show a flat line at zero
  attrition  what happens to an offer -- already known, refused by the
             receiver's lens, or kept
  reclass    how often a listener files what it heard under a different kind
             than the witness did. This is the channel by which interpretation
             reaches behaviour: the context tag is knows_<kind>_<place>, so the
             kind a receiver assigns decides which instructions it can retrieve.
             Wording drift, by contrast, changes nothing it can do
  unlocked   decisions that were only reachable because somebody had learned
             something, which is knowledge becoming behaviour

    python experiments/knowledge_flow.py <run_id> [<run_id> ...]
    python experiments/knowledge_flow.py --latest 3

Writes results/knowledge_flow.{json,md} and fig6_drift.png.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hearthwick.config import ROOT, SimConfig  # noqa: E402
from hearthwick.corpus import make_embedder  # noqa: E402
from hearthwick.knowledge import EXPERIENCE_KINDS  # noqa: E402
from hearthwick.config import DATA_DIR  # noqa: E402


def _by_kind(reach: list[dict]) -> dict[str, list[dict]]:
    """Spreading events grouped by the kind of event their root names."""
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for row in reach:
        out[row["root"].split(":")[0]].append(row)
    return out


def knowledge_gated() -> set[str]:
    """Authored instructions that require knowing something (a ``knows_`` gate).

    Classified by the gate, not the name. Counting ids that start with
    ``knows-`` left out instructions such as the farmers' answer to the
    blight, which is gated on knowing of it but named for food.
    """
    from bear import Corpus
    return {i.id for i in Corpus.from_directory(DATA_DIR / "instructions")
            if any(t.startswith("knows_") for t in (i.scope.required_tags or ()))}


def cosine(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


def load(run_dir: Path) -> dict:
    events = [json.loads(line) for line
              in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    return {
        "name": run_dir.name,
        "events": events,
        "knowledge": json.loads((run_dir / "knowledge.json").read_text(encoding="utf-8")),
        "meta": json.loads((run_dir / "meta.json").read_text(encoding="utf-8")),
    }


def analyse(runs: list[dict], embedder) -> dict:
    villagers = max(len(set(r["knowledge"]) - {
        c["id"] for e in r["events"] if e["type"] == "roster"
        for c in e["characters"] if c.get("visitor")}) for r in runs)
    outcomes = collections.Counter()
    by_hop: dict[int, list[float]] = collections.defaultdict(list)
    reach: list[dict] = []
    unlocked = collections.Counter()
    gated = knowledge_gated()
    reclassified = collections.Counter()
    moves: collections.Counter = collections.Counter()
    decisions = 0
    kinds = collections.Counter()
    cache: dict[str, list[float]] = {}

    def vector(text: str):
        if embedder is None:
            return None
        if text not in cache:
            try:
                cache[text] = embedder.embed_single(text, is_query=False)
            except Exception:  # noqa: BLE001 - a missing vector is not a result
                return None
        return cache[text]

    by_vector: list[float] = []
    for run in runs:
        for event in run["events"]:
            if event["type"] == "diffusion":
                outcomes[event["outcome"]] += 1
                # The root check logs a similarity of exactly 1. Anything
                # else was caught by the embedder as the same news in other
                # words, from a different event.
                if event["outcome"] == "duplicate" and event.get("similarity") != 1.0:
                    by_vector.append(event["similarity"])
            elif event["type"] == "decision" and event["character"] != "world":
                decisions += 1
                chosen = event.get("chosen")
                if chosen in gated:
                    unlocked[chosen] += 1

        # News only. Stores also hold what a villager lived through (a
        # conversation it had), and those have their own root per memory, so
        # counting them makes every chat an "event" with one holder.
        facts = [f for holder in run["knowledge"].values() for f in holder
                 if f["kind"] not in EXPERIENCE_KINDS]
        for fact in facts:
            kinds[fact["kind"]] += 1

        # Group by the event each fact descends from. The first-hand wording is
        # the yardstick: everything else is measured against what the people
        # who were actually there said.
        trees: dict[str, list[dict]] = collections.defaultdict(list)
        for fact in facts:
            trees[fact["root"]].append(fact)

        # A visiting storyteller holds news too, but "held by N of M villagers"
        # counts the people who live here.
        visitors = {c["id"] for e in run["events"] if e["type"] == "roster"
                    for c in e["characters"] if c.get("visitor")}
        residents = set(run["knowledge"]) - visitors
        for root, tree in trees.items():
            source = [f for f in tree if f["hop"] == 0]
            if not source:
                continue
            # Only news that travelled. Weather is witnessed by everyone and
            # told by nobody, and once the world decided the sky every day it
            # was most of the events: counted here it made the median event
            # one wording, and put facts that cannot be refiled into the
            # reclassification denominator.
            if max(f["hop"] for f in tree) == 0:
                continue
            origin = vector(source[0]["text"])
            reach.append({
                "run": run["name"], "root": root,
                "holders": len({f["holder"] for f in tree} & residents),
                "villagers": len(residents),
                "visitor_holders": len({f["holder"] for f in tree} & visitors),
                "first_hand": len(source),
                "max_hop": max(f["hop"] for f in tree),
                "wordings": len({f["text"] for f in tree}),
            })
            # What the people who were there called it, against what each
            # holder ended up calling it.
            witnessed_kind = source[0]["kind"]
            for fact in tree:
                reclassified["total"] += 1
                if fact["kind"] != witnessed_kind:
                    reclassified["changed"] += 1
                    moves[(witnessed_kind, fact["kind"])] += 1

            if origin is None:
                continue
            for fact in tree:
                other = vector(fact["text"])
                if other is not None:
                    by_hop[fact["hop"]].append(1.0 - cosine(origin, other))

    total_offers = sum(outcomes.values())
    drift = [{"hop": hop,
              "n": len(by_hop[hop]),
              "median": round(float(statistics.median(by_hop[hop])), 4),
              "mean": round(float(statistics.fmean(by_hop[hop])), 4)}
             for hop in sorted(by_hop) if by_hop[hop]]

    return {
        "meta": {"runs": [r["name"] for r in runs], "villagers": villagers,
                 "date": datetime.now().strftime("%Y-%m-%d")},
        "reach": {
            "events_that_spread": len(reach),
            "median_holders": (round(statistics.median([r["holders"] for r in reach]), 1)
                               if reach else None),
            "median_share_pct": (round(100 * statistics.median(
                [r["holders"] / r["villagers"] for r in reach]), 1) if reach else None),
            "max_holders": max((r["holders"] for r in reach), default=0),
            "median_wordings": (round(statistics.median([r["wordings"] for r in reach]), 1)
                                if reach else None),
            "deepest_chain": max((r["max_hop"] for r in reach), default=0),
            "per_event": sorted(reach, key=lambda r: -r["holders"])[:12],
            # By the kind of event it grew from: the world's sickness spreads
            # differently from a storyteller's tale.
            "by_kind": {
                kind: {"events": len(rows),
                       "median_holders": statistics.median(r["holders"] for r in rows),
                       "fewest": min(r["holders"] for r in rows),
                       "most": max(r["holders"] for r in rows)}
                for kind, rows in sorted(_by_kind(reach).items())},
        },
        "drift": drift,
        "reclassified": {
            "facts": reclassified["total"],
            "changed": reclassified["changed"],
            "pct": (round(100 * reclassified["changed"] / reclassified["total"], 1)
                    if reclassified["total"] else None),
            "moves": {f"{a} -> {b}": n for (a, b), n in moves.most_common()},
            "toward_trouble_pct": (round(100 * sum(
                n for (a, b), n in moves.items() if b in ("hazard", "sickness"))
                / max(1, reclassified["changed"]), 1)),
        },
        "attrition": {
            "offers": total_offers,
            **{k: outcomes[k] for k in ("duplicate", "refused", "stored", "unchanged")},
            "already_known_pct": (round(100 * outcomes["duplicate"] / total_offers, 1)
                                  if total_offers else None),
            "refused_of_new_pct": (round(100 * outcomes["refused"]
                                         / max(1, total_offers - outcomes["duplicate"]), 1)),
            "duplicate_by_root": outcomes["duplicate"] - len(by_vector),
            "duplicate_by_vector": len(by_vector),
            "vector_similarity_range": ([round(min(by_vector), 3), round(max(by_vector), 3)]
                                        if by_vector else None),
        },
        "unlocked": {"decisions": decisions, "by_instruction": dict(unlocked.most_common()),
                     "total": sum(unlocked.values()),
                     "share_pct": round(100 * sum(unlocked.values()) / decisions, 2)
                     if decisions else None},
        "fact_kinds": dict(kinds),
    }


def draw(data: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURFACE, INK, INK_SOFT, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2dd"
    ACCENT = "#2a78d6"
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "font.size": 9,
                         "text.color": INK, "axes.labelcolor": INK_SOFT,
                         "axes.edgecolor": GRID, "xtick.color": INK_SOFT,
                         "ytick.color": INK_SOFT, "axes.spines.top": False,
                         "axes.spines.right": False})

    drift = data["drift"]
    if not drift:
        return
    hops = [d["hop"] for d in drift]
    medians = [d["median"] for d in drift]

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.plot(hops, medians, color=ACCENT, linewidth=2, marker="o", markersize=7,
            zorder=3)
    for d in drift:
        ax.annotate(f"n={d['n']}", (d["hop"], d["median"]),
                    textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=7.5, color=INK_SOFT)
    ax.set_xlabel("tellings from the person who was there")
    ax.set_ylabel("distance from the first-hand wording")
    ax.set_xticks(hops)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)

    height = fig.get_figheight()
    meta = data["meta"]
    fig.text(0.012, 1 - 0.30 / height, "News changes as it travels",
             fontsize=13.5, fontweight="bold", va="top", color=INK)
    fig.text(0.012, 1 - 0.62 / height,
             "each retelling is the receiver's own words, not a copy, so the "
             "version held drifts from the one witnessed",
             fontsize=8.8, va="top", color=INK)
    fig.text(0.012, 1 - 0.88 / height,
             f"{meta['villagers']} villagers, {len(meta['runs'])} runs; "
             "cosine distance from the first-hand account of the same event",
             fontsize=8, va="top", color=INK_SOFT)
    fig.subplots_adjust(top=1 - 1.20 / height, left=0.11, right=0.97, bottom=0.14)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")


def to_markdown(data: dict) -> str:
    r, a, u = data["reach"], data["attrition"], data["unlocked"]
    lines = [
        "# How news travels", "",
        f"{len(data['meta']['runs'])} runs, {data['meta']['villagers']} villagers, "
        f"{data['meta']['date']}. Generated by `experiments/knowledge_flow.py`.", "",
        "## Reach", "",
        f"- events that reached anyone: **{r['events_that_spread']}**",
        f"- villagers holding a given event's news, median: **{r['median_holders']}** "
        f"({r['median_share_pct']}% of the village), most: {r['max_holders']}",
        f"- distinct wordings of the same event, median: **{r['median_wordings']}**",
        f"- longest chain from the event: **{r['deepest_chain']}** tellings", "",
        "| event kind | events | villagers holding it, median | fewest | most |",
        "|---|---|---|---|---|",
        *[f"| {k} | {v['events']} | {v['median_holders']} | {v['fewest']} | {v['most']} |"
          for k, v in r["by_kind"].items()], "",
        "## Drift", "",
        "Distance from the first-hand wording, by how many tellings away the "
        "holder is. A system that copied facts would be flat at zero.", "",
        "| tellings | n | median distance | mean |", "|---|---|---|---|",
    ]
    for d in data["drift"]:
        lines.append(f"| {d['hop']} | {d['n']} | {d['median']} | {d['mean']} |")
    lines += [
        "", "## What it gets filed as", "",
        "A fact's context tag is `knows_<kind>_<place>`, so the kind a listener "
        "assigns is what decides which instructions it can retrieve. Wording "
        "drift changes nothing a villager can do; reclassification changes "
        "everything it can do.", "",
        f"- facts descended from a witnessed event: **{data['reclassified']['facts']}**",
        f"- filed under a different kind than the witness used: "
        f"**{data['reclassified']['changed']}** ({data['reclassified']['pct']}%)",
        f"- of those, moving toward hazard or sickness: "
        f"**{data['reclassified']['toward_trouble_pct']}%**", "",
        "| from - to | n |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in data["reclassified"]["moves"].items()],
        "", "## What happens to an offer", "",
        f"- offers made: **{a['offers']}**",
        f"- already known: {a['duplicate']} ({a['already_known_pct']}%)",
        f"- refused by the receiver's lens: {a['refused']} "
        f"({a['refused_of_new_pct']}% of what was new to them)",
        f"- kept: {a['stored']} reworded, {a['unchanged']} as heard", "",
        "## Knowledge becoming behaviour", "",
        "Instructions that no villager could retrieve until somebody learned "
        "something. They are not reachable at the start of a run.", "",
        f"- decisions taken: {u['decisions']}",
        f"- decisions only reachable through knowledge: **{u['total']}** "
        f"({u['share_pct']}%)", "",
        "| instruction | chosen |", "|---|---|",
    ]
    for name, count in u["by_instruction"].items():
        lines.append(f"| `{name}` | {count} |")
    lines += ["", "## The events that travelled furthest", "",
              "| event | holders | first-hand | tellings | wordings |", "|---|---|---|---|---|"]
    for row in r["per_event"]:
        lines.append(f"| `{row['root']}` | {row['holders']}/{row['villagers']} | "
                     f"{row['first_hand']} | {row['max_hop']} | {row['wordings']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="*")
    parser.add_argument("--latest", type=int, default=0)
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    if args.latest:
        dirs = [d for d in sorted((ROOT / "runs").iterdir(),
                                  key=lambda p: p.stat().st_mtime)
                if (d / "knowledge.json").exists()][-args.latest:]
    else:
        dirs = [ROOT / "runs" / name for name in args.runs]
    if not dirs:
        raise SystemExit("name some runs, or pass --latest N")

    embedder = make_embedder("service", SimConfig.embed_url)
    if embedder is None:
        print("note: no embedding service, so drift cannot be measured")
    data = analyse([load(d) for d in dirs], embedder)

    r, a, u = data["reach"], data["attrition"], data["unlocked"]
    print(f"runs: {', '.join(data['meta']['runs'])}\n")
    print(f"  events that spread     {r['events_that_spread']}")
    print(f"  median holders         {r['median_holders']} of {data['meta']['villagers']}"
          f"  ({r['median_share_pct']}%)")
    print(f"  median wordings        {r['median_wordings']}")
    print(f"  longest chain          {r['deepest_chain']} tellings")
    print(f"  offers                 {a['offers']}  "
          f"({a['already_known_pct']}% already known, "
          f"{a['refused_of_new_pct']}% of the rest refused)")
    print(f"  knowledge-only actions {u['total']} of {u['decisions']} ({u['share_pct']}%)")
    rc = data["reclassified"]
    print("  reclassified          "
          + str(rc["changed"]) + "/" + str(rc["facts"])
          + " (" + str(rc["pct"]) + "%), "
          + str(rc["toward_trouble_pct"]) + "% of those toward trouble")
    print("\n  drift by telling:")
    for d in data["drift"]:
        print(f"    hop {d['hop']}:  median {d['median']:.4f}  (n={d['n']})")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "knowledge_flow.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (out / "knowledge_flow.md").write_text(to_markdown(data), encoding="utf-8")
    draw(data, out / "figures" / "fig6_drift.png")
    print(f"\nwrote {out / 'knowledge_flow.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
