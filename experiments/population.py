#!/usr/bin/env python3
"""How a run's village changed, year by year: its people, births, deaths,
marriages, couples and granary, read from the run's own log.

    python experiments/population.py <run_id> [<run_id> ...] [--out results/long_run]

It reads them from any run's events.jsonl, such as a long run's
(results/long_runs_v4/runs.txt). Visitors pass through and are never
counted. Births by family are experiments/family.py's report.

For each run:

- one row a year: the people at its start, the young among them (infants and
  children), couples, and that year's births, deaths and marriages, with the
  granary's store at the year's end
- the totals, the fewest people at any year's start, how many founders are
  alive at the end, and the generations born (a founder's child is the first
  generation, a grandchild the second)

Writes results/population.json and .md, or into another directory given with
--out, for runs that are not the paper's.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RESULTS = ROOT / "results"
YOUNG = ("infant", "child")


def day_of(t: int) -> int:
    return (6 * 60 + t * 10) // (24 * 60)


# The events the census reads. A new year starts at the first event past it,
# and every day opens with day_start, so a reader that passes only these gets
# the same rows as one that passes the whole log (experiments/long_run_report.py
# skips the rest of a 3 GB log this way).
CENSUS_TYPES = {"roster", "born", "died", "married", "stage_change", "food", "day_start"}


class Census:
    """The village counted as its log is read, one event at a time."""

    def __init__(self, per_year: int):
        self.per_year = per_year
        self.stage, self.partner, self.generation = {}, {}, {}
        self.founders: set[str] = set()
        self.alive: set[str] = set()
        self.rows: list[dict] = []
        self.year, self.granary, self.last_day = 0, None, 0
        self.counts = {"born": 0, "died": 0, "married": 0}

    def snapshot(self, y: int) -> dict:
        alive, partner = self.alive, self.partner
        couples = sum(1 for a in alive if partner.get(a) in alive) // 2
        return {"year": y, "people": len(alive),
                "young": sum(self.stage[a] in YOUNG for a in alive),
                "couples": couples, "born": 0, "died": 0, "married": 0, "granary": None}

    def see(self, e: dict) -> None:
        kind = e["type"]
        if kind == "roster" and not self.founders:
            for c in e["characters"]:
                if c.get("visitor"):
                    continue
                self.founders.add(c["id"])
                self.alive.add(c["id"])
                self.stage[c["id"]] = c["stage"]
                self.partner[c["id"]] = c.get("partner")
                self.generation[c["id"]] = 0
            self.rows.append(self.snapshot(0))
            return
        if not self.founders:
            return
        rows = self.rows
        day = day_of(e["t"])
        self.last_day = max(self.last_day, day)
        while day >= (self.year + 1) * self.per_year:      # a new year starts
            rows[-1]["granary"] = self.granary
            self.year += 1
            rows.append(self.snapshot(self.year))
        if kind == "born":
            child = e["character"]
            self.alive.add(child)
            self.stage[child] = "infant"
            self.generation[child] = 1 + max(self.generation.get(e["mother"], 0),
                                             self.generation.get(e["father"], 0))
            rows[-1]["born"] += 1
            self.counts["born"] += 1
        elif kind == "died" and e["character"] in self.alive:
            self.alive.discard(e["character"])
            rows[-1]["died"] += 1
            self.counts["died"] += 1
        elif kind == "married":
            self.partner[e["asker"]], self.partner[e["asked"]] = e["asked"], e["asker"]
            rows[-1]["married"] += 1
            self.counts["married"] += 1
        elif kind == "stage_change" and e["character"] in self.stage:
            self.stage[e["character"]] = e["now"]
        elif kind == "food":
            self.granary = round(e["store"], 1)

    def result(self, run_id: str, meta: dict) -> dict:
        rows = self.rows
        if rows:
            rows[-1]["granary"] = self.granary
        founders, alive = self.founders, self.alive
        born = [g for c, g in self.generation.items() if c not in founders]
        # The days reached, never more than planned: an open-ended run plans far
        # past where it is, and a finished one logs its last midnight as a new day.
        planned = (meta.get("plan") or {}).get("days")
        days = min(planned, self.last_day + 1) if planned else self.last_day + 1
        return {"run": run_id, "days": round(days), "days_per_year": self.per_year,
                "rows": rows, "start": len(founders), "end": len(alive), **self.counts,
                "fewest": min((r["people"] for r in rows), default=0),
                "founders_alive": len(founders & alive),
                "generations": {str(g): born.count(g) for g in sorted(set(born))}}


def per_year_of(meta: dict) -> int:
    return int((meta.get("config") or {}).get("days_per_year", 8))


def analyse(run_id: str) -> dict:
    run = RUNS / run_id
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    census = Census(per_year_of(meta))
    with open(run / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            census.see(json.loads(line))
    return census.result(run_id, meta)


def markdown(results: list[dict]) -> str:
    out = ["# The village year by year", "",
           f"{len(results)} run(s). Generated by `experiments/population.py` on "
           f"{date.today().isoformat()}. Visitors are not counted.", ""]
    for r in results:
        gens = ", ".join(f"generation {g}: {n}" for g, n in r["generations"].items()) or "none"
        out += [f"## {r['run']}", "",
                f"- {r['days']} days at {r['days_per_year']} a year",
                f"- people: {r['start']} at the start, {r['end']} at the end, "
                f"fewest at a year's start {r['fewest']}",
                f"- births {r['born']}, deaths {r['died']}, marriages {r['married']}",
                f"- founders alive at the end: {r['founders_alive']} of {r['start']}",
                f"- born, by generation: {gens}", "",
                "| year | people | young | couples | born | died | married | granary at year's end |",
                "|---|---|---|---|---|---|---|---|"]
        for row in r["rows"]:
            out.append(f"| {row['year']} | {row['people']} | {row['young']} | {row['couples']} | "
                       f"{row['born']} | {row['died']} | {row['married']} | {row['granary']} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    out = RESULTS
    if "--out" in argv:
        i = argv.index("--out")
        out = Path(argv[i + 1]) if Path(argv[i + 1]).is_absolute() else ROOT / argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 2
    results = [analyse(r) for r in argv]
    out.mkdir(parents=True, exist_ok=True)
    (out / "population.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    text = markdown(results)
    (out / "population.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
