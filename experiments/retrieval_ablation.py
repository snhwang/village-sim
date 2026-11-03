#!/usr/bin/env python3
"""Is retrieval load-bearing, or is the corpus a lookup table?

Runs the village under each combination of gating and embedder and reports, for
each, how often similarity rather than priority decided the action, how much of
the corpus got used, and whether the village still behaves (asleep at night,
working in the morning). Writes results/retrieval_ablation.{json,md}.

    python experiments/retrieval_ablation.py            # every configuration
    python experiments/retrieval_ablation.py --days 2   # longer

The service configurations need the embedding service on :8360
(serving/: docker compose --profile embed up -d). Without it they fall
back to BM25 and the run is marked as such.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hearthwick.config import ROOT, SimConfig  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402

CONFIGS = [
    ("hard gates, BM25", dict(gating="hard", embedder="bm25", retrieval_threshold=0.0)),
    ("hard gates, service", dict(gating="hard", embedder="service", retrieval_threshold=0.0)),
    ("soft tags, BM25", dict(gating="soft", embedder="bm25", retrieval_threshold=0.0)),
    ("soft tags, service, t=0", dict(gating="soft", embedder="service", retrieval_threshold=0.0)),
    # The same with BEAR's old threshold behavior. At t=0 nothing is set aside,
    # so this must match the arm above exactly. If it does not, something
    # other than the threshold differs between the arms.
    ("soft tags, service, t=0, restored", dict(gating="soft", embedder="service",
                                               retrieval_threshold=0.0,
                                               restore_below_threshold=True)),
    ("soft tags, service, t=0.15", dict(gating="soft", embedder="service", retrieval_threshold=0.15)),
    ("soft tags, service, t=0.40", dict(gating="soft", embedder="service", retrieval_threshold=0.40)),
]


def behavior(run_dir: Path) -> dict:
    """Two sanity checks a broken configuration fails: night and morning."""
    frames = [json.loads(line) for line in open(run_dir / "frames.jsonl", encoding="utf-8")]

    def at(day: float, hour: float):
        for f in frames:
            if f["clock"]["day"] == day and abs(f["clock"]["hour"] - hour) < 0.01:
                return f
        return None

    # The morning check asks whether the village gets up and works, so it has
    # to be a dry morning. Once the world decided the sky separately, every
    # run opened with spring rain, and a 9am snapshot of day 1 caught the
    # whole village sheltering whatever the configuration.
    ticks_per_day = round(24 / (frames[1]["clock"]["hour"] - frames[0]["clock"]["hour"]))
    sky = {}
    for line in open(run_dir / "events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e["type"] == "world_event" and e["event"] == "weather":
            sky[e["t"] // ticks_per_day] = e["data"]["kind"]
    weather, day_weather = "clear", {}
    last_day = max(f["clock"]["day"] for f in frames)
    for day in range(last_day + 1):
        weather = sky.get(day, weather)
        day_weather[day] = weather
    dry = [d for d in range(1, last_day + 1) if day_weather[d] == "clear"]
    morning_day = dry[0] if dry else 1

    night, morning = at(1, 2.0), at(morning_day, 9.0)
    return {
        "asleep_at_2am": sum(1 for c in night["c"] if c[3] == "rest") if night else None,
        "villagers": len(night["c"]) if night else None,
        "morning_day": morning_day,
        "morning_weather": day_weather.get(morning_day),
        "activities_at_9am": dict(collections.Counter(c[3] for c in morning["c"])) if morning else {},
    }


def set_aside(records: list[dict]) -> dict:
    """How often the threshold set anything aside in villagers' decisions.

    Read from BEAR's audit record of each retrieval, which lists every
    candidate left out and why, so nothing here re-derives the retriever's
    rules. Without it, a configuration that moved little cannot be told from
    one in which the threshold never fired. Decisions are the retrievals
    whose context carries a stage tag, which leaves out the world's and the
    speech and lens retrievals.
    """
    decisions = with_any = total = 0
    for record in records:
        if record.get("schema") != "bear.turn/1":
            continue
        for retrieval in record.get("retrievals", []):
            tags = (retrieval.get("context") or {}).get("tags") or []
            if not any(t.startswith("stage_") for t in tags) or "talking" in tags \
                    or "absorbing" in tags:
                continue
            decisions += 1
            n = sum(1 for e in retrieval.get("excluded", []) if e.get("reason") == "threshold")
            total += n
            with_any += n > 0
    return {"audited_decisions": decisions, "decisions_with_set_aside": with_any,
            "set_aside_per_decision": round(total / decisions, 2) if decisions else None}


def choices_digest(run_dir: Path) -> str:
    """A fingerprint of every decision's tick, decider and choice, in order.

    Two arms that must behave identically (t=0 with and without the old
    threshold behavior) must give the same digest.
    """
    import hashlib
    h = hashlib.sha256()
    for line in open(run_dir / "events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e["type"] == "decision":
            h.update(f"{e['t']}|{e['character']}|{e.get('chosen')};".encode())
    return h.hexdigest()[:16]


def arm_config(overrides: dict, seed: int, village: str | None = None,
               days_per_year: int | None = None, profile: str | None = None) -> SimConfig:
    """The configuration of one arm: the profile's switches, then the arm's
    own settings over them, then a year length given explicitly. The arm
    comes last because it is what the ablation varies. Applied the other way
    round, the illustrative profile, which sets restore_below_threshold off,
    silently turned the restored arm into the unrestored one (2026-10-18).
    The paper profile sets nothing an arm sets, so its ablation is the same
    either way."""
    from dataclasses import replace

    from hearthwick.__main__ import PROFILES

    config = SimConfig(seed=seed, llm_base_url=None, village=village)
    if profile:
        config = replace(config, **PROFILES[profile])
    config = replace(config, **overrides)
    if days_per_year:
        config = replace(config, days_per_year=days_per_year)
    return config


def run_one(label: str, overrides: dict, days: float, seed: int,
            village: str | None = None, days_per_year: int | None = None,
            profile: str | None = None) -> dict:
    """One arm. ``profile`` names a set of switches (hearthwick.__main__.PROFILES),
    applied as the command line applies it. Without one, a SimConfig built
    here has its defaults, which are not the paper's village."""
    sim = Simulation(arm_config(overrides, seed, village, days_per_year, profile))
    records: list[dict] = []
    try:
        from bear import Auditor
    except ImportError:  # a bear without the audit records nothing more
        Auditor = None
    if Auditor is not None:
        with Auditor([records.append]).turn(session_id=label):
            asyncio.run(sim.run(int(days * sim.clock.ticks_per_day)))
    else:
        asyncio.run(sim.run(int(days * sim.clock.ticks_per_day)))
    sim.close()

    usage = json.loads((sim.log.dir / "usage.json").read_text(encoding="utf-8"))
    asked_for_service = overrides["embedder"] == "service"
    got_service = sim.embedder is not None
    return {
        "label": label,
        "gating": overrides["gating"],
        "embedder": "service" if got_service else "bm25",
        "threshold": overrides["retrieval_threshold"],
        "restore_below_threshold": overrides.get("restore_below_threshold", False),
        **set_aside(records),
        "choices_digest": choices_digest(sim.log.dir),
        "fell_back_to_bm25": asked_for_service and not got_service,
        "run_id": sim.log.run_id,
        "decisions": usage["decisions"],
        "similarity_decided_pct": usage["similarity_decided_pct"],
        "instructions_used": usage["instructions_chosen"],
        "actionable_instructions": usage["actionable_instructions"],
        "never_chosen": len(usage["never_chosen"]),
        **behavior(sim.log.dir),
    }


