#!/usr/bin/env python3
"""Does a run show anything that looks like a bug? Reads a run's record,
events, frames and, if given, its console log, and flags what a healthy
village should not do: calls the model never answered, errors, villagers
standing idle or stuck, the granary empty for long stretches, the same news
told again and again, a villager acting on one of its one-shot lessons again
and again in a day, the same warning to the same listener again and again,
warnings that carried nothing, the live memory index growing without end,
years without births, deaths before old age.

    python experiments/health_check.py <run_id> [--log runs/long_run_vN.log]
                                       [--to-day N] [--out results/health/<run_id>]

Each check prints its figures and FLAG or ok. The limits are a healthy
village's, set from the long runs (SPECIFICATION-warnings.md sections 11 and
12, SPECIFICATION-memory.md sections 7 and 8), and a FLAG is something to look
at, not proof of a fault. Writes health_check.md and .json in --out.
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
GROWN = ("adult", "apprentice", "elder")

# Limits a healthy village stays within.
# A quick warning ends within its tick, so the frame shows its teller idle:
# about two thirds of the idle frames of the seventh long run were warnings.
IDLE_SHARE = 0.08          # of grown villagers' waking frames, idle
EMPTY_STREAK = 10          # days on end the granary is empty
EMPTY_DAYS_A_YEAR = 14     # days a year the granary is empty
# In a village of sixty to ninety, most news reaches a listener from someone
# else first, and a teller can know only what it shared itself (told memory):
# about 0.9 in every year of the seventh long run. Duplicates are caught
# before any rewording, so they cost no model call.
DUPLICATE_TELLING = 0.95   # of tellings, to someone who already had the news
SAME_TALK_A_YEAR = 50      # the same speaker, listener and topic in a year
STUCK_TICKS = 48           # a grown villager awake, still, in one activity
# Work done in one spot for hours, which is not being stuck.
STEADY = ("rest", "work", "talk", "clear", "fight_blight", "build", "fell")
YEARS_WITHOUT_BIRTH = 3    # years on end, while there are couples
OLD_AGE = 35.0             # deaths before it, in in-game years
# Times a villager chooses one of its own one-shot lessons in a day. In the
# illustrative trials an apprentice chose its warning lesson 121 times in one
# day (SPECIFICATION-memory.md section 11).
LESSON_REPEATS_A_DAY = 12
# The lessons whose goal is met once carried out, as hearthwick.memory.ONE_SHOT,
# for a lesson that declared no rhythm. One that did rests unless it declared
# "always" (SPECIFICATION-memory.md section 12).
ONE_SHOT = frozenset({"talk", "warn", "go", "follow", "avoid", "wander", "play"})
MARKER = re.compile(r"\[!(\w+)\(")
# The same warner, listener and topic in a day. A warning carrying a warner's
# old news went to the same listener up to 58 times a day in the paper-v3
# runs (SPECIFICATION-warnings.md section 13). With fresh warnings a listener
# hears of each fresh event once from each warner, two events a telling.
SAME_WARNING_A_DAY = 3
# Of a year's warnings, those that carried nothing: a decision that changed
# nothing. 14 to 18% in the first trial of fresh warnings, from a second
# warning in the same tick, and under 0.5% once it was fixed. 1 to 7% in the
# paper-v3 runs' first 56 days.
EMPTY_WARNINGS = 0.05
# One villager's warnings in a day are a figure, not a flag. They are bounded
# by how many neighbours it has and how many fresh events it knows of: in the
# second trial the most was 42, to 23 listeners about 5 events, none told
# twice. Reported over this many.
WARNINGS_A_DAY = 40


def rests(lesson: dict) -> bool:
    """Whether a lesson, as the consolidated event records it, rests once
    carried out (hearthwick.memory.MemoryIndex.recurs_of)."""
    if lesson.get("recurs"):
        return lesson["recurs"] != "always"
    kinds = set(MARKER.findall(lesson.get("content", "")))
    return bool(kinds) and kinds <= ONE_SHOT


def lines_of(path: Path, wanted: tuple[str, ...], to_tick: int):
    """The events of the wanted types, in order, up to ``to_tick``. Lines are
    filtered by text before parsing, since a long run holds billions of bytes."""
    keys = tuple(f'"type": "{w}"' for w in wanted)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not any(k in line for k in keys):
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue          # a line cut short by a stop
            if e["t"] >= to_tick:
                return
            yield e


def check(run_id: str, log: Path | None, to_day: int | None) -> dict:
    run = ROOT / "runs" / run_id
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    dpy = meta["config"]["days_per_year"]
    ticks_per_year = TICKS_PER_DAY * dpy
    to_tick = (to_day * TICKS_PER_DAY) if to_day else 10 ** 12
    checks = []

    def add(name, flagged, figures):
        checks.append({"check": name, "flag": bool(flagged), "figures": figures})

    # -- the record --------------------------------------------------------
    # A run writes the count to its record when it ends. While it runs, its
    # last checkpoint holds the count so far.
    errors, source = meta.get("speech_errors", "not recorded"), "record"
    if "speech_errors" not in meta and (run / "checkpoint.json").exists():
        errors = json.loads((run / "checkpoint.json").read_text(encoding="utf-8")).get(
            "speech_errors", "not recorded")
        source = "checkpoint, the run still going"
    add("model calls never answered", errors not in (0,),
        {"speech_errors": errors, "from": source})

    # A run asked for the embedding service but given BM25 had none when it
    # started, and its similarities mean something else. The record names
    # the embedder it used when the run ends.
    asked = meta["config"].get("embedder")
    used = (meta.get("embedder") or {}).get("kind")
    ended = bool(meta.get("finished"))
    add("the run without the embedder it asked for",
        ended and asked == "service" and used != "service",
        {"asked": asked, "used": used if ended else "not recorded until the run ends"})
    # Servers that stopped answering and were waited out
    # (SimConfig.server_wait_minutes). Waiting changes nothing in a lockstep
    # run's outcome, so these are figures, not flags.
    add("servers that stopped answering, waited out", False,
        {"model": {"outages": meta.get("speech_outages", "not recorded"),
                   "seconds": meta.get("speech_outage_seconds", "not recorded")},
         "embedder": {"outages": (meta.get("embedder") or {}).get("outages", "not recorded"),
                      "seconds": (meta.get("embedder") or {}).get("outage_seconds",
                                                                  "not recorded")}})

    # -- the console log ---------------------------------------------------
    if log is not None and log.exists():
        counts = collections.Counter()
        for line in open(log, encoding="utf-8", errors="replace"):
            for key in ("Simulation step failed", "Traceback", "Speech generation failed",
                        "Composition failed", "consolidation failed",
                        "Replacing duplicate instruction"):
                if key in line:
                    counts[key] += 1
        bad = sum(v for k, v in counts.items() if k != "Replacing duplicate instruction")
        add("errors in the console log", bad, dict(counts))

    # -- events --------------------------------------------------------------
    food = collections.defaultdict(list)
    tellings = collections.Counter()
    duplicates = collections.Counter()
    talk = collections.defaultdict(collections.Counter)
    decisions = collections.Counter()
    refused = collections.Counter()
    births = collections.Counter()
    deaths = []
    live = {}
    stages = {}
    one_shot: set[str] = set()
    lesson_days = collections.Counter()      # (day, villager, lesson): times chosen
    declared = {"recurs": collections.Counter(), "lasts": collections.Counter(),
                "answering no news": 0, "lessons": 0}
    warned_by = collections.Counter()        # (day, warner): warnings
    warned_to = collections.Counter()        # (day, warner, listener, topic): warnings
    warned_empty = collections.Counter()     # year: warnings that carried nothing
    warned_all = collections.Counter()       # year: warnings
    wanted = ("food", "diffusion", "conversation_start", "decision", "born", "died",
              "death", "memories_left_index", "consolidated", "warned")
    for e in lines_of(run / "events.jsonl", wanted, to_tick):
        y = e["t"] // ticks_per_year
        kind = e["type"]
        if kind == "food":
            food[y].append(e["store"])
        elif kind == "diffusion":
            tellings[y] += 1
            duplicates[y] += e.get("outcome") == "duplicate"
        elif kind == "conversation_start":
            people = e.get("participants") or []
            if len(people) == 2:
                talk[y][(people[0], people[1], e.get("topic"))] += 1
        elif kind == "decision":
            decisions[y] += 1
            refused[y] += bool(e.get("refused"))
            if e.get("chosen") in one_shot and e.get("character"):
                lesson_days[(e["t"] // TICKS_PER_DAY, e["character"], e["chosen"])] += 1
        elif kind == "consolidated":
            for lesson in e.get("instructions") or []:
                if rests(lesson):
                    one_shot.add(lesson["id"])
                if "declared_recurs" in lesson:
                    declared["lessons"] += 1
                    declared["recurs"][str(lesson.get("recurs"))] += 1
                    declared["lasts"][str(lesson.get("lasts"))] += 1
                    declared["answering no news"] += not lesson.get("sources")
        elif kind == "born":
            births[y] += 1
        elif kind in ("died", "death"):
            deaths.append(e)
        elif kind == "memories_left_index":
            live[y] = e["live"]
        elif kind == "warned":
            day = e["t"] // TICKS_PER_DAY
            warned_by[(day, e.get("teller"))] += 1
            warned_to[(day, e.get("teller"), e.get("receiver"), e.get("topic"))] += 1
            warned_empty[y] += not e.get("facts")
            warned_all[y] += 1

    years = sorted(set(food) | set(decisions))
    streaks, empty = {}, {}
    for y in years:
        run_len = best = 0
        for store in food[y]:
            run_len = run_len + 1 if store <= 0 else 0
            best = max(best, run_len)
        streaks[y], empty[y] = best, sum(1 for s in food[y] if s <= 0)
    add("the granary empty for long", any(v > EMPTY_STREAK for v in streaks.values())
        or any(v > EMPTY_DAYS_A_YEAR for v in empty.values()),
        {"longest empty streak by year": streaks, "empty days by year": empty})

    share = {y: round(duplicates[y] / tellings[y], 3) for y in years if tellings[y]}
    add("news told to someone who had it", any(v > DUPLICATE_TELLING for v in share.values()),
        {"share of tellings by year": share})

    most = {y: max(talk[y].values()) for y in years if talk[y]}
    worst = {y: list(talk[y].most_common(1)[0][0]) for y in years if talk[y]}
    add("the same talk again and again", any(v > SAME_TALK_A_YEAR for v in most.values()),
        {"most repeated talk a year": most, "which": worst})

    add("decisions with a refused action",
        False, {"share by year": {y: round(refused[y] / decisions[y], 3)
                                  for y in years if decisions[y]}})

    # A one-shot lesson acted on again and again in one day: its owner caught
    # in a loop rather than meeting its goal.
    top, top_who, over = {}, {}, collections.Counter()
    for (day, who, lesson), n in lesson_days.items():
        y = day * TICKS_PER_DAY // ticks_per_year
        if n > top.get(y, 0):
            top[y], top_who[y] = n, [who, lesson, day]
        over[y] += n > LESSON_REPEATS_A_DAY
    add("a one-shot lesson acted on again and again in a day",
        any(v > LESSON_REPEATS_A_DAY for v in top.values()),
        {"most times in a day, by year": top, "which (villager, lesson, day)": top_who,
         f"villager-days over {LESSON_REPEATS_A_DAY}, by year": dict(over),
         "one-shot lessons written": len(one_shot)})
    if declared["lessons"]:
        add("what lessons declared as they were written", False,
            {"lessons": declared["lessons"], "recurs": dict(declared["recurs"]),
             "lasts": dict(declared["lasts"]),
             "answering no news": declared["answering no news"]})

    # The same warning to the same listener again and again in a day, a
    # warning pumping out old news, and warnings that carried nothing.
    def by_year(counts, limit):
        """The most in a day each year, which it was, and the days over the
        limit. Each key starts with its day."""
        most, which, over = {}, {}, collections.Counter()
        for key, n in counts.items():
            y = key[0] * TICKS_PER_DAY // ticks_per_year
            if n > most.get(y, 0):
                most[y], which[y] = n, list(key)
            over[y] += n > limit
        return most, which, over
    same_most, same_which, same_over = by_year(warned_to, SAME_WARNING_A_DAY)
    add("the same warning to the same listener again and again in a day",
        any(v > SAME_WARNING_A_DAY for v in same_most.values()),
        {"most times in a day, by year": same_most,
         "which (day, warner, listener, topic)": same_which,
         f"listener-days over {SAME_WARNING_A_DAY}, by year": dict(same_over)})
    empty_share = {y: round(warned_empty[y] / warned_all[y], 3) for y in sorted(warned_all)}
    add("warnings that carried nothing", any(v > EMPTY_WARNINGS for v in empty_share.values()),
        {"share by year": empty_share, "count by year": dict(warned_empty),
         "warnings by year": dict(warned_all)})
    by_most, by_which, by_over = by_year(warned_by, WARNINGS_A_DAY)
    add("warnings by one villager in a day", False,
        {"most in a day, by year": by_most, "which (day, warner)": by_which,
         f"villager-days over {WARNINGS_A_DAY}, by year": dict(by_over)})


    # -- frames ---------------------------------------------------------------
    idle = collections.Counter()
    awake = collections.Counter()
    still: dict[str, tuple] = {}
    stuck = collections.Counter()
    examples: list[dict] = []
    alive_at_year = {}
    couples_known = meta.get("config", {}).get("fertility")
    with open(run / "frames.jsonl", encoding="utf-8") as f:
        for line in f:
            try:
                fr = json.loads(line)
            except json.JSONDecodeError:
                continue
            if fr["t"] >= to_tick:
                break
            y = fr["t"] // ticks_per_year
            if fr["t"] % ticks_per_year == 0:
                alive_at_year[y] = len(fr["c"])
            hour = fr["clock"]["hour"]
            if not 6 <= hour < 22:
                still.clear()
                continue
            for c in fr["c"]:
                cid, x, yy, act, stage = c[0], c[1], c[2], c[3], c[4]
                stages[cid] = stage
                if stage not in GROWN:
                    continue
                awake[y] += 1
                idle[y] += act == "idle"
                key = (x, yy, act)
                start, last = still.get(cid, (None, None))
                if last == key:
                    if fr["t"] - start == STUCK_TICKS and act not in STEADY:
                        stuck[y] += 1
                        examples.append({"who": cid, "doing": act, "at": [x, yy],
                                         "from_tick": start})
                else:
                    still[cid] = (fr["t"], key)
    # Per villager, since a growing village holds more memories however well
    # it forgets. Routine news leaves the index only after eight or nine
    # years, so a ten-year run is still nearing its level.
    if live:
        per = {y: round(live[y] / alive_at_year[y], 1) for y in sorted(live)
               if alive_at_year.get(y)}
        values = [per[y] for y in sorted(per)]
        growing = len(values) >= 4 and values[-1] > 1.5 * values[len(values) // 2]
        add("the live memory index growing without end", growing,
            {"live index at a year's last trim": live, "per villager": per})

    idle_share = {y: round(idle[y] / awake[y], 3) for y in sorted(awake) if awake[y]}
    add("grown villagers standing idle", any(v > IDLE_SHARE for v in idle_share.values()),
        {"idle share of waking frames by year": idle_share})
    add("grown villagers stuck in one place and activity",
        any(stuck.values()), {f"still for {STUCK_TICKS}+ waking ticks, by year": dict(stuck),
                              "first cases": examples[:5]})

    # -- people ---------------------------------------------------------------
    gap = best = 0
    for y in years[:-1]:                 # the last year is cut short
        gap = gap + 1 if births[y] == 0 else 0
        best = max(best, gap)
    add("years without a birth", best >= YEARS_WITHOUT_BIRTH and couples_known,
        {"births by year": dict(births), "longest run of years without": best,
         "people at a year's start": alive_at_year})
    young = [{"who": d.get("character"), "age": d.get("age")} for d in deaths
             if d.get("age") is not None and d["age"] < OLD_AGE]
    add("deaths before old age", bool(young), {"deaths": len(deaths), "young": young})

    return {"run": run_id, "read_to_day": to_day, "checks": checks,
            "flags": sum(c["flag"] for c in checks)}


def to_markdown(result: dict) -> str:
    out = [f"# Health check of {result['run']}", "",
           f"Made by `experiments/health_check.py`"
           + (f", read to day {result['read_to_day']}" if result["read_to_day"] else "")
           + f". {result['flags']} of {len(result['checks'])} checks flagged.", ""]
    for c in result["checks"]:
        out += [f"## {'FLAG' if c['flag'] else 'ok'}: {c['check']}", "",
                "```", json.dumps(c["figures"], indent=1), "```", ""]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--to-day", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    result = check(args.run_id, args.log, args.to_day)
    out = args.out or ROOT / "results" / "health" / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "health_check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "health_check.md").write_text(to_markdown(result), encoding="utf-8")
    for c in result["checks"]:
        print(("FLAG " if c["flag"] else "ok   ") + c["check"])
    print(f"{result['flags']} flagged; wrote {out / 'health_check.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
