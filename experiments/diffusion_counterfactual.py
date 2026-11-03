#!/usr/bin/env python3
"""Would another villager, hearing the same thing, have kept it?

The action counterfactual (experiments/counterfactual.py) asks whether
temperament changes what a villager *does*. This asks the other half: whether
temperament changes what a villager *keeps and passes on*, which is the only
way individual difference can reach the knowledge itself.

It is the same paired design applied to the lens. Every reframing the
simulation actually performed is replayed with one thing changed: the absorbing
instructions are rebuilt from another villager's temperament, holding the
speaker, the sentence heard, what the receiver already knew, its name, stage
and role fixed. The model is called at temperature 0 with one seed per pair, so
the original and the counterfactual differ in their prompt and nothing else.

Three things are measured, because the first two mislead on their own:

1. How often the keep/discard decision flips when the temperament is swapped.
2. The same, restricted to the pairs where the swap really did hand the
   villager a different filter. A swap that retrieved the same instructions
   cannot have caused anything, and how often that happens varies by an order
   of magnitude between loci (trust 86%, sociability 5%), so the unrestricted
   rate mostly measures the retrieval, not the trait.
3. The identical prompt, called twice. vLLM batches continuously and is not
   bitwise deterministic even at temperature 0, so the floor is a measured
   quantity rather than zero.

Sociability and diligence carry no absorbing instruction on either allele, so
they were expected to be inert. They are not: changing a tag changes the text
the lens query is embedded with, which reorders the role instructions and moves
the top-k cut. That is why (2) and (3) exist.

    python experiments/diffusion_counterfactual.py <run_id> [<run_id> ...]
    python experiments/diffusion_counterfactual.py <run_id> --sample 150

Writes results/diffusion_counterfactual.{json,md} and fig5_lens.png.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import random
import math
import statistics
import sys
import zlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hearthwick.character import LOCI, load_founders  # noqa: E402
from hearthwick.config import DATA_DIR, ROOT, SimConfig  # noqa: E402
from hearthwick.conversation import describe  # noqa: E402
from hearthwick.corpus import build_corpus, build_retriever, make_embedder  # noqa: E402
from hearthwick.diffusion import (  # noqa: E402
    REFRAME_SYSTEM,
    REFRAME_USER,
    _parse,
    compose_lens,
)
from hearthwick.llm import SpeechModel  # noqa: E402

# Loci with no absorbing instruction on either allele. Swapping one adds and
# removes no filter of its own -- but it still changes the tag text the query
# carries, which can reorder the role instructions around it, so these are a
# weak control and not a true null. Checked against the corpus, not assumed.
NO_LENS_LOCI = ("sociability", "diligence")

# The true null: the same prompt, asked twice.
NULL = "same prompt"


def lens_events(run_dir: Path) -> tuple[list[dict], dict, dict]:
    """The reframings a run performed, with the roster and config it used."""
    events = [json.loads(line) for line
              in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    # Every roster line: a visitor adds itself when it arrives.
    roster = {c["id"]: c for e in events if e["type"] == "roster" for c in e["characters"]}
    replayable = [e for e in events if e["type"] == "lens" and e.get("parsed")
                  and e.get("heard") and "tags" in e]
    return replayable, roster, meta


def audit_placebos(retriever, roster: dict) -> dict:
    """Which alleles actually carry a lens, read out of the corpus."""
    absorbing: dict[str, str] = {}
    for instruction in retriever.corpus.instructions:
        required = set(instruction.scope.required_tags or ())
        if "absorbing" not in required:
            continue
        for tag in required:
            if tag.startswith("temp_"):
                absorbing.setdefault(tag[len("temp_"):], instruction.id)
    by_locus: dict[str, list[str]] = collections.defaultdict(list)
    for character in roster.values():
        for locus, allele in character["temperament"].items():
            if allele not in by_locus[locus]:
                by_locus[locus].append(allele)
    return {locus: {allele: absorbing.get(allele) for allele in sorted(alleles)}
            for locus, alleles in sorted(by_locus.items())}


def swapped_tags(tags: list[str], mine: str, theirs: str) -> list[str]:
    return sorted([t for t in tags if t != "temp_" + mine] + ["temp_" + theirs])


def whole_swap(tags: list[str], donor: dict[str, str]) -> list[str]:
    kept = [t for t in tags if not t.startswith("temp_")]
    return sorted(kept + ["temp_" + allele for allele in donor.values()])


def build_prompt(retriever, event: dict, character: dict,
                 tags: list[str]) -> tuple[str, str]:
    """The reframing call the simulation makes, with this lens in place of its own."""
    lens, _ = compose_lens(retriever, character["name"], tags)
    who = SimpleNamespace(stage=character["stage"], role=character["role"])
    system = REFRAME_SYSTEM.format(name=character["name"], description=describe(who),
                                   lens=lens or "- nothing in particular")
    user = REFRAME_USER.format(teller=event["teller"], text=event["heard"],
                               known=event["known"] or "- nothing yet")
    return system, user


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided p for a 2x2 table, without pulling in scipy.

    Rows are (flipped, not flipped) for the condition and for the floor. The
    question is only ever "is this condition above the floor", so the tail is
    one-sided and the p-values are not corrected for the six loci: they are
    there to stop a number near the floor being read as an effect, not to
    carry a claim on their own.
    """
    n = a + b + c + d

    def table_p(x: int) -> float:
        return (math.comb(a + b, x) * math.comb(c + d, a + c - x)
                / math.comb(n, a + c))

    lo = max(0, a + c - (c + d))
    hi = min(a + b, a + c)
    return sum(table_p(x) for x in range(a, hi + 1)) if lo <= a <= hi else 1.0


