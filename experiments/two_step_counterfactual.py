#!/usr/bin/env python3
"""Does one villager's personality reach what another villager remembers?

The absorption counterfactual (experiments/diffusion_counterfactual.py) shows
that temperament changes what a villager keeps and how it words it. That is one
villager at a time. This follows the news one step further.

It takes chains the simulation actually produced, where villager B reframed a
piece of news and later told it to villager C, and C reframed it in turn. Then:

  1. B's reframing is replayed with B's own lens, and again with B's
     temperament swapped (the whole temperament, or one locus). Everything
     else B saw is held fixed.
  2. C hears each of B's versions. C's own lens, what C already knew, and the
     decoder seed are held fixed, so C's two calls differ only in what B said.

What changes in C's memory is caused by B's personality. Three measures:

  memory changed   the news no longer reaches C (B's swapped self discarded
                   it), or C now keeps or discards it differently, or C files
                   it under a different kind. The kind sets C's
                   knows_<kind>_<place> tag, so a changed kind changes what C
                   can do
  kind changed     the last of those on its own
  rewording        how far apart C's two versions are (1 - cosine), when C
                   kept both

The same floors as the absorption counterfactual. The decoder floor replays
B's original prompt a second time and passes that on. The inert-tag floor
swaps a locus that carries no lens (sociability, diligence) at B.

    python experiments/two_step_counterfactual.py <run_id> [<run_id> ...]
    python experiments/two_step_counterfactual.py --from-raw results/two_step_counterfactual.json

The first form needs the speech model and the embedder. The second recomputes
every statistic from the saved model outputs and needs only the embedder.

Writes results/two_step_counterfactual.{json,md}.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import statistics
import sys
import zlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import diffusion_counterfactual as dc  # noqa: E402
from lens_divergence import rank_sum  # noqa: E402
from world_balance import effective  # noqa: E402

from hearthwick.character import LOCI, load_founders  # noqa: E402
from hearthwick.config import DATA_DIR, ROOT, SimConfig  # noqa: E402
from hearthwick.corpus import build_corpus, build_retriever, make_embedder  # noqa: E402
from hearthwick.diffusion import _parse, compose_lens  # noqa: E402
from hearthwick.knowledge import KINDS  # noqa: E402
from hearthwick.llm import SpeechModel  # noqa: E402

BASE = "as heard"
LABELS = [dc.NULL, "whole temperament", *LOCI]


def chains(run_dir: Path) -> tuple[list[dict], dict, dict, dict]:
    """(B's reframing, C's reframing of B's result) pairs from one run."""
    events, roster, meta = dc.lens_events(run_dir)
    knowledge = json.loads((run_dir / "knowledge.json").read_text(encoding="utf-8"))
    kinds = {f["id"]: f["kind"] for held in knowledge.values() for f in held}
    roots = {f["id"]: f["root"] for held in knowledge.values() for f in held}
    stored: dict[tuple[str, str], str] = {}
    with open(run_dir / "events.jsonl", encoding="utf-8") as log:
        for line in log:
            e = json.loads(line)
            if e["type"] == "knowledge_stored" and e.get("parent"):
                stored[(e["holder"], e["parent"])] = e["id"]
                kinds.setdefault(e["id"], e["kind"])
    by_fact: dict[str, list[dict]] = collections.defaultdict(list)
    for e in events:
        by_fact[e["fact"]].append(e)
    out = []
    for b in events:
        told = stored.get((b["character"], b["fact"]))
        for c in by_fact.get(told, []):
            out.append({"run": run_dir.name, "b": b, "c": c,
                        "root": roots.get(b["fact"]),
                        "b_heard_kind": kinds.get(b["fact"], "news"),
                        "c_heard_kind": kinds.get(told, "news")})
    return out, roster, meta, kinds


def b_tags(label: str, tags: list[str], actor: dict, roster: dict) -> list[str] | None:
    """The lens tags for B under one condition, as the absorption replay builds them."""
    if label in (BASE, dc.NULL):
        return tags
    if label == "whole temperament":
        donor = next((c for cid, c in sorted(roster.items())
                      if cid != actor["id"] and c["temperament"] != actor["temperament"]),
                     None)
        return dc.whole_swap(tags, donor["temperament"]) if donor else None
    mine = actor["temperament"][label]
    other = next((a for a in sorted({c["temperament"][label] for c in roster.values()})
                  if a != mine), None)
    return dc.swapped_tags(tags, mine, other) if other else None


def settle(parsed, heard_text: str, heard_kind: str) -> dict | None:
    """What the simulation would store, from the model's reply."""
    if parsed is None:
        return None
    keep, text, kind = parsed
    return {"kept": bool(keep), "text": text or heard_text,
            "kind": kind if kind in KINDS else heard_kind}


async def collect(args) -> dict:
    all_chains: list[dict] = []
    roster: dict = {}
    meta = None
    for run_id in args.runs:
        found, run_roster, run_meta, _ = chains(ROOT / "runs" / run_id)
        all_chains += found
        roster.update(run_roster)
        meta = meta or run_meta
    if not all_chains:
        raise SystemExit("no two-step chains in those runs (was the speech model up?)")
    if args.limit:
        all_chains = all_chains[:args.limit]

    config = meta["config"]
    retriever, _ = setup(meta)
    speech = SpeechModel(config["llm_base_url"] or args.llm, config["llm_model"],
                         concurrency=args.concurrency, max_tokens=160,
                         temperature=0.0, api_key=config.get("llm_api_key"))
    if not await speech.connect():
        raise SystemExit("speech model unavailable; this measurement needs it")
    print(f"{len(all_chains)} chains, replayed through {speech.model} at temperature 0")

    async def call(event: dict, character: dict, tags: list[str], step: str):
        system, user = dc.build_prompt(retriever, event, character, tags)
        seed = zlib.crc32(f"{args.seed}:{step}:{event['fact']}:{event['character']}".encode())
        return _parse(await speech.say(system, user, seed))

    async def gather(jobs, what):
        results = {}
        for start in range(0, len(jobs), args.chunk):
            batch = jobs[start:start + args.chunk]
            for key, parsed in await asyncio.gather(*(j() for j in batch)):
                results[key] = parsed
            print(f"  {what}: {min(start + args.chunk, len(jobs))}/{len(jobs)} calls",
                  flush=True)
        return results

    # Step 1: B under each condition. Chains that share B's reframing share it.
    b_jobs, b_keys = [], {}
    for i, ch in enumerate(all_chains):
        b = ch["b"]
        key_b = (ch["run"], b["fact"], b["character"])
        b_keys[i] = key_b
        actor = roster[b["character"]]
        for label in (BASE, *LABELS):
            tags = b_tags(label, b["tags"], actor, roster)
            if tags is None:
                continue

            async def job(b=b, actor=actor, tags=tags, label=label, key_b=key_b):
                return (key_b, label), await call(b, actor, tags, "B")
            b_jobs.append(((key_b, label), job))
    unique = {}
    for key, job in b_jobs:
        unique.setdefault(key, job)
    b_raw = await gather(list(unique.values()), "B")

    # Step 2: C hears each of B's versions, with C's own lens.
    c_jobs = []
    for i, ch in enumerate(all_chains):
        c = ch["c"]
        for label in (BASE, *LABELS):
            said = settle(b_raw.get((b_keys[i], label)), ch["b"]["heard"], ch["b_heard_kind"])
            if said is None or not said["kept"]:
                continue
            event = {**c, "heard": said["text"]}

            async def job(i=i, label=label, event=event, c=c):
                return (i, label), await call(event, roster[c["character"]], c["tags"], "C")
            c_jobs.append(job)
    c_raw = await gather(c_jobs, "C")

    raw = []
    for i, ch in enumerate(all_chains):
        b_actor = roster[ch["b"]["character"]]
        for label in (BASE, *LABELS):
            tags = b_tags(label, ch["b"]["tags"], b_actor, roster)
            if tags is None:
                continue
            said = settle(b_raw.get((b_keys[i], label)), ch["b"]["heard"], ch["b_heard_kind"])
            heard_by_c = said["text"] if said and said["kept"] else None
            kept_by_c = settle(c_raw.get((i, label)), heard_by_c or "", ch["c_heard_kind"])
            raw.append({"chain": i, "run": ch["run"], "condition": label,
                        "b": ch["b"]["character"], "c": ch["c"]["character"],
                        "b_tags": tags, "b_result": said, "c_result": kept_by_c})
    return {"meta": {"runs": list(args.runs), "village": meta.get("village"),
                     "chains": len(all_chains), "model": speech.model,
                     "calls": speech.calls, "failures": speech.failures,
                     "errors": speech.errors,
                     "date": datetime.now().strftime("%Y-%m-%d")},
            "raw": raw}


def setup(meta: dict):
    config = meta["config"]
    village = meta.get("village") if meta.get("village") != "hearthwick" else None
    base = (DATA_DIR / "villages" / village) if village else None
    founders = load_founders((base / "founders.yaml") if base
                             else DATA_DIR / "characters" / "founders.yaml")
    embedder = make_embedder(config["embedder"], config["embed_url"])
    return build_retriever(build_corpus(DATA_DIR, founders,
                                        switches=SimpleNamespace(**config)), embedder,
                           config["retrieval_threshold"],
                           config.get("restore_below_threshold", True)), embedder


def score(payload: dict, embedder, retriever, roster_names: dict) -> dict:
    by_chain: dict[int, dict[str, dict]] = collections.defaultdict(dict)
    for row in payload["raw"]:
        by_chain[row["chain"]][row["condition"]] = row

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

    tally = {label: collections.Counter() for label in LABELS}
    rewording: dict[str, list[float]] = collections.defaultdict(list)
    examples = []
    for i, rows in by_chain.items():
        base = rows.get(BASE)
        if base is None or base["b_result"] is None:
            continue
        b_base_kept = base["b_result"]["kept"]
        c_base = base["c_result"]
        name = roster_names.get(base["b"], base["b"])
        _, base_lens = compose_lens(retriever, name, base["b_tags"])
        for label in LABELS:
            row = rows.get(label)
            if row is None or row["b_result"] is None:
                continue
            reach_changed = row["b_result"]["kept"] != b_base_kept
            c = row["c_result"]
            if not reach_changed and b_base_kept and (c is None or c_base is None):
                continue            # C's reply did not parse, so nothing to compare
            t = tally[label]
            t["compared"] += 1
            _, lens = compose_lens(retriever, name, row["b_tags"])
            moved = set(lens) != set(base_lens)
            t["b_lens_moved"] += moved
            changed = reach_changed
            kind_changed = False
            if not reach_changed and b_base_kept:
                if c["kept"] != c_base["kept"]:
                    changed = True
                    t["c_keep_flipped"] += 1
                elif c["kept"] and c["kind"] != c_base["kind"]:
                    changed = kind_changed = True
                    t["c_kind_changed"] += 1
                if c["kept"] and c_base["kept"]:
                    t["both_kept"] += 1
                    va, vb = vector(c_base["text"]), vector(c["text"])
                    if va is not None and vb is not None:
                        rewording[label].append(1.0 - dc.cosine(va, vb))
            t["reach_changed"] += reach_changed
            t["memory_changed"] += changed
            if moved:
                t["moved_compared"] += 1
                t["moved_changed"] += changed
            if kind_changed and label == "whole temperament" and len(examples) < 6:
                examples.append({"b": base["b"], "c": base["c"],
                                 "b_said_own": base["b_result"]["text"],
                                 "b_said_swapped": row["b_result"]["text"],
                                 "c_kept_own": c_base["text"], "c_kind_own": c_base["kind"],
                                 "c_kept_swapped": row["c_result"]["text"],
                                 "c_kind_swapped": row["c_result"]["kind"]})

    floor = tally[dc.NULL]
    inert = collections.Counter()
    for locus in dc.NO_LENS_LOCI:
        inert.update(tally[locus])
    inert_rewording = [v for l in dc.NO_LENS_LOCI for v in rewording[l]]

    rows = []
    for label in LABELS:
        t, n = tally[label], tally[label]["compared"]
        spread = rewording[label]
        rows.append({
            "what": label, "compared": n,
            "memory_changed": t["memory_changed"],
            "memory_changed_pct": round(100 * t["memory_changed"] / n, 1) if n else None,
            "reach_changed": t["reach_changed"], "c_keep_flipped": t["c_keep_flipped"],
            "c_kind_changed": t["c_kind_changed"],
            "kind_changed_pct": round(100 * t["c_kind_changed"] / n, 1) if n else None,
            "b_lens_moved_pct": round(100 * t["b_lens_moved"] / n, 1) if n else None,
            "pct_when_moved": (round(100 * t["moved_changed"] / t["moved_compared"], 1)
                               if t["moved_compared"] else None),
            "rewording_median": round(float(statistics.median(spread)), 3) if spread else None,
            "rewording_n": len(spread),
            "no_lens": label in dc.NO_LENS_LOCI, "null": label == dc.NULL,
            "p_vs_floor": (None if label == dc.NULL or not n or not floor["compared"] else
                           round(dc.fisher_exact_greater(
                               t["memory_changed"], n - t["memory_changed"],
                               floor["memory_changed"],
                               floor["compared"] - floor["memory_changed"]), 4)),
            "p_vs_inert": (None if label == dc.NULL or label in dc.NO_LENS_LOCI or not n
                           or not inert["compared"] else
                           round(dc.fisher_exact_greater(
                               t["memory_changed"], n - t["memory_changed"],
                               inert["memory_changed"],
                               inert["compared"] - inert["memory_changed"]), 4)),
            "rewording_p_vs_inert": (None if label in dc.NO_LENS_LOCI or label == dc.NULL
                                     or not spread or not inert_rewording else
                                     round(rank_sum(spread, inert_rewording)[1], 4)),
        })
    return {
        "floors": {
            "decoder": {"changed": floor["memory_changed"], "compared": floor["compared"],
                        "pct": round(100 * floor["memory_changed"] / floor["compared"], 1)
                        if floor["compared"] else None},
            "inert_tag": {"changed": inert["memory_changed"], "compared": inert["compared"],
                          "pct": round(100 * inert["memory_changed"] / inert["compared"], 1)
                          if inert["compared"] else None},
        },
        "rows": rows, "examples": examples,
    }


def to_markdown(data: dict) -> str:
    m, f = data["meta"], data["floors"]
    lines = [
        "# Two-step counterfactual", "",
        f"{m['chains']} chains (B reframed news, then told it to C) from "
        f"{len(m['runs'])} run(s), replayed at temperature 0 through {m['model']}. "
        f"Generated by `experiments/two_step_counterfactual.py` on {m['date']}.", "",
        f"The chains come from {data['events']['distinct']} events, "
        f"{data['events']['effective']} of them effective, and the p-values treat "
        "chains as independent, so they overstate significance.", "",
        "B's temperament is swapped. C's lens, prior knowledge and decoder seed are "
        "held fixed, so any change in C's memory was caused by B's personality.", "",
        f"Floors: the same prompt at B, replayed twice ({f['decoder']['pct']}%), and a "
        f"locus with no lens swapped at B ({f['inert_tag']['pct']}%). A claim about "
        "memory has to clear whichever floor is higher, so both are tested.", "",
        "| Swapped at B | C's memory changed | of which C's kind changed | B's lens moved "
        "| p vs decoder | p vs inert | C's rewording (median) | p vs inert |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in data["rows"]:
        name = r["what"] + (" (no lens)" if r["no_lens"] else "")
        lines.append(
            f"| {name} | {r['memory_changed_pct']}% ({r['memory_changed']}/{r['compared']}) "
            f"| {r['kind_changed_pct']}% | {r['b_lens_moved_pct']}% "
            f"| {r['p_vs_floor'] if r['p_vs_floor'] is not None else '-'} "
            f"| {r['p_vs_inert'] if r['p_vs_inert'] is not None else '-'} "
            f"| {r['rewording_median'] if r['rewording_median'] is not None else '-'} "
            f"| {r['rewording_p_vs_inert'] if r['rewording_p_vs_inert'] is not None else '-'} |")
    if data["examples"]:
        lines += ["", "## Examples: B's temperament changed the kind C remembered", ""]
        for e in data["examples"]:
            lines += [f"- {e['b']} to {e['c']}.",
                      f"  - B as itself: \"{e['b_said_own']}\"",
                      f"  - B swapped: \"{e['b_said_swapped']}\"",
                      f"  - C kept, as {e['c_kind_own']}: \"{e['c_kept_own']}\"",
                      f"  - C kept, as {e['c_kind_swapped']}: \"{e['c_kept_swapped']}\""]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="*")
    parser.add_argument("--from-raw", default=None,
                        help="recompute statistics from a saved result, with no model calls")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0,
                        help="use only the first N chains (a quick check that it runs)")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--chunk", type=int, default=64)
    parser.add_argument("--llm", default=SimConfig.llm_base_url)
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    if args.from_raw:
        saved = json.loads(Path(args.from_raw).read_text(encoding="utf-8"))
        payload = {"meta": saved["meta"], "raw": saved["raw"]}
        args.runs = saved["meta"]["runs"]
    else:
        if not args.runs:
            raise SystemExit("name the runs to replay, or pass --from-raw")
        payload = asyncio.run(collect(args))

    _, _, meta, _ = chains(ROOT / "runs" / args.runs[0])
    names = {}
    for run_id in args.runs:
        _, run_roster, _, _ = chains(ROOT / "runs" / run_id)
        names.update({cid: c["name"] for cid, c in run_roster.items()})
    retriever, embedder = setup(meta)
    data = {**payload, **score(payload, embedder, retriever, names)}

    # The chains cluster within events, and the p-values above treat them as
    # independent. Report how many independent events they amount to.
    every = [ch for run_id in args.runs for ch in chains(ROOT / "runs" / run_id)[0]]
    used = {row["chain"] for row in payload["raw"]}
    per_event = collections.Counter((every[i]["run"], every[i]["root"])
                                    for i in used if i < len(every))
    data["events"] = {"distinct": len(per_event),
                      "effective": round(effective(per_event.values()), 2),
                      "largest_share_pct": (round(100 * max(per_event.values())
                                                  / sum(per_event.values()), 1)
                                            if per_event else None),
                      "by_kind": dict(collections.Counter(
                          (root or "?").split(":")[0] + ":" + (root or "?:?").split(":")[1]
                          for (_, root) in per_event))}

    f, ev = data["floors"], data["events"]
    print(f"\n{len(used)} chains from {ev['distinct']} events, {ev['effective']} effective")
    print(f"floors: decoder {f['decoder']['pct']}%, inert tag {f['inert_tag']['pct']}%")
    for r in data["rows"]:
        print(f"  {r['what']:18} C's memory changed {r['memory_changed_pct']:>5}% "
              f"({r['memory_changed']}/{r['compared']}), kind {r['kind_changed_pct']}%, "
              f"B's lens moved {r['b_lens_moved_pct']}%, p={r['p_vs_inert']}, "
              f"rewording {r['rewording_median']} p={r['rewording_p_vs_inert']}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "two_step_counterfactual.json").write_text(json.dumps(data, indent=2),
                                                      encoding="utf-8")
    (out / "two_step_counterfactual.md").write_text(to_markdown(data), encoding="utf-8")
    print(f"\nwrote {out / 'two_step_counterfactual.json'} and .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
