#!/usr/bin/env python3
"""How each lesson in a run that rests once carried out was used: the day it
was written, what it declared (config.declared_lessons), the times its owner
chose it, and on how many days. A lesson that rests
(config.lessons_satisfied, SPECIFICATION-memory.md sections 11 and 12) is
chosen about once on each day it is used, and one caught in a loop many times
on one day.

    python experiments/lesson_use.py <run_id> [--to-day N] [--out results/.../lesson_use.md]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKS_PER_DAY = 144
# The lessons whose goal is met once carried out, as hearthwick.memory.ONE_SHOT,
# for a lesson that declared no rhythm (experiments/health_check.py rests).
ONE_SHOT = frozenset({"talk", "warn", "go", "follow", "avoid", "wander", "play"})
MARKER = re.compile(r"\[!(\w+)\(")


def rests(lesson: dict) -> bool:
    if lesson.get("recurs"):
        return lesson["recurs"] != "always"
    kinds = set(MARKER.findall(lesson.get("content", "")))
    return bool(kinds) and kinds <= ONE_SHOT


def use(run_id: str, to_day: int | None) -> list[dict]:
    to_tick = (to_day * TICKS_PER_DAY) if to_day else 10 ** 12
    written: dict[str, tuple[str, int]] = {}
    declared: dict[str, dict] = {}
    per_day = collections.defaultdict(collections.Counter)    # lesson: day: times
    with open(ROOT / "runs" / run_id / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            if '"type": "consolidated"' not in line and '"type": "decision"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue          # a line cut short by a stop
            if e["t"] >= to_tick:
                break
            if e["type"] == "consolidated":
                for lesson in e.get("instructions") or []:
                    if rests(lesson):
                        written[lesson["id"]] = (e["character"], e["t"] // TICKS_PER_DAY)
                        declared[lesson["id"]] = {
                            "recurs": lesson.get("recurs") or "",
                            "lasts": lesson.get("lasts") or "",
                            "sources": len(lesson.get("sources") or [])}
            elif e.get("chosen") in written and e.get("character") == written[e["chosen"]][0]:
                per_day[e["chosen"]][e["t"] // TICKS_PER_DAY] += 1
    return [{"lesson": i, "villager": who, "written_day": day, **declared[i],
             "chosen": sum(per_day[i].values()), "days_chosen": len(per_day[i]),
             "most_in_a_day": max(per_day[i].values(), default=0)}
            for i, (who, day) in sorted(written.items())]


def to_markdown(run_id: str, to_day: int | None, rows: list[dict]) -> str:
    out = [f"# Lessons that rest, of {run_id}", "",
           "Made by `experiments/lesson_use.py`"
           + (f", read to day {to_day}" if to_day else "") + ".", "",
           "| lesson | written on day | recurs | lasts | facts it answers "
           "| times chosen | days chosen on | most in a day |",
           "|---|---|---|---|---|---|---|---|"]
    out += [f"| {r['lesson']} | {r['written_day']} | {r['recurs']} | {r['lasts']} "
            f"| {r['sources']} | {r['chosen']} | {r['days_chosen']} "
            f"| {r['most_in_a_day']} |" for r in rows]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    ap.add_argument("--to-day", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    text = to_markdown(args.run_id, args.to_day, use(args.run_id, args.to_day))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
