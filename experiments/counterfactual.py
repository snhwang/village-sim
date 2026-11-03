#!/usr/bin/env python3
"""Would a different villager, in this exact situation, have done something else?

Comparing conditions across runs cannot answer that. Change anything and the
village takes a different course, so the situations two conditions produce are
not the same situations, and the comparison sets do not match.

This is paired instead. Every decision in a run is replayed with one thing
changed: the deciding villager's temperament is swapped for another villager's,
holding the situation, the knowledge and the query text fixed. If the retrieved
choice changes, that difference is caused by the instructions and nothing else.

    python experiments/counterfactual.py <run_id> [<run_id> ...]
    python experiments/counterfactual.py <run_id> --donor first   # the paper's first version

The donor is drawn at random for each decision unless ``--donor first``, and
``--sample`` decisions are replayed from each run. Writes
results/counterfactual.{json,md}, with every replayed decision under "raw".
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bear import Context, parse_actions  # noqa: E402

from hearthwick.character import load_founders  # noqa: E402
from hearthwick.config import DATA_DIR, ROOT  # noqa: E402
from hearthwick.corpus import build_corpus, build_retriever, make_embedder  # noqa: E402

LOCI = ("sociability", "caution", "curiosity", "trust", "diligence", "candor")


def top_actionable(retriever, query: str, tags: list[str]) -> str | None:
    """What this context would choose on score alone, ignoring markers.

    Marker resolution depends on the rest of the world (whose house, whose
    parent), which is not what this measures, so the comparison stops at the
    best-scoring instruction that carries an action.
    """
    for scored in retriever.retrieve(query, Context(tags=sorted(tags)), top_k=12):
        if parse_actions(scored.content):
            return scored.id
    return None


def swap_temperament(tags: list[str], donor: dict[str, str], locus: str | None) -> list[str]:
    """The same tags with the donor's temperament (or one locus of it)."""
    if locus is None:
        kept = [t for t in tags if not t.startswith("temp_")]
        return kept + [f"temp_{allele}" for allele in donor.values()]
    return tags  # per-locus handled by the caller, which knows both sides


# What a condition is called on a figure. "Whole temperament" read as all six
# genes swapped at once. It is another villager's temperament, which shares
# some alleles with the listener's, so it changes some genes and not others.
SHOWN = {"whole temperament": "another villager's temperament"}