def to_markdown(results: list[dict], meta: dict) -> str:
    lines = [
        "# Retrieval ablation",
        "",
        f"{meta['days']} in-game day(s), seed {meta['seed']}, {meta['villagers']} villagers, "
        "no speech model. Generated by `experiments/retrieval_ablation.py` on "
        f"{meta['date']}.",
        "",
        "`similarity decided` is the share of decisions where ranking the candidate "
        "instructions by score chose a different one than ranking them by priority "
        "alone. Near zero means the gates are deciding and the corpus is a lookup "
        "table.",
        "",
        "The 9am column is the first dry morning, so that the check asks whether "
        "the village gets up and works rather than whether it shelters from rain.",
        "",
        "`set aside` is the share of villagers' decisions in which the threshold "
        "set any candidate aside, from BEAR's audit record of each retrieval.",
        "",
        "| Configuration | Similarity decided | Set aside | Instructions used | Asleep at 2am | 9am, dry morning |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        note = " *(service unavailable, fell back)*" if r["fell_back_to_bm25"] else ""
        acts = ", ".join(f"{k} {v}" for k, v in sorted(r["activities_at_9am"].items()))
        audited = r.get("audited_decisions")
        aside = (f"{round(100 * r['decisions_with_set_aside'] / audited, 1)}%"
                 if audited else "not recorded")
        lines.append(
            f"| {r['label']}{note} | {r['similarity_decided_pct']}% | {aside} | "
            f"{r['instructions_used']}/{r['actionable_instructions']} | "
            f"{r['asleep_at_2am']}/{r['villagers']} | day {r['morning_day']}: {acts} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--village", default=None,
                        help="a generated village in data/villages/")
    parser.add_argument("--days", type=float, default=2.4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--days-per-year", type=int, default=None,
                        help="year length (default the simulation's)")
    parser.add_argument("--profile", default=None,
                        help="a set of switches, as for a run (the paper's is 'paper')")
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    results = []
    for label, overrides in CONFIGS:
        print(f"running {label} ...", flush=True)
        results.append(run_one(label, overrides, args.days, args.seed, args.village,
                               args.days_per_year, args.profile))
        print(f"  {results[-1]['similarity_decided_pct']}% similarity, "
              f"{results[-1]['instructions_used']} instructions, "
              f"{results[-1]['asleep_at_2am']}/{results[-1]['villagers']} asleep")

    from hearthwick.events import code_versions
    meta = {"days": args.days, "seed": args.seed, "villagers": results[0]["villagers"],
            "days_per_year": args.days_per_year or SimConfig.days_per_year,
            "profile": args.profile,
            "date": datetime.now().strftime("%Y-%m-%d"), "code": code_versions()}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "retrieval_ablation.json").write_text(
        json.dumps({"meta": meta, "results": results}, indent=2), encoding="utf-8")
    (out / "retrieval_ablation.md").write_text(to_markdown(results, meta), encoding="utf-8")
    print(f"\nwrote {out / 'retrieval_ablation.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
