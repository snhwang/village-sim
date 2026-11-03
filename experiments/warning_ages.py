#!/usr/bin/env python3
"""How old is the news warnings pass on? For every fact a warning carried:
how old its event was (the warning's tick less the tick in the fact's root)
and how long its warner had held it (less the tick the warner learned it),
by the instruction that chose the warning.

    python experiments/warning_ages.py <run_id> [--to-day N] [--out DIR]

Found with the paper-v4 ten-year runs (SPECIFICATION-warnings.md sections 13
and 14): a villager holds news as fresh for a week from when it heard it, so
storytellers' tales months old still went out as warnings of danger abroad,
though nearly all had been learned by their warner within the week. For a
danger in the village (the well, the blight, the road) the event's age says
less, since the danger living again restarts an old fact's clock without a
new root. Writes warning_ages.json in --out when given.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKS_PER_DAY = 144


def root_tick(root: str | None, fallback: int) -> int:
    parts = (root or "").split(":")
    try:
        return int(parts[2].split("-")[0]) if len(parts) > 2 else fallback
    except ValueError:
        return fallback


def ages(run_id: str, to_day: int | None) -> dict:
    to_tick = to_day * TICKS_PER_DAY if to_day else 10 ** 12
    learned: dict[str, tuple[int, int]] = {}      # fact id -> (event tick, tick learned)
    by = collections.defaultdict(collections.Counter)
    with open(ROOT / "runs" / run_id / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            if '"knowledge_stored"' in line:
                e = json.loads(line)
                learned[e["id"]] = (root_tick(e.get("root"), e["t"]), e["t"])
            elif '"type": "warned"' in line:
                e = json.loads(line)
                if e["t"] >= to_tick:
                    break
                inst = e.get("instruction") or "-"
                inst = "learned lessons" if inst.startswith("learned-") else inst
                for fid in e.get("facts") or []:
                    if fid not in learned:
                        continue
                    born, got = learned[fid]
                    age, held = (e["t"] - born) / TICKS_PER_DAY, (e["t"] - got) / TICKS_PER_DAY
                    b = by[inst]
                    b["facts"] += 1
                    b["event over 7 days old"] += age > 7
                    b["event over 28 days old"] += age > 28
                    b["held over 7 days"] += held > 7
    out = {}
    for inst, b in sorted(by.items(), key=lambda kv: -kv[1]["facts"]):
        n = b["facts"]
        out[inst] = {"facts": n, **{k: round(100 * v / n, 1) for k, v in b.items() if k != "facts"}}
    return {"run": run_id, "read_to_day": to_day, "percent_of_facts_by_instruction": out}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    ap.add_argument("--to-day", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    result = ages(args.run_id, args.to_day)
    for inst, r in result["percent_of_facts_by_instruction"].items():
        print(f"{inst:28s} facts {r['facts']:7d}  event over 7 days old {r['event over 7 days old']:5.1f}%"
              f"  over 28 days {r['event over 28 days old']:5.1f}%"
              f"  held over 7 days {r['held over 7 days']:5.1f}%")
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "warning_ages.json").write_text(json.dumps(result, indent=2) + "\n",
                                                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