def draw(payload: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURFACE, INK, INK_SOFT, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2dd"
    ACCENT, NEUTRAL, PLACEBO = "#2a78d6", "#b9b7ae", "#eb6834"
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "font.size": 9,
                         "text.color": INK, "axes.labelcolor": INK_SOFT,
                         "axes.edgecolor": GRID, "xtick.color": INK_SOFT,
                         "ytick.color": INK_SOFT, "axes.spines.top": False,
                         "axes.spines.right": False})

    rows = payload["rows"]
    labels = [r["what"] for r in rows]
    values = [r["pct"] or 0 for r in rows]
    colors = [ACCENT if i == 0 else (PLACEBO if labels[i] == "candor" else NEUTRAL)
              for i in range(len(rows))]

    fig, ax = plt.subplots(figsize=(8.4, 4.3))
    ax.bar(range(len(rows)), values, color=colors, width=0.62)
    for i, (value, row) in enumerate(zip(values, rows)):
        ax.text(i, value + 0.8, f"{value:.0f}%", ha="center", fontsize=10, fontweight="bold")
    placebo = next((r["pct"] for r in rows if r["what"] == payload.get("placebo")), None)
    if placebo:
        ax.axhline(placebo, color=PLACEBO, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
        # A key line above the bars, as in the absorption figure. Set beside
        # the floor it ran into the labels of the bars standing near it.
        ax.text(0.01, 0.98, f"- - -  noise floor: candor has no action instructions "
                f"({placebo:.1f}%)", transform=ax.transAxes, color=PLACEBO, fontsize=8,
                ha="left", va="top")
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([SHOWN.get(l, l).replace(" ", chr(10)) for l in labels], fontsize=8.5)
    ax.set_ylabel("decisions that would have changed")
    ax.set_ylim(0, max(values) * 1.35)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)

    height = fig.get_figheight()
    meta = payload["meta"]
    fig.text(0.012, 1 - 0.30 / height, "Swap the temperament, hold the situation",
             fontsize=13.5, fontweight="bold", va="top", color=INK)
    fig.text(0.012, 1 - 0.64 / height,
             "how often a villager would have done something else with another villager's instructions",
             fontsize=8.8, va="top", color=INK)
    fig.text(0.012, 1 - 0.90 / height,
             f"{meta['decisions_replayed']} decisions replayed, {meta['villagers']} villagers, "
             f"situation, knowledge and query text held fixed",
             fontsize=8, va="top", color=INK_SOFT)
    fig.subplots_adjust(top=1 - 1.25 / height, left=0.10, right=0.97, bottom=0.17)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--village", default=None)
    parser.add_argument("--sample", type=int, default=400,
                        help="decisions to replay from each run (0 = all)")
    parser.add_argument("--seed", type=int, default=0)
    # The paper's first version took the first villager in the roster whose
    # temperament differed, which was the same villager for every decision
    # but its own. A donor drawn at random for each decision measures
    # temperament in general rather than one villager's.
    parser.add_argument("--donor", choices=("random", "first"), default="random")
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    changed = collections.Counter()
    total = collections.Counter()
    examples = []
    raw = []
    replayed = {}
    residents = 0
    embedder = None

    for run_id in args.run_ids:
        run_dir = ROOT / "runs" / run_id
        events = [json.loads(l) for l in
                  (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        roster = {c["id"]: c for e in events if e["type"] == "roster"
                  for c in e["characters"]}
        residents = max(residents, sum(1 for c in roster.values() if not c.get("visitor")))
        decisions = [e for e in events
                     if e["type"] == "decision" and e["character"] != "world"]

        village = args.village or (meta.get("village")
                                   if meta.get("village") != "hearthwick" else None)
        base = (DATA_DIR / "villages" / village) if village else None
        founders = load_founders((base / "founders.yaml") if base
                                 else DATA_DIR / "characters" / "founders.yaml")
        # The run's own switches decide which instruction directories it
        # loaded, so the replay loads the same (hearthwick.corpus).
        corpus = build_corpus(DATA_DIR, founders,
                              switches=SimpleNamespace(**meta["config"]))
        if embedder is None:
            embedder = make_embedder(meta["config"]["embedder"], meta["config"]["embed_url"])
        # A run recorded before BEAR's threshold fix was retrieved with what
        # the threshold set aside put back, so it is replayed that way
        # (SimConfig).
        retriever = build_retriever(corpus, embedder, meta["config"]["retrieval_threshold"],
                                    meta["config"].get("restore_below_threshold", True))

        if args.sample and len(decisions) > args.sample:
            decisions = rng.sample(decisions, args.sample)
        replayed[run_id] = len(decisions)

        for decision in decisions:
            actor = roster[decision["character"]]
            tags, query = decision["tags"], decision["query"]
            baseline = top_actionable(retriever, query, tags)
            if baseline is None:
                continue
            record = {"run": run_id, "t": decision["t"], "actor": actor["id"],
                      "chose": baseline}

            # Another villager's whole temperament, one donor per decision.
            donors = [d for d_id, d in roster.items()
                      if d_id != actor["id"] and not d.get("visitor")
                      and d["temperament"] != actor["temperament"]]
            if donors:
                donor = rng.choice(donors) if args.donor == "random" else donors[0]
                swapped = swap_temperament(tags, donor["temperament"], None)
                choice = top_actionable(retriever, query, swapped)
                total["whole temperament"] += 1
                record.update(donor=donor["id"], would_have=choice)
                if choice != baseline:
                    changed["whole temperament"] += 1
                    if len(examples) < 8:
                        examples.append({
                            "situation": [t for t in tags
                                          if t.startswith(("time_", "at_", "near_"))],
                            "actor": actor["name"], "chose": baseline,
                            "donor": donor["name"], "would_have": choice,
                        })

            # One gene at a time: which trait actually moves a decision?
            record["genes_changed"] = []
            for locus in LOCI:
                mine = actor["temperament"][locus]
                other = next((a for a in sorted({r["temperament"][locus]
                                                 for r in roster.values()})
                              if a != mine), None)
                if other is None:
                    continue
                swapped = [t for t in tags if t != f"temp_{mine}"] + [f"temp_{other}"]
                total[locus] += 1
                if top_actionable(retriever, query, swapped) != baseline:
                    changed[locus] += 1
                    record["genes_changed"].append(locus)
            raw.append(record)

    rows = [("whole temperament", changed["whole temperament"], total["whole temperament"])]
    rows += [(locus, changed[locus], total[locus]) for locus in LOCI]

    print(f"replayed {sum(replayed.values())} decisions from {len(replayed)} run(s)\n")
    for name, n, d in rows:
        pct = 100 * n / d if d else 0
        print(f"  {name:20} {n:5}/{d:<5} {pct:5.1f}% of decisions would have changed")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {"run": args.run_ids[0] if len(args.run_ids) == 1 else None,
                 "runs": args.run_ids, "village": meta.get("village"),
                 "villagers": residents, "decisions_replayed": sum(replayed.values()),
                 "per_run": replayed, "donor": args.donor, "seed": args.seed,
                 "date": datetime.now().strftime("%Y-%m-%d")},
        "rows": [{"what": n, "changed": c, "compared": d,
                  "pct": round(100 * c / d, 1) if d else None} for n, c, d in rows],
        "examples": examples,
        # One entry per replayed decision, so the analysis can be redone, for
        # example with intervals that allow for clustering by villager.
        "raw": raw,
    }
    payload["placebo"] = "candor"
    (out / "counterfactual.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    draw(payload, out / "figures" / "fig4_counterfactual.png")

    lines = ["# Counterfactual: swap the temperament, hold the situation", "",
             f"Runs {', '.join(f'`{r}`' for r in args.run_ids)}, {residents} villagers, "
             f"{sum(replayed.values())} decisions replayed, donor {args.donor}, "
             f"{payload['meta']['date']}.", "",
             "Each decision is replayed with the deciding villager's temperament "
             "replaced by another villager's, holding the situation, the knowledge "
             "and the query text fixed. A change is caused by the instructions and "
             "nothing else.", "",
             "**Candor is the placebo.** Its two alleles carry only speech "
             "instructions and no action markers, so swapping it should change "
             "nothing; what it does change is the noise floor from altering the "
             "tag text the query is embedded with. Read the other loci against "
             "it.", "",
             "| Swapped | Decisions changed |", "|---|---|"]
    for name, n, d in rows:
        lines.append(f"| {name} | {n}/{d} ({100 * n / d:.1f}%) |" if d else f"| {name} | — |")
    if examples:
        lines += ["", "## Examples", ""]
        for ex in examples[:5]:
            where = ", ".join(ex["situation"][:3])
            lines.append(f"- [{where}] **{ex['actor']}** chose `{ex['chose']}`; with "
                         f"**{ex['donor']}**'s temperament it would have been "
                         f"`{ex['would_have']}`")
    (out / "counterfactual.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out / 'counterfactual.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
