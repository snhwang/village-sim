#!/usr/bin/env python3
"""Can the world do more than one thing, and can it say more than one thing?

Two different questions, and the second is the one that limits what can be
measured about knowledge.

A world that decides reasonably every single day can still be degenerate in its
marginal distribution -- a traveler arriving is not a bug on any given day, and
six travelers in nine events is only visible if you count. This reports:

  repertoire   which events fire, how concentrated, how many instructions are
               ever chosen, and whether different seeds diverge at all
  vocabulary   how many distinct first-hand sentences the world can produce,
               which caps the effective sample size of every measurement of
               what villagers keep, however many villagers or seeds are run

    python experiments/world_balance.py <run_id> [<run_id> ...]
    python experiments/world_balance.py --latest 6

Writes results/world_balance.{json,md}.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bear import Corpus, parse_actions  # noqa: E402

from hearthwick.config import DATA_DIR, ROOT  # noqa: E402
from hearthwick.knowledge import EXPERIENCE_KINDS  # noqa: E402


def effective(counts) -> float:
    """Inverse Simpson: how many stimuli this would be if they were even.

    A nominal 400 observations drawn 58% from one sentence is not 400
    independent trials, and reporting it as such overstates every p-value
    computed from it.
    """
    total = sum(counts)
    if not total:
        return 0.0
    return 1.0 / sum((c / total) ** 2 for c in counts)


def read(run_dir: Path) -> dict:
    events = [json.loads(line) for line
              in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    return {"name": run_dir.name, "events": events}


def analyse(runs: list[dict]) -> dict:
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    world_ids = {i.id for i in corpus.instructions
                 if "world" in (i.scope.required_tags or [])
                 and parse_actions(i.content)}

    kinds = collections.Counter()
    chosen = collections.Counter()
    retrieved = collections.Counter()
    sentences = collections.Counter()
    stimuli = collections.Counter()      # (run, root): one telling-tree each
    # (run, root) of what a listener actually reframed. This, not the world's
    # vocabulary, bounds the absorption counterfactual, because village-wide
    # weather is never told and so never reaches a lens.
    reframed = collections.Counter()
    sequences = set()
    decisions = quiet = 0

    per_run = []
    for run in runs:
        root_of = {}
        seq = [e["event"] for e in run["events"] if e["type"] == "world_event"]
        kinds.update(seq)
        sequences.add(tuple(seq))
        for event in run["events"]:
            if event["type"] == "decision" and event["character"] == "world":
                # A quiet sky is ordinary. A quiet day is one where nothing
                # happened. Runs from before the split have neither tag.
                if "sky" not in event.get("tags", []):
                    decisions += 1
                    quiet += event["chosen"] is None
                if event["chosen"]:
                    chosen[event["chosen"]] += 1
                retrieved.update(r["id"] for r in event["retrieved"])
            elif event["type"] == "knowledge_stored":
                if event.get("kind") in EXPERIENCE_KINDS:
                    continue    # a memory of a conversation is not news
                # The vocabulary is what the world says, so only first-hand
                # accounts count. Counting every stored sentence mixed in the
                # retellings ("Ilsa says the harvest...") and reported 174
                # "first-hand" sentences for a world that has a few dozen.
                if event.get("hop") == 0:
                    sentences[event["text"]] += 1
                stimuli[(run["name"], event["root"])] += 1
                root_of[event["id"]] = event["root"]
            elif event["type"] == "lens":
                reframed[(run["name"], root_of.get(event["fact"]))] += 1
        per_run.append({"run": run["name"],
                        "events": dict(collections.Counter(seq))})

    total = sum(kinds.values())
    happenings = collections.Counter({k: n for k, n in kinds.items() if k != "weather"})
    return {
        "meta": {"runs": [r["name"] for r in runs],
                 "date": datetime.now().strftime("%Y-%m-%d")},
        "repertoire": {
            "events": dict(kinds),
            "total": total,
            "top_share_pct": round(100 * kinds.most_common(1)[0][1] / total, 1) if total else None,
            # Weather has its own decision each day, so it is most of every
            # run by construction. The repertoire question is about the rest.
            "top_happening_share_pct": (
                round(100 * happenings.most_common(1)[0][1] / sum(happenings.values()), 1)
                if happenings else None),
            "happenings": sum(happenings.values()),
            "effective_event_kinds": round(effective(kinds.values()), 2),
            "distinct_sequences": len(sequences),
            "seeds": len(runs),
            "world_decisions": decisions,
            "quiet_days": quiet,
            "instructions_chosen": len(chosen),
            "instructions_retrieved": len(set(retrieved) & world_ids),
            "instructions_available": len(world_ids),
            "never_chosen": sorted(world_ids - set(chosen)),
            "never_retrieved": sorted(world_ids - set(retrieved)),
        },
        "vocabulary": {
            "distinct_sentences": len(sentences),
            "effective_sentences": round(effective(sentences.values()), 2),
            "top_sentence_share_pct": (round(100 * sentences.most_common(1)[0][1]
                                             / sum(sentences.values()), 1)
                                       if sentences else None),
            "distinct_stimuli": len(stimuli),
            "effective_stimuli": round(effective(stimuli.values()), 2),
            "reframings": sum(reframed.values()),
            "reframed_events": len(reframed),
            "effective_reframed": (round(effective(reframed.values()), 2)
                                   if reframed else None),
            "sentences": [{"text": t, "n": n} for t, n in sentences.most_common()],
        },
        "per_run": per_run,
    }


def to_markdown(data: dict) -> str:
    r, v = data["repertoire"], data["vocabulary"]
    lines = [
        "# World balance", "",
        f"{r['seeds']} run(s), {data['meta']['date']}. Generated by "
        "`experiments/world_balance.py`.", "",
        "## Repertoire: can the world do more than one thing?", "",
        f"- events: `{r['events']}`",
        f"- most common event: **{r['top_share_pct']}%** of {r['total']}",
        f"- most common event other than weather: **{r['top_happening_share_pct']}%** "
        f"of {r['happenings']}",
        f"- effective event kinds: **{r['effective_event_kinds']}**",
        f"- distinct event sequences across {r['seeds']} seeds: "
        f"**{r['distinct_sequences']}** "
        + ("(seeds do not diverge; they are not replicates)"
           if r["distinct_sequences"] <= 1 and r["seeds"] > 1 else ""),
        f"- world decisions: {r['world_decisions']}, of which {r['quiet_days']} quiet",
        f"- instructions chosen at least once: {r['instructions_chosen']} of "
        f"{r['instructions_available']} (retrieved at all: {r['instructions_retrieved']})",
    ]
    if r["never_retrieved"]:
        lines += ["", "Never retrieved (gated out, or below the top-k cut):", ""]
        lines += [f"  - `{i}`" for i in r["never_retrieved"]]
    if r["never_chosen"]:
        lines += ["", "Retrieved but never chosen (outscored, or always refused):", ""]
        lines += [f"  - `{i}`" for i in sorted(set(r["never_chosen"]) - set(r["never_retrieved"]))]

    lines += [
        "", "## Vocabulary: can the world say more than one thing?", "",
        "This is the ceiling on every measurement of what villagers keep. A "
        "village of any size, run for any number of seeds, cannot produce more "
        "independent stimuli than the world has distinct things to say.", "",
        f"- distinct first-hand sentences: **{v['distinct_sentences']}**",
        f"- effective independent sentences: **{v['effective_sentences']}**",
        f"- most common sentence: {v['top_sentence_share_pct']}% of first-hand facts",
        f"- distinct (seed, event) stimuli: {v['distinct_stimuli']}, "
        f"effective **{v['effective_stimuli']}**",
        f"- reframings: {v['reframings']}, from {v['reframed_events']} (seed, event) "
        f"stimuli, effective **{v['effective_reframed']}**. This bounds the "
        "absorption counterfactual", "",
        "| n | sentence |", "|---|---|",
    ]
    for row in v["sentences"][:15]:
        lines.append(f"| {row['n']} | {row['text'][:96]} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="*")
    parser.add_argument("--latest", type=int, default=0,
                        help="use the N most recent runs instead of naming them")
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    if args.latest:
        dirs = [d for d in sorted((ROOT / "runs").iterdir(),
                                  key=lambda p: p.stat().st_mtime)
                if (d / "events.jsonl").exists()][-args.latest:]
    else:
        dirs = [ROOT / "runs" / name for name in args.runs]
    if not dirs:
        raise SystemExit("name some runs, or pass --latest N")

    data = analyse([read(d) for d in dirs])
    r, v = data["repertoire"], data["vocabulary"]

    print(f"runs: {', '.join(data['meta']['runs'])}\n")
    print("repertoire")
    print(f"  events                      {r['events']}")
    print(f"  most common event           {r['top_share_pct']}%")
    print(f"  most common, weather aside  {r['top_happening_share_pct']}% of {r['happenings']}")
    print(f"  distinct sequences          {r['distinct_sequences']} of {r['seeds']} seeds")
    print(f"  instructions chosen         {r['instructions_chosen']}/{r['instructions_available']}"
          f"  (retrieved {r['instructions_retrieved']})")
    print(f"  quiet days                  {r['quiet_days']}/{r['world_decisions']}")
    print("\nvocabulary")
    print(f"  distinct sentences          {v['distinct_sentences']}")
    print(f"  effective sentences         {v['effective_sentences']}")
    print(f"  effective (seed, event)     {v['effective_stimuli']}")
    print(f"  reframed (seed, event)      {v['reframed_events']} of {v['reframings']} "
          f"reframings, effective {v['effective_reframed']}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "world_balance.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (out / "world_balance.md").write_text(to_markdown(data), encoding="utf-8")
    print(f"\nwrote {out / 'world_balance.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