def cosine(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


async def run(args) -> dict:
    all_events: list[dict] = []
    roster: dict = {}
    meta: dict | None = None
    for run_id in args.runs:
        events, run_roster, run_meta = lens_events(ROOT / "runs" / run_id)
        for event in events:
            event["run"] = run_id
        all_events += events
        roster.update(run_roster)
        meta = meta or run_meta
    if not all_events:
        raise SystemExit("no replayable lens events in those runs "
                         "(was the speech model up?)")

    config = meta["config"]
    village = meta.get("village") if meta.get("village") != "hearthwick" else None
    base = (DATA_DIR / "villages" / village) if village else None
    founders = load_founders((base / "founders.yaml") if base
                             else DATA_DIR / "characters" / "founders.yaml")
    corpus = build_corpus(DATA_DIR, founders, switches=SimpleNamespace(**config))
    embedder = make_embedder(config["embedder"], config["embed_url"])
    retriever = build_retriever(corpus, embedder, config["retrieval_threshold"],
                                config.get("restore_below_threshold", True))

    placebo_audit = audit_placebos(retriever, roster)
    for locus in NO_LENS_LOCI:
        live = {a: i for a, i in placebo_audit.get(locus, {}).items() if i}
        if live:
            raise SystemExit(locus + " is not a placebo any more: " + repr(live)
                             + ". Pick a different locus or drop the claim.")

    rng = random.Random(args.seed)
    if args.sample and len(all_events) > args.sample:
        all_events = rng.sample(all_events, args.sample)

    speech = SpeechModel(config["llm_base_url"] or args.llm, config["llm_model"],
                         concurrency=args.concurrency, max_tokens=160,
                         temperature=0.0, api_key=config.get("llm_api_key"))
    if not await speech.connect():
        raise SystemExit("speech model unavailable; this measurement needs it")
    print("replaying " + str(len(all_events)) + " reframings through "
          + str(speech.model) + " at temperature 0")

    # One call per (event, condition). The original is replayed too, so the
    # baseline comes from the same decoder settings as the counterfactual and
    # not from the logged run, which sampled at temperature 0.8.
    jobs: list[tuple[int, str, list[str]]] = []
    tags_for: dict[tuple[int, str], list[str]] = {}
    for index, event in enumerate(all_events):
        actor = roster[event["character"]]
        tags = event["tags"]
        jobs.append((index, "as heard", tags))
        jobs.append((index, "same prompt", tags))

        donor = next((c for cid, c in sorted(roster.items())
                      if cid != actor["id"]
                      and c["temperament"] != actor["temperament"]), None)
        if donor is not None:
            jobs.append((index, "whole temperament", whole_swap(tags, donor["temperament"])))

        for locus in LOCI:
            mine = actor["temperament"][locus]
            other = next((a for a in sorted({c["temperament"][locus]
                                             for c in roster.values()}) if a != mine), None)
            if other is not None:
                jobs.append((index, locus, swapped_tags(tags, mine, other)))

    for index, label, tags in jobs:
        tags_for[(index, label)] = tags

    async def one(index: int, label: str, tags: list[str]):
        event = all_events[index]
        system, user = build_prompt(retriever, event, roster[event["character"]], tags)
        seed = zlib.crc32((str(args.seed) + ":" + str(event["fact"]) + ":"
                           + str(event["character"])).encode())
        return index, label, _parse(await speech.say(system, user, seed))

    done = 0
    results: dict[tuple[int, str], tuple] = {}
    for start in range(0, len(jobs), args.chunk):
        batch = jobs[start:start + args.chunk]
        for index, label, parsed in await asyncio.gather(*(one(*j) for j in batch)):
            if parsed is not None:
                results[(index, label)] = parsed
        done += len(batch)
        print("  " + str(done) + "/" + str(len(jobs)) + " calls", flush=True)

    # Score each condition against the replayed original of the same event.
    flips: collections.Counter = collections.Counter()
    compared: collections.Counter = collections.Counter()
    kept_rate: collections.Counter = collections.Counter()
    divergence: dict[str, list[float]] = collections.defaultdict(list)
    examples: list[dict] = []
    labels = ["same prompt", "whole temperament", *LOCI]
    vectors: dict[str, list[float]] = {}

    def vector(text: str):
        if embedder is None:
            return None
        if text not in vectors:
            try:
                vectors[text] = embedder.embed_single(text, is_query=False)
            except Exception:  # noqa: BLE001 - a missing vector is not a result
                return None
        return vectors[text]

    lens_moved: collections.Counter = collections.Counter()
    moved_by: dict[tuple[int, str], bool] = {}
    moved_compared: collections.Counter = collections.Counter()
    moved_flips: collections.Counter = collections.Counter()

    for index, event in enumerate(all_events):
        base_parsed = results.get((index, "as heard"))
        if base_parsed is None:
            continue
        base_keep, base_text, _ = base_parsed
        name = roster[event["character"]]["name"]
        _, base_lens = compose_lens(retriever, name, event["tags"])
        for label in labels:
            other = results.get((index, label))
            if other is None:
                continue
            keep, text, _ = other
            compared[label] += 1
            kept_rate[label] += int(keep)
            _, other_lens = compose_lens(retriever, name, tags_for[(index, label)])
            moved = set(other_lens) != set(base_lens)
            moved_by[(index, label)] = moved
            lens_moved[label] += int(moved)
            if moved:
                moved_compared[label] += 1
            if keep != base_keep:
                flips[label] += 1
                if moved:
                    moved_flips[label] += 1
                if label == "whole temperament" and len(examples) < 8:
                    examples.append({
                        "heard": event["heard"],
                        "receiver": roster[event["character"]]["name"],
                        "kept_as_self": base_keep, "kept_as_other": keep,
                    })
            elif keep and base_keep:
                va, vb = vector(base_text), vector(text)
                if va is not None and vb is not None:
                    divergence[label].append(1.0 - cosine(va, vb))

    # Two floors, because they answer different questions. The decoder floor is
    # the same prompt asked twice: how much of a flip is the model rather than
    # the lens. The inert-tag floor is the loci that carry no lens of their own:
    # how much of a flip is any tag swap perturbing retrieval. A claim about a
    # trait has to clear the second, which is much the higher of the two.
    floor_flips, floor_n = flips[NULL], compared[NULL]
    inert_flips = sum(flips[l] for l in NO_LENS_LOCI)
    inert_n = sum(compared[l] for l in NO_LENS_LOCI)
    rows = []
    for label in labels:
        n = compared[label]
        spread = divergence[label]
        rows.append({
            "what": label,
            "flipped": flips[label], "compared": n,
            "pct": round(100 * flips[label] / n, 1) if n else None,
            "kept_pct": round(100 * kept_rate[label] / n, 1) if n else None,
            "divergence": round(float(statistics.median(spread)), 3) if spread else None,
            "rewrites": len(spread),
            "lens_moved": lens_moved[label],
            "moved_compared": moved_compared[label],
            "moved_flipped": moved_flips[label],
            "pct_when_moved": (round(100 * moved_flips[label] / moved_compared[label], 1)
                               if moved_compared[label] else None),
            "no_lens": label in NO_LENS_LOCI,
            "null": label == NULL,
            "p_vs_floor": (None if label == NULL or not n or not floor_n else
                           round(fisher_exact_greater(flips[label], n - flips[label],
                                                      floor_flips, floor_n - floor_flips), 4)),
            # scoring a no-lens locus against a floor it helps define is
            # circular, so those rows get no p against the inert floor
            "p_vs_inert": (None if label == NULL or label in NO_LENS_LOCI or not n
                           or not inert_n else
                           round(fisher_exact_greater(flips[label], n - flips[label],
                                                      inert_flips,
                                                      inert_n - inert_flips), 4)),
        })

    return {
        "meta": {"runs": list(args.runs), "village": meta.get("village"),
                 "villagers": sum(1 for c in roster.values() if not c.get("visitor")), "reframings_replayed": len(all_events),
                 "model": speech.model, "calls": speech.calls,
                 "failures": speech.failures, "errors": speech.errors,
                 "date": datetime.now().strftime("%Y-%m-%d")},
        "no_lens_loci": list(NO_LENS_LOCI),
        "null_condition": NULL,
        "floors": {"decoder": {"flipped": floor_flips, "compared": floor_n,
                               "pct": round(100 * floor_flips / floor_n, 1)
                               if floor_n else None},
                   "inert_tag": {"flipped": inert_flips, "compared": inert_n,
                                 "pct": round(100 * inert_flips / inert_n, 1)
                                 if inert_n else None}},
        "raw": [{"event": i, "condition": c, "kept": results[(i, c)][0],
                 "text": results[(i, c)][1],
                 "lens_moved": bool(moved_by.get((i, c)))}
                for (i, c) in sorted(results, key=lambda k: (k[0], k[1]))],
        "placebo_audit": placebo_audit,
        "rows": rows,
        "examples": examples,
    }


# What a condition is called on a figure. "Whole temperament" read as all six
# genes swapped at once. It is another villager's temperament, which shares
# some alleles with the listener's, so it changes some genes and not others.
SHOWN = {"whole temperament": "another villager's temperament"}

def draw(payload: dict, out: Path) -> None:
    """Two panels: what changed, and why it changed.

    The flip rate on its own invites the wrong reading, because a locus can
    look inert only because its instructions were never retrieved. The lower
    panel is the mechanism, and the two panels share an x order so a reader can
    run their eye down one column.
    """
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

    rows = [r for r in payload["rows"] if r["pct"] is not None]
    labels = [r["what"] for r in rows]
    values = [r["pct"] for r in rows]
    moved = [round(100 * r["lens_moved"] / r["compared"], 1) if r["compared"] else 0
             for r in rows]
    clears = [r.get("p_vs_inert") is not None and r["p_vs_inert"] < 0.05 for r in rows]
    colors = [ACCENT if c else NEUTRAL for c in clears]

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(8.6, 6.4), sharex=True,
        gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.18})

    floors = payload.get("floors", {})
    decoder = (floors.get("decoder") or {}).get("pct")
    inert = (floors.get("inert_tag") or {}).get("pct")
    headroom = max(values + [inert or 0]) * 1.55

    top.bar(range(len(rows)), values, color=colors, width=0.62)
    for i, value in enumerate(values):
        top.text(i, value + headroom * 0.02, str(round(value)) + "%", ha="center",
                 fontsize=10, fontweight="bold")
    # The two reference lines are annotated in the empty upper-left rather than
    # against the lines themselves, which collide with the right-hand bars.
    note_y = 0.97
    if inert:
        top.axhline(inert, color=PLACEBO, linewidth=1.3, linestyle=(0, (4, 3)), zorder=1)
        top.text(0.012, note_y,
                 "- - -  floor: swapping a trait that carries no lens of its own ("
                 + str(inert) + "%)",
                 transform=top.transAxes, color=PLACEBO, fontsize=8,
                 ha="left", va="top")
        note_y -= 0.065
    if decoder:
        top.axhline(decoder, color=INK_SOFT, linewidth=1.0, linestyle=(0, (2, 3)), zorder=1)
        top.text(0.012, note_y,
                 ".......  the same prompt, asked twice (" + str(decoder) + "%)",
                 transform=top.transAxes, color=INK_SOFT, fontsize=7.5,
                 ha="left", va="top")
    top.set_ylabel("keep/discard decisions that flipped")
    top.set_ylim(0, headroom)
    top.grid(axis="y", color=GRID, linewidth=0.8)
    top.set_axisbelow(True)

    bottom.bar(range(len(rows)), moved, color=colors, width=0.62)
    for i, value in enumerate(moved):
        bottom.text(i, value + max(moved) * 0.03, str(round(value)) + "%",
                    ha="center", fontsize=9)
    bottom.set_ylabel("swaps that changed the lens")
    bottom.set_ylim(0, max(moved) * 1.30 if max(moved) else 1)
    bottom.grid(axis="y", color=GRID, linewidth=0.8)
    bottom.set_axisbelow(True)
    bottom.set_xticks(range(len(rows)))
    bottom.set_xticklabels([SHOWN.get(l, l).replace(" ", chr(10)) for l in labels], fontsize=8.5)

    height = fig.get_figheight()
    meta = payload["meta"]
    fig.text(0.012, 1 - 0.30 / height, "Swap the lens, hold what was heard",
             fontsize=14, fontweight="bold", va="top", color=INK)
    fig.text(0.012, 1 - 0.62 / height,
             "a trait changes what a villager keeps only as far as its instructions "
             "are retrieved; blue clears the floor",
             fontsize=9, va="top", color=INK)
    fig.text(0.012, 1 - 0.88 / height,
             str(meta["reframings_replayed"]) + " reframings replayed at temperature 0, "
             + str(meta["villagers"]) + " villagers; teller, sentence and prior "
             "knowledge held fixed",
             fontsize=8, va="top", color=INK_SOFT)
    fig.subplots_adjust(top=1 - 1.20 / height, left=0.10, right=0.975, bottom=0.11)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("  wrote " + str(out))


