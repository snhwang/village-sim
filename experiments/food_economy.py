#!/usr/bin/env python3
"""How the village feeds itself: the granary, the harvest, the fields, the work.

    python experiments/food_economy.py <run_id> [<run_id> ...]

Reads each run's logs and reports, per run and pooled:

- the granary and the standing crop at each dawn, and yesterday's field workers
- what each harvest brought in against a year's need, and its verdict
- how often the fields grew, and by whom
- the days the village went hungry
- which food instructions villagers chose, and how often
- what adults and elders were doing in working hours (9 to 17) on dry days,
  and which instructions they chose then

It also reads runs from before food existed, for the working-hours figures.

Writes results/food_economy.json and .md.
"""

from __future__ import annotations

import collections
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RESULTS = ROOT / "results"
WORK_HOURS = range(9, 17)


def events(run: Path):
    with open(run / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def analyse(run_id: str) -> dict:
    run = RUNS / run_id
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    clock = meta["config"]
    ticks_per_day = 24 * 60 // clock["minutes_per_tick"]
    start_hour = 6

    def day_hour(t: int) -> tuple[int, int]:
        minutes = start_hour * 60 + t * clock["minutes_per_tick"]
        return minutes // (24 * 60), (minutes % (24 * 60)) // 60

    roster, dawns, harvests, grown, wet = {}, [], [], [], set()
    chosen, working_choices = collections.Counter(), collections.Counter()
    decisions = []
    for e in events(run):
        kind = e["type"]
        if kind == "roster":
            roster.update({c["id"]: c for c in e["characters"]})
        elif kind == "food":
            day, _ = day_hour(e["t"])
            dawns.append({"day": day, **{k: e.get(k) for k in (
                "season", "store", "need", "crop", "capacity", "tiles", "worked_fields",
                "gathered")}})
        elif kind == "world_event" and e.get("event") == "harvest":
            harvests.append({"day": day_hour(e["t"])[0], **(e.get("data") or {})})
        elif kind == "world_event" and e.get("event") == "weather":
            if (e.get("data") or {}).get("kind") in ("rain", "storm"):
                wet.add(day_hour(e["t"])[0])
        elif kind == "place_grown":
            grown.append({"day": day_hour(e["t"])[0], "by": e.get("by"), "tiles": e.get("tiles")})
        elif kind == "decision" and e.get("character") != "world":
            if str(e.get("chosen", "")).startswith("food-"):
                chosen[e["chosen"]] += 1
            decisions.append(e)

    working = {cid for cid, c in roster.items() if c["stage"] in ("adult", "elder")}
    # "Go home and rest" chosen by someone who was not tired (fault 39)
    tired = [e for e in decisions if str(e.get("chosen", "")).endswith("-tired")]
    tired_rested = sum(1 for e in tired if "energy_low" not in (e.get("tags") or []))
    for e in decisions:
        day, hour = day_hour(e["t"])
        if e["character"] in working and day not in wet and hour in WORK_HOURS:
            working_choices[e.get("chosen")] += 1
    activity = collections.Counter()
    by_role = collections.defaultdict(collections.Counter)
    with open(run / "frames.jsonl", encoding="utf-8") as f:
        for line in f:
            frame = json.loads(line)
            day, hour = day_hour(frame["t"])
            if day in wet or hour not in WORK_HOURS:
                continue
            for cid, _x, _y, act, *_ in frame["c"]:
                if cid in working:
                    activity[act] += 1
                    by_role[roster[cid].get("role") or "none"][act] += 1

    def shares(counter):
        total = sum(counter.values()) or 1
        return {k: round(v / total, 3) for k, v in counter.most_common()}

    need = dawns[0]["need"] if dawns else None
    year = need * clock["days_per_year"] if need else None
    hungry = sorted({d["day"] for d in dawns if (d["store"] or 0) <= 0})
    return {
        "run": run_id, "villagers": sum(1 for c in roster.values() if not c.get("visitor")), "need_per_day": need, "need_per_year": year,
        "dawns": dawns, "harvests": harvests, "fields_grown": grown, "hungry_days": hungry,
        "wet_days": sorted(wet), "food_instructions_chosen": dict(chosen.most_common()),
        "working_hours_dry": shares(activity),
        "working_hours_dry_decisions": sum(working_choices.values()),
        "working_hours_dry_chosen": dict(working_choices.most_common(15)),
        "adults_and_elders": len(working),
        "tired_chosen": len(tired), "tired_chosen_while_rested": tired_rested,
        "working_hours_dry_by_role": {r: shares(c) for r, c in sorted(by_role.items())},
    }


def markdown(results: list[dict]) -> str:
    out = ["# Food economy", "",
           f"{len(results)} run(s). Generated by `experiments/food_economy.py` on "
           f"{date.today().isoformat()}.", ""]
    for r in results:
        out += [f"## {r['run']}", ""]
        if r["need_per_day"] is None:
            out += ["No food events: this run predates the food economy.", ""]
        else:
            out += [f"{r['villagers']} villagers eat {r['need_per_day']} a day, "
                    f"{r['need_per_year']} a year. Wet days: {r['wet_days'] or 'none'}.", "",
                    "| dawn | season | granary | days of food | crop / fields hold | plots | field workers yesterday |",
                    "|---|---|---|---|---|---|---|"]
        for d in r["dawns"]:
            days = d["store"] / d["need"] if d["need"] else 0
            out.append(f"| {d['day']} | {d['season']} | {d['store']:.0f} | {days:.1f} | "
                       f"{d['crop']:.0f} / {d['capacity']:.0f} | {d['tiles']} | "
                       f"{d.get('worked_fields', '')} |")
        out.append("")
        for h in r["harvests"]:
            share = h.get("brought_in", 0) / r["need_per_year"] if r["need_per_year"] else 0
            out.append(f"- harvest on day {h['day']}: {h.get('brought_in')} brought in, "
                       f"{share:.0%} of a year's need, called {h.get('yield')}")
        if not r["harvests"]:
            out.append("- no harvest reckoned")
        out.append(f"- fields grew {len(r['fields_grown'])} time(s)"
                   + (f", to {r['fields_grown'][-1]['tiles']} plots" if r["fields_grown"] else ""))
        out.append(f"- hungry days: {r['hungry_days'] or 'none'}")
        out.append(f"- food instructions chosen: {r['food_instructions_chosen'] or 'none'}")
        out.append(f"- the {r['adults_and_elders']} adults and elders, in working hours on dry "
                   f"days, spent their time: {r['working_hours_dry']}")
        out.append(f"- their {r['working_hours_dry_decisions']} decisions then chose most often: "
                   f"{r['working_hours_dry_chosen']}")
        out.append(f"- a tired instruction was chosen {r['tired_chosen']} times, "
                   f"{r['tired_chosen_while_rested']} of them by a villager who was not tired")
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    results = [analyse(r) for r in argv]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "food_economy.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    text = markdown(results)
    (RESULTS / "food_economy.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