def to_markdown(payload: dict) -> str:
    meta = payload["meta"]
    runs = ", ".join("`" + r + "`" for r in meta["runs"])
    lines = [
        "# Counterfactual: swap the lens, hold what was heard", "",
        "Runs " + runs + ", " + str(meta["villagers"]) + " villagers, "
        + str(meta["reframings_replayed"]) + " reframings replayed, "
        + str(meta["model"]) + " at temperature 0, " + meta["date"] + ".", "",
        "Every reframing the simulation performed is replayed with the receiver's "
        "absorbing instructions rebuilt from another villager's temperament. The "
        "speaker, the sentence heard, what the receiver already knew, and its name, "
        "stage and role are held fixed, and the original is replayed under the same "
        "decoder settings, so the pair differs in its lens and nothing else.", "",
        "**There are two floors, and a claim about a trait has to clear the "
        "higher one.**", "",
        "The *decoder floor* is `" + payload["null_condition"] + "`: the identical "
        "prompt, asked twice. vLLM batches continuously and is not bitwise "
        "deterministic even at temperature 0, so some flips are the model rather "
        "than the lens. It is low — around 1% — which is the good news.", "",
        "The *inert-tag floor* is the loci that carry no lens of their own, pooled. "
        "Swapping one adds no filter, but it still changes the tag text the lens "
        "query is embedded with, which reorders the role instructions around it. "
        "At this sample size every locus clears the decoder floor, including those "
        "two, so the decoder floor cannot separate a trait that matters from a tag "
        "that merely jostles retrieval. The inert-tag floor can.", "",
        "**" + " and ".join(payload["no_lens_loci"]) + " carry no absorbing "
        "instruction on either allele** and were expected to be inert controls. "
        "They are not, which is worth more than the result they were meant to "
        "support: changing any tag changes the text the lens query is embedded "
        "with, reordering the role instructions around it. The `lens moved` "
        "column is how often a swap actually handed the villager different "
        "instructions, and the last column restricts the flip rate to those "
        "pairs. A swap that retrieved the same lens cannot have caused "
        "anything.", "",
        "| Swapped | Keep/discard flipped | vs decoder floor | vs inert-tag floor | Lens moved | Flipped when it moved |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        if row["pct"] is None:
            continue
        name = row["what"]
        if row["null"]:
            name = "**" + name + " (floor)**"
        elif row["no_lens"]:
            name = "*" + name + " (no lens of its own)*"
        moved = (str(row["lens_moved"]) + "/" + str(row["compared"]) + " ("
                 + str(round(100 * row["lens_moved"] / row["compared"])) + "%)"
                 ) if row["compared"] else "—"
        cond = ("—" if row["pct_when_moved"] is None else
                str(row["moved_flipped"]) + "/" + str(row["moved_compared"])
                + " (" + str(row["pct_when_moved"]) + "%)")
        def fmt(value):
            if value is None:
                return "—"
            return ("**p=" + format(value, ".4f") + "**" if value < 0.05
                    else "p=" + format(value, ".3f"))
        lines.append("| " + name + " | " + str(row["flipped"]) + "/"
                     + str(row["compared"]) + " (" + str(row["pct"]) + "%) | "
                     + fmt(row["p_vs_floor"]) + " | " + fmt(row["p_vs_inert"])
                     + " | " + moved + " | " + cond + " |")
    if payload["examples"]:
        lines += ["", "## Examples", ""]
        for ex in payload["examples"][:5]:
            verb = "kept" if ex["kept_as_self"] else "discarded"
            other = "kept" if ex["kept_as_other"] else "discarded"
            lines.append("- **" + ex["receiver"] + "** " + verb + ' "' + ex["heard"]
                         + '"; with another villager\'s temperament it would have '
                         "been " + other)
    lines += ["", "## Which alleles carry a lens at all", "",
              "| Locus | Allele | Absorbing instruction |", "|---|---|---|"]
    for locus, alleles in payload["placebo_audit"].items():
        for allele, instruction in alleles.items():
            lines.append("| " + locus + " | " + allele + " | "
                         + (instruction or "—") + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--sample", type=int, default=150,
                        help="reframings to replay (0 = all)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--chunk", type=int, default=64,
                        help="calls in flight before the next progress line")
    parser.add_argument("--llm", default=SimConfig.llm_base_url)
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    payload = asyncio.run(run(args))

    print()
    for row in payload["rows"]:
        if row["pct"] is None:
            continue
        mark = " (floor)" if row["null"] else (" (no lens)" if row["no_lens"] else "")
        cond = ("     -" if row["pct_when_moved"] is None
                else format(row["pct_when_moved"], "5.1f") + "%")
        p = ("" if row["p_vs_floor"] is None else
             ("  p=" + format(row["p_vs_floor"], ".4f")
              + ("  *" if row["p_vs_floor"] < 0.05 else "")))
        print("  " + (row["what"] + mark).ljust(26) + str(row["flipped"]).rjust(4)
              + "/" + str(row["compared"]).ljust(4) + " "
              + format(row["pct"], "5.1f") + "% flipped | lens moved "
              + format(100 * row["lens_moved"] / row["compared"], "5.1f")
              + "% | flipped when it moved " + cond + p)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diffusion_counterfactual.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    (out / "diffusion_counterfactual.md").write_text(to_markdown(payload), encoding="utf-8")
    draw(payload, out / "figures" / "fig5_lens.png")
    print("\nwrote " + str(out / "diffusion_counterfactual.json") + " and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
