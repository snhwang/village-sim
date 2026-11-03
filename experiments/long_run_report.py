#!/usr/bin/env python3
"""The long run in detail: its people, trades and houses, and the lessons its
villagers wrote for themselves, with why most were refused.

    python experiments/long_run_report.py <run_id> [--to-day N] [--out results/long_run]

The numbers behind results/long_run/REPORT.md. It reads the run's meta.json,
and its events.jsonl once, up to the size the log had when the script
started, or to the start of day N. A run that is still going grows while it is
read, and --to-day lets a later reading give the same numbers. The long run's
log is over 3 GB, so only the events counted here are parsed, and decisions
are read by pattern.

What it measures:

- the run: its builds, model, switches and resumptions
- the village year by year (experiments/population.py's census), and its
  steady state, with intervals from batch means over the steady years
- lifespans, the way from a moment a couple could have a child to a birth,
  conception, and births per family
- careers: a parent's trade, a parent as master, new masters after a death
- houses, sales, blights and visitors
- the lessons villagers wrote at each stage change (hearthwick/consolidation.py):
  how many, which markers, why the check refused most, and how often the
  accepted ones were chosen

One run, so its intervals come from within it. Yearly rates use batch means
over the steady years, which allows for one year leaning on the next.
Proportions use a bootstrap over couples or families, since one couple's
tries are not independent of each other. Genotypes are never read.

Writes long_run_report.json and long_run_report.md in --out.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
import statistics
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from population import CENSUS_TYPES, RUNS, Census, day_of, per_year_of  # noqa: E402

from hearthwick.consolidation import REQUIRED, SWITCHED_MARKERS, offered_markers  # noqa: E402
from hearthwick.events import code_versions  # noqa: E402

# The events parsed in full. Every other type is only counted.
PARSED = CENSUS_TYPES | {
    "tried_for_child", "apprenticed", "took_up_trade", "new_master", "house_built",
    "consolidated", "consolidation_refused", "resumed", "sold", "world_event",
    "proposed", "declined", "warned"}

_TYPE = re.compile(rb'"type": "([a-z_]+)"')
_TICK = re.compile(rb'^\{"t": (\d+)')
_CHOSEN = re.compile(rb'"chosen": "([^"]*)"')
_LEARNED = re.compile(rb'"id": "(learned-[^"]+)"')
_TAGS = re.compile(rb'"tags": \[([^\]]*)\]')
_MARKER = re.compile(r"\[!(\w+)")
_FACT_ID = re.compile(rb'"id": "([^"]+)"')
_ROOT = re.compile(rb'"root": "([^"]+)"')

# The have-child instruction's gate (data/instructions/family), so a decision
# carrying all three is a moment the couple could have chosen a child.
CHILD_GATE = (b'"daytime"', b'"fertile"', b'"partner_home"')
HAVE_CHILD = "family-have-child"
_HAVE_CHILD_ID = b'"id": "family-have-child"'

# The check's reasons (consolidation.executable), from most to least common in
# the long run. It names only the first fault it finds in an instruction.
REFUSALS = [
    ("wrong argument name", re.compile(r"^\[!(\w+)\] was given \[(.*)\], which it does not read")),
    ("required argument missing", re.compile(r"^\[!(\w+)\] has no (\w+), so it cannot act")),
    ("names someone not in the village", re.compile(r"^\[!(\w+)\] names (.+), who is not anyone")),
    ("names a place not in the village", re.compile(r"^\[!(\w+)\] names (.+), which is not a place")),
    ("a marker the village does not have", re.compile(r"^\[!(\w+)\] is not a marker")),
    ("a switched-off mechanic's marker", re.compile(r"^\[!(\w+)\] belongs to a mechanic")),
    ("no action marker", re.compile(r"^no action marker")),
]

BATCH_YEARS = 5
PLATEAU_SHARE = 0.95     # the steady state starts when people first reach this share
TAIL_YEARS = 10          # of the mean over the last ten full years
FLAT = 0.2               # which may span no more than this share of their mean
BOOT = 2000
# Two-sided 95% points of Student's t, by degrees of freedom.
T95 = [None, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
       2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086]


def batch_means(values: list[float], size: int = BATCH_YEARS) -> dict | None:
    """Mean and 95% interval from means of consecutive batches of years."""
    n = len(values) // size
    if n < 2:
        return None
    values = values[len(values) - n * size:]           # the earliest leftover years go
    means = [statistics.fmean(values[i * size:(i + 1) * size]) for i in range(n)]
    m = statistics.fmean(means)
    half = (T95[n - 1] if n - 1 < len(T95) else 1.96) * statistics.stdev(means) / math.sqrt(n)
    return {"mean": round(m, 2), "low": round(m - half, 2), "high": round(m + half, 2),
            "batches": n, "years": n * size}


def lag1(values: list[float]) -> float | None:
    if len(values) < 3 or statistics.pvariance(values) == 0:
        return None
    m = statistics.fmean(values)
    num = sum((a - m) * (b - m) for a, b in zip(values, values[1:]))
    return round(num / sum((v - m) ** 2 for v in values), 2)


def cluster_share(clusters: list[tuple[int, int]], seed: int = 0) -> dict:
    """A pooled share and its 95% percentile interval, resampling clusters."""
    hits, trials = sum(a for a, _ in clusters), sum(b for _, b in clusters)
    rng, k, shares = random.Random(seed), len(clusters), []
    for _ in range(BOOT):
        s = t = 0
        for _ in range(k):
            a, b = clusters[rng.randrange(k)]
            s, t = s + a, t + b
        shares.append(s / t if t else 0.0)
    shares.sort()
    return {"hits": hits, "of": trials, "share": round(hits / trials, 3) if trials else None,
            "low": round(shares[int(0.025 * BOOT)], 3), "high": round(shares[int(0.975 * BOOT) - 1], 3),
            "clusters": k}


def quartiles(values: list[float]) -> dict:
    if len(values) < 2:
        return {"n": len(values)}
    q = statistics.quantiles(values, n=4)
    return {"n": len(values), "mean": round(statistics.fmean(values), 1),
            "q1": round(q[0], 1), "median": round(q[1], 1), "q3": round(q[2], 1)}


def refusal_kind(why: str) -> tuple[str, list[str]]:
    """The kind of fault, and what it was about, such as [!avoid(site=…)]."""
    for kind, pattern in REFUSALS:
        m = pattern.match(why)
        if not m:
            continue
        if kind == "wrong argument name":
            return kind, [f"[!{m[1]}({a}=…)]" for a in re.findall(r"'([^']*)'", m[2])]
        if kind == "required argument missing":
            return kind, [f"[!{m[1]}] without {m[2]}"]
        if kind.startswith("names"):
            return kind, [m[2].strip("'\"")]
        if kind == "no action marker":
            return kind, ["(none)"]
        return kind, [f"[!{m[1]}]"]
    return "other", [why]


def read(run_id: str, to_day: int | None = None, runs: Path = RUNS) -> dict:
    run = runs / run_id
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    config = meta.get("config") or {}
    per_year = per_year_of(meta)
    census = Census(per_year)
    offered = set(offered_markers(SimpleNamespace(**config)))
    # The markers of a mechanic this run had switched off. A mechanic added
    # after the run began has no switch in its config, and its markers did not
    # exist for it.
    switched_off = {m for m, needed in SWITCHED_MARKERS.items() if m not in offered
                    and all(k in config for k in ((needed,) if isinstance(needed, str) else needed))}

    def year_of(t: int) -> int:
        return day_of(t) // per_year

    types = collections.Counter()
    resumed, sold = [], [0, 0.0]
    world = collections.Counter()
    proposals = {"proposed": 0, "declined": 0}
    # children
    parents: dict[str, tuple[str, str]] = {}
    tries: dict[tuple, list[int]] = collections.defaultdict(lambda: [0, 0])
    funnel = collections.defaultdict(collections.Counter)      # decade -> stage -> n
    yearly = collections.defaultdict(collections.Counter)      # year -> what villagers did
    warned_by = collections.Counter()           # instruction behind each warning decision
    root_of: dict[str, str] = {}                # fact id -> the kind of event it came from
    passed_on = collections.Counter()           # what quick warnings passed on, by event
    instead = collections.defaultdict(collections.Counter)     # decade -> what was chosen
    married_at: dict[tuple, int] = {}
    waits: list[float] = []
    houses = 0
    # trades
    trade: dict[str, str] = {}
    apprenticeships, master_deaths = [], {"masters": 0, "apprentices": 0, "reassigned": 0}
    new_masters = 0
    deaths: list[tuple[int, float]] = []
    # lessons
    written: list[dict] = []
    stage_changes = 0
    consolidations = {"accepted some": 0, "all refused": 0}
    chosen = collections.Counter()
    candidate = collections.Counter()
    decisions = collections.Counter()           # decade -> decisions
    learned_choices = collections.Counter()     # decade -> decisions that chose a lesson
    last_t = 0

    path = run / "events.jsonl"
    size = path.stat().st_size
    seen = 0
    # The first tick of day to_day, where reading stops (population.day_of).
    stop = None if to_day is None else 144 * to_day - 36
    with open(path, "rb") as f:
        for raw in f:
            seen += len(raw)
            if seen > size or not raw.endswith(b"\n"):
                break                           # past where the log was when we began
            tick = _TICK.match(raw)
            if stop is not None and tick and int(tick[1]) >= stop:
                break
            m = _TYPE.search(raw, 0, 80)
            if not m:
                continue
            kind = m[1].decode()
            types[kind] += 1
            if kind == "decision":
                t = int(tick[1])
                last_t = max(last_t, t)
                decade = year_of(t) // 10
                decisions[decade] += 1
                c = _CHOSEN.search(raw)
                name = c[1].decode() if c else None
                year = yearly[year_of(t)]
                year["decisions"] += 1
                acts = raw[raw.find(b'"actions"'):]
                warns = b'"kind": "warn"' in acts
                year["warn"] += warns
                if warns:
                    warned_by["lessons villagers wrote" if (name or "").startswith("learned-")
                              else name] += 1
                year["field work"] += b'"kind": "work"' in acts and b'fields' in acts[:400]
                year["lesson"] += bool(name and name.startswith("learned-"))
                for lid in set(_LEARNED.findall(raw)):
                    candidate[lid.decode()] += 1
                if name and name.startswith("learned-"):
                    chosen[name] += 1
                    learned_choices[decade] += 1
                tags = _TAGS.search(raw)
                if tags and all(g in tags[1] for g in CHILD_GATE):
                    stage = "elder" if b'"stage_elder"' in tags[1] else "adult"
                    funnel[decade]["could choose a child"] += 1
                    funnel[decade][f"could, as {stage}"] += 1
                    funnel[decade]["a candidate"] += _HAVE_CHILD_ID in raw
                    if name == HAVE_CHILD:
                        funnel[decade]["chose a child"] += 1
                        funnel[decade][f"chose, as {stage}"] += 1
                    else:
                        instead[decade][name] += 1
                continue
            if kind == "knowledge_stored":
                fid, root = _FACT_ID.search(raw), _ROOT.search(raw)
                if fid and root:
                    root_of[fid[1].decode()] = root[1].decode().split(":")[0]
                continue
            if kind not in PARSED:
                continue
            e = json.loads(raw)
            t = e["t"]
            last_t = max(last_t, t)
            if kind in CENSUS_TYPES:
                census.see(e)
            if kind == "food":
                year = yearly[year_of(t)]
                year["days"] += 1
                year["worked fields"] += e.get("worked_fields") or 0
                year["need"] += e.get("need") or 0
                year["largest crop"] = max(year["largest crop"], e.get("crop") or 0)
            decade = year_of(t) // 10
            if kind == "roster" and not trade:
                for c in e["characters"]:
                    if not c.get("visitor"):
                        trade[c["id"]] = c.get("role")
            elif kind == "born":
                parents[e["character"]] = (e["mother"], e["father"])
                funnel[decade]["born"] += 1
            elif kind == "died":
                deaths.append((t, e["age"]))
                moved = e.get("apprentices") or {}
                if moved:
                    master_deaths["masters"] += 1
                    master_deaths["apprentices"] += len(moved)
                    master_deaths["reassigned"] += sum(1 for v in moved.values() if v)
            elif kind == "stage_change":
                stage_changes += 1
            elif kind == "tried_for_child":
                couple = tuple(e["couple"])
                tries[couple][1] += 1
                tries[couple][0] += bool(e.get("conceived"))
                funnel[decade]["tried"] += 1
                funnel[decade]["conceived"] += bool(e.get("conceived"))
            elif kind == "married":
                if e.get("waiting"):
                    married_at[tuple(sorted((e["asker"], e["asked"])))] = t
            elif kind == "house_built":
                houses += 1
                couple = tuple(sorted(e.get("couple") or ()))
                if couple in married_at:
                    waits.append((t - married_at.pop(couple)) / 144 / per_year)
            elif kind == "took_up_trade":
                trade[e["character"]] = e["trade"]
            elif kind == "apprenticed":
                who = e["character"]
                if who in parents:
                    mum, dad = parents[who]
                    apprenticeships.append({
                        "family": (mum, dad), "trade": e["trade"],
                        "parent_trade": e["trade"] in {trade.get(mum), trade.get(dad)},
                        "under_parent": e["master"] in (mum, dad)})
                else:
                    apprenticeships.append({"family": None, "trade": e["trade"]})
            elif kind == "new_master":
                new_masters += 1
            elif kind in ("consolidated", "consolidation_refused"):
                consolidations["accepted some" if kind == "consolidated" else "all refused"] += 1
                base = {"author": e["character"], "became": e["became"], "t": t}
                for i in e.get("instructions") or []:
                    written.append({**base, "id": i["id"], "content": i["content"],
                                    "accepted": True, "scope": i.get("scope") or []})
                for r in e.get("refused") or []:
                    written.append({**base, "id": r["id"], "content": r["content"],
                                    "accepted": False, "why": r["why"]})
            elif kind == "resumed":
                resumed.append({"t": t, "learned": e.get("learned")})
            elif kind == "sold":
                sold[0] += 1
                sold[1] += e.get("coins") or 0.0
            elif kind == "world_event":
                world[e.get("event")] += 1
            elif kind in proposals:
                proposals[kind] += 1
            elif kind == "warned":
                passed_on.update(root_of.get(f, "unknown") for f in e.get("facts") or [])

    pop = census.result(run_id, meta)
    return {"meta": meta, "offered": offered, "switched_off": switched_off,"types": types, "last_t": last_t, "pop": pop,
            "resumed": resumed, "sold": sold, "world": world, "proposals": proposals,
            "parents": parents, "tries": tries, "funnel": funnel, "instead": instead,
            "yearly": yearly, "warned_by": warned_by, "passed_on": passed_on,
            "waits": waits,
            "unhoused": len(married_at), "houses": houses, "apprenticeships": apprenticeships,
            "master_deaths": master_deaths, "new_masters": new_masters, "deaths": deaths,
            "written": written, "stage_changes": stage_changes,
            "consolidations": consolidations, "chosen": chosen, "candidate": candidate,
            "decisions": decisions, "learned_choices": learned_choices,
            "year_of": year_of, "to_day": to_day}


def summarise(run_id: str, r: dict) -> dict:
    meta, pop, year_of = r["meta"], r["pop"], r["year_of"]
    config = meta.get("config") or {}
    per_year = pop["days_per_year"]
    last_day = day_of(r["last_t"])
    # The year under way is not full, unless reading stopped where a year begins.
    reached = r["to_day"] and last_day + 1 >= r["to_day"]
    full_years = (r["to_day"] if reached else last_day) // per_year
    rows = [row for row in pop["rows"] if row["year"] < full_years]

    # The run
    switches = {k: v for k, v in sorted(config.items()) if isinstance(v, bool)}
    out = {"run": run_id, "date": date.today().isoformat(), "generated_with": code_versions(),
           "read_to": {"tick": r["last_t"], "day": last_day, "year": last_day // per_year,
                       "full_years": full_years, "events": sum(r["types"].values())},
           "started": meta.get("started"), "code": meta.get("code"),
           "resumptions": [{**x, "at": m.get("at"), "code": m.get("code")}
                           for x, m in zip(r["resumed"], meta.get("resumed") or [])],
           "model": (meta.get("speech_model") or {}).get("model"),
           "days_per_year": per_year,
           "switches_on": [k for k, v in switches.items() if v],
           "switches_off": [k for k, v in switches.items() if not v],
           "events": dict(r["types"].most_common())}

    # The village, and its steady state
    tail = [row["people"] for row in rows[-TAIL_YEARS:]]
    steady = None
    level = statistics.fmean(tail) if tail else 0
    # Only a village still there and level over its last years has one.
    if len(rows) >= 2 * TAIL_YEARS and level > 0 and max(tail) - min(tail) <= FLAT * level:
        start = next(row["year"] for row in rows if row["people"] >= PLATEAU_SHARE * level)
        years = [row for row in rows if row["year"] >= start]
        ages = [age for t, age in r["deaths"] if year_of(t) >= start and year_of(t) < full_years]
        steady = {"from_year": start, "to_year": full_years - 1, "years": len(years),
                  "tail_mean_people": round(level, 1)}
        for key in ("people", "born", "died", "married"):
            series = [row[key] for row in years]
            steady[key] = batch_means(series)
            if steady[key]:
                steady[key]["lag1"] = lag1(series)
        steady["age_at_death"] = quartiles(ages)
        if steady["born"] and ages:
            # A steady population is births a year times the mean lifespan
            # (Little's law), with no one arriving or leaving for good.
            steady["births_times_lifespan"] = round(steady["born"]["mean"] * statistics.fmean(ages), 1)
    out["village"] = {k: pop[k] for k in ("start", "end", "born", "died", "married", "fewest",
                                            "founders_alive", "generations")}
    out["years"] = pop["rows"]
    out["steady"] = steady
    out["age_at_death"] = quartiles([age for _, age in r["deaths"]])

    # Children
    decades = sorted(set(r["funnel"]) | set(r["decisions"]))
    couples_by_decade = collections.defaultdict(list)
    for row in rows:
        couples_by_decade[row["year"] // 10].append(row["couples"])
    out["children"] = {
        "funnel": [{"decade": f"{10 * d}-{10 * d + 9}",
                    "couples": round(statistics.fmean(couples_by_decade[d]), 1)
                    if couples_by_decade[d] else None,
                    **{k: r["funnel"][d][k] for k in (
                        "could choose a child", "a candidate", "chose a child", "tried",
                        "conceived", "born", "could, as adult", "chose, as adult",
                        "could, as elder", "chose, as elder")},
                    "chosen instead": r["instead"][d].most_common(5)}
                   for d in decades],
        "conception": cluster_share([tuple(v) for v in r["tries"].values()]),
        "per_family": dict(sorted(collections.Counter(
            collections.Counter(r["parents"].values()).values()).items())),
        "families": len(set(r["parents"].values())),
        "proposals": r["proposals"], "houses_built": r["houses"],
        "waited_for_a_house": quartiles(r["waits"]), "still_waiting": r["unhoused"]}

    # Trades
    born_here = [a for a in r["apprenticeships"] if a["family"]]
    by_family = collections.defaultdict(lambda: [0, 0, 0])
    for a in born_here:
        f = by_family[a["family"]]
        f[0] += a["parent_trade"]
        f[1] += a["under_parent"]
        f[2] += 1
    out["trades"] = {
        "apprenticeships": len(r["apprenticeships"]), "born_here": len(born_here),
        "parent_trade": cluster_share([(f[0], f[2]) for f in by_family.values()]),
        "under_parent": cluster_share([(f[1], f[2]) for f in by_family.values()]),
        "chosen": dict(collections.Counter(a["trade"] for a in born_here).most_common()),
        "master_deaths": r["master_deaths"], "new_master_events": r["new_masters"]}

    # What villagers did with their time, and what the fields gave
    def frac(n, of):
        return round(n / of, 3) if of else None
    out["by_year"] = [
        {"year": y, "decisions": v["decisions"],
         "warn": frac(v["warn"], v["decisions"]),
         "lesson": frac(v["lesson"], v["decisions"]),
         "field work": frac(v["field work"], v["decisions"]),
         "worked fields": round(v["worked fields"] / v["days"], 1) if v["days"] else None,
         "need": round(v["need"] / v["days"], 1) if v["days"] else None,
         "largest crop": round(v["largest crop"])}
        for y, v in sorted(r["yearly"].items())]

    # Warnings: what chose them, and what quick warnings passed on, by the kind
    # of event the news came from (a storyteller's tale, a traveller, a raid)
    out["warnings"] = {"decisions": sum(r["warned_by"].values()),
                       "by_instruction": r["warned_by"].most_common(10),
                       "passed_on": r["passed_on"].most_common(12)}

    # The world
    out["world"] = {"sales": r["sold"][0], "coins": round(r["sold"][1], 1),
                    "world_events": dict(r["world"].most_common())}

    # Lessons
    written, offered = r["written"], r["offered"]
    accepted = [w for w in written if w["accepted"]]
    refused = [w for w in written if not w["accepted"]]
    kinds, details = collections.Counter(), collections.defaultdict(collections.Counter)
    for w in refused:
        kind, about = refusal_kind(w["why"])
        w["kind"] = kind
        kinds[kind] += 1
        details[kind].update(about)
    markers = collections.defaultdict(lambda: [0, 0])
    for w in written:
        w["markers"] = sorted(set(_MARKER.findall(w["content"])))
        for mk in w["markers"]:
            markers[mk][0 if w["accepted"] else 1] += 1
    switched_off = r["switched_off"]
    off =[w for w in written if set(w["markers"]) & switched_off]
    # Whether a lesson needed the model to name something: a marker with a
    # required argument (consolidation.REQUIRED).
    needs = collections.defaultdict(lambda: [0, 0])
    for w in written:
        key = "needs an argument" if set(w["markers"]) & set(REQUIRED) else "needs none"
        if not w["markers"]:
            key = "no marker"
        needs[key][0 if w["accepted"] else 1] += 1
    by_stage = collections.defaultdict(lambda: [0, 0])
    by_decade = collections.defaultdict(lambda: [0, 0])
    for w in written:
        by_stage[w["became"]][0 if w["accepted"] else 1] += 1
        by_decade[year_of(w["t"]) // 10][0 if w["accepted"] else 1] += 1
    rng = random.Random(0)
    examples = {kind: [{"content": w["content"], "why": w["why"], "author": w["author"],
                        "became": w["became"]}
                       for w in rng.sample([w for w in refused if w["kind"] == kind],
                                           min(2, kinds[kind]))]
                for kind, _ in kinds.most_common()}
    out["lessons"] = {
        "stage_changes": r["stage_changes"], "consolidations": r["consolidations"],
        "written": len(written), "accepted": len(accepted), "refused": len(refused),
        "refused_share": round(len(refused) / len(written), 3) if written else None,
        "why_refused": [{"kind": k, "n": n, "share": round(n / len(refused), 3),
                         "most_common": details[k].most_common(8)}
                        for k, n in kinds.most_common()],
        "by_stage": {k: {"accepted": v[0], "refused": v[1]} for k, v in sorted(by_stage.items())},
        "by_decade": [{"decade": f"{10 * d}-{10 * d + 9}", "accepted": v[0], "refused": v[1]}
                      for d, v in sorted(by_decade.items())],
        "markers": [{"marker": mk, "accepted": v[0], "refused": v[1],
                     "in this run": ("on" if mk in offered else
                                     "switched off" if mk in switched_off else "not a marker"),
                     "required": REQUIRED.get(mk)}
                    for mk, v in sorted(markers.items(), key=lambda kv: -sum(kv[1]))],
        "needs_an_argument": {k: {"accepted": v[0], "refused": v[1]}
                              for k, v in sorted(needs.items())},
        "switched_off_marker": {"written": len(off), "accepted": sum(w["accepted"] for w in off),
                                "markers": dict(collections.Counter(
                                    mk for w in off for mk in w["markers"] if mk in switched_off)),
                                "accepted_examples": [
                                    {"id": w["id"], "author": w["author"], "content": w["content"]}
                                    for w in off if w["accepted"]][:3]},
        "refused_examples": examples}

    # How the accepted lessons were used
    by_id = {w["id"]: w for w in accepted}
    chosen, candidate = r["chosen"], r["candidate"]
    did = collections.Counter()
    for lid, n in chosen.items():
        for mk in (by_id.get(lid) or {}).get("markers", []):
            did[mk] += n
    never = [w for w in accepted if not chosen[w["id"]]]
    out["use"] = {
        "accepted": len(accepted),
        "ever_a_candidate": sum(1 for w in accepted if candidate[w["id"]]),
        "ever_chosen": sum(1 for w in accepted if chosen[w["id"]]),
        "choices": sum(chosen.values()),
        "decisions": sum(r["decisions"].values()),
        "unknown_ids_chosen": sum(n for lid, n in chosen.items() if lid not in by_id),
        "by_decade": [{"decade": f"{10 * d}-{10 * d + 9}", "decisions": r["decisions"][d],
                       "chose a lesson": r["learned_choices"][d]} for d in sorted(r["decisions"])],
        "markers_chosen": dict(did.most_common()),
        "most_chosen": [{"id": lid, "n": n, "candidate": candidate[lid],
                         "author": by_id[lid]["author"], "became": by_id[lid]["became"],
                         "content": by_id[lid]["content"]}
                        for lid, n in chosen.most_common(8) if lid in by_id],
        "never_chosen_examples": [{"id": w["id"], "author": w["author"], "became": w["became"],
                                   "candidate": candidate[w["id"]], "content": w["content"]}
                                  for w in random.Random(1).sample(never, min(3, len(never)))]}
    return out


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def interval(b: dict | None, unit: str = "") -> str:
    if not b:
        return "too few years"
    return (f"{b['mean']}{unit} (95% interval {b['low']} to {b['high']}, {b['batches']} batches "
            f"of {BATCH_YEARS} years, lag-1 autocorrelation {b.get('lag1')})")


def share(s: dict) -> str:
    return (f"{s['hits']} of {s['of']}, {pct(s['share'])} (95% interval {pct(s['low'])} "
            f"to {pct(s['high'])}, resampling {s['clusters']} clusters)")


def markdown(s: dict) -> str:
    rt = s["read_to"]
    out = ["# The long run in detail", "",
           f"Run `{s['run']}`, read to tick {rt['tick']} (day {rt['day']}, year {rt['year']}, "
           f"{rt['full_years']} full years, {rt['events']:,} events). Generated by "
           f"`experiments/long_run_report.py` on {s['date']}, at Hearthwick "
           f"{s['generated_with']['hearthwick']}"
           + (f", with `--to-day {s['to_day']}`." if s.get("to_day") else "."), "",
           "## The run", "",
           f"- started {s['started']} on Hearthwick {s['code']['hearthwick']} with BEAR "
           f"{s['code']['bear']}"]
    for x in s["resumptions"]:
        out.append(f"- resumed at tick {x['t']} on {x['at']}, on Hearthwick "
                   f"{x['code']['hearthwick']} with BEAR {x['code']['bear']}, "
                   f"with {x['learned']} learned instructions restored")
    out += [f"- speech by {s['model']}, {s['days_per_year']} days a year",
            f"- switches on: {', '.join(s['switches_on'])}",
            f"- switches off: {', '.join(s['switches_off'])}", "",
            "## The village", ""]
    v = s["village"]
    gens = ", ".join(f"generation {g}: {n}" for g, n in v["generations"].items())
    out += [f"- people: {v['start']} at the start, {v['end']} now, fewest at a year's start "
            f"{v['fewest']}",
            f"- births {v['born']}, deaths {v['died']}, marriages {v['married']}",
            f"- founders alive: {v['founders_alive']} of {v['start']}",
            f"- born, by generation: {gens}",
            f"- age at death, all {s['age_at_death']['n']} deaths: mean "
            f"{s['age_at_death'].get('mean')}, median {s['age_at_death'].get('median')}, "
            f"quartiles {s['age_at_death'].get('q1')} and {s['age_at_death'].get('q3')} years", ""]
    st = s["steady"]
    if not st:
        out += [f"No steady state: the last {TAIL_YEARS} full years are missing, empty, or span "
                f"more than {int(100 * FLAT)}% of their mean.", ""]
    else:
        a = st["age_at_death"]
        out += ["### The steady state", "",
                f"From year {st['from_year']}, the first year whose people reached "
                f"{int(100 * PLATEAU_SHARE)}% of the mean over the last {TAIL_YEARS} full years "
                f"({st['tail_mean_people']}), to year {st['to_year']}.", "",
                f"- people at a year's start: {interval(st['people'])}",
                f"- births a year: {interval(st['born'])}",
                f"- deaths a year: {interval(st['died'])}",
                f"- marriages a year: {interval(st['married'])}",
                f"- age at death, {a['n']} deaths: mean {a.get('mean')}, median "
                f"{a.get('median')}, quartiles {a.get('q1')} and {a.get('q3')} years",
                f"- births a year times the mean age at death: "
                f"{st.get('births_times_lifespan')} people", ""]
    out += ["### Year by year", "",
            "| year | people | young | couples | born | died | married | granary at year's end |",
            "|---|---|---|---|---|---|---|---|"]
    for row in s["years"]:
        out.append(f"| {row['year']} | {row['people']} | {row['young']} | {row['couples']} | "
                   f"{row['born']} | {row['died']} | {row['married']} | {row['granary']} |")
    c = s["children"]
    out += ["", "## Children", "",
            "From a moment a couple could have chosen a child (a decision carrying the "
            "have-child instruction's gate of daytime, fertile and partner_home) to a birth. "
            "Couples are the mean at a year's start.", "",
            "| years | couples | could choose a child | it was a candidate | chose a child | "
            "chose, per moment | tried | tried, per choice | conceived | born |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for f in c["funnel"]:
        could, chose = f["could choose a child"], f["chose a child"]
        out.append(f"| {f['decade']} | {f['couples']} | {could} | "
                   f"{f['a candidate']} | {chose} | "
                   f"{pct(chose / could if could else None)} | {f['tried']} | "
                   f"{pct(f['tried'] / chose if chose else None)} | "
                   f"{f['conceived']} | {f['born']} |")
    out += ["", "The same moments by the stage of the one deciding, and what was chosen instead "
            "of a child:", "",
            "| years | could, as adult | chose, as adult | could, as elder | chose, as elder | "
            "chosen instead, most often |", "|---|---|---|---|---|---|"]
    for f in c["funnel"]:
        instead = ", ".join(f"{name} {n}" for name, n in f["chosen instead"])
        out.append(f"| {f['decade']} | {f['could, as adult']} | {f['chose, as adult']} | "
                   f"{f['could, as elder']} | {f['chose, as elder']} | {instead} |")
    per_family = ", ".join(f"{k} children: {n}" for k, n in c["per_family"].items())
    w = c["waited_for_a_house"]
    waited = (f"median {w['median']} years (quartiles {w['q1']} and {w['q3']}) over {w['n']} couples"
              if w["n"] >= 2 else f"{w['n']} couples")
    out += ["",
            f"- conception per try: {share(c['conception'])}",
            f"- births per family, over {c['families']} families: {per_family}",
            f"- proposals {c['proposals']['proposed']}, declined {c['proposals']['declined']}",
            f"- houses built {c['houses_built']}. Couples who married without a house of their "
            f"own waited for one {waited}, and {c['still_waiting']} are still waiting", ""]
    tr = s["trades"]
    md = tr["master_deaths"]
    out += ["## Trades", "",
            f"- apprenticeships {tr['apprenticeships']}, {tr['born_here']} of them by children "
            "born in the run",
            f"- took a parent's trade: {share(tr['parent_trade'])}",
            f"- trained under a parent: {share(tr['under_parent'])}",
            f"- trades taken: {', '.join(f'{k} {n}' for k, n in tr['chosen'].items())}",
            f"- masters who died with apprentices: {md['masters']}, leaving {md['apprentices']} "
            f"apprentices, {md['reassigned']} of whom were given a new master "
            f"({tr['new_master_events']} new_master events)", "",
            "## What villagers did, year by year", "",
            "Shares of all decisions: a warning among the actions, a lesson the villager "
            "wrote chosen, and work at the fields. Fields worked and the village's food "
            "need are means over the year's days.", "",
            "| year | decisions | warning | lesson | work at the fields | fields worked | "
            "food need | largest crop |", "|---|---|---|---|---|---|---|---|"]
    for y in s["by_year"]:
        out.append(f"| {y['year']} | {y['decisions']:,} | {pct(y['warn'])} | {pct(y['lesson'])} | "
                   f"{pct(y['field work'])} | {y['worked fields']} | {y['need']} | "
                   f"{y['largest crop']} |")
    w = s["warnings"]
    out += ["", "## Warnings", "",
            f"{w['decisions']:,} decisions chose a warning. By the instruction behind it: "
            + (", ".join(f"{k} {n:,}" for k, n in w["by_instruction"]) or "none") + ".", "",
            "What quick warnings passed on, by the kind of event the news came from: "
            + (", ".join(f"{k} {n:,}" for k, n in w["passed_on"]) or "none (no quick warnings)")
            + ".",
            "",
            "## Goods and the world", "",
            f"- sales {s['world']['sales']}, for {s['world']['coins']} coins",
            f"- world events: {', '.join(f'{k} {n}' for k, n in s['world']['world_events'].items())}",
            ""]
    ls = s["lessons"]
    cons = ls["consolidations"]
    out += ["## The lessons villagers wrote", "",
            f"- stage changes {ls['stage_changes']}. Consolidations that kept at least one lesson "
            f"{cons['accepted some']}, and that had all refused {cons['all refused']}",
            f"- lessons written {ls['written']}, accepted {ls['accepted']}, refused "
            f"{ls['refused']} ({pct(ls['refused_share'])})", "",
            "### Why the check refused them", "",
            "The check names only the first fault it finds in a lesson.", "",
            "| why | lessons | share of refusals |", "|---|---|---|"]
    for w in ls["why_refused"]:
        out.append(f"| {w['kind']} | {w['n']} | {pct(w['share'])} |")
    for w in ls["why_refused"]:
        out += ["", f"Most common for {w['kind']}:", ""]
        out += [f"- {about}: {n}" for about, n in w["most_common"]]
    so = ls["switched_off_marker"]
    out += ["", "### The markers they used", "",
            f"Lessons carrying a marker of a mechanic this run had switched off: {so['written']} "
            f"written, {so['accepted']} accepted "
            f"({', '.join(f'{k} {n}' for k, n in so['markers'].items()) or 'none'}).", ""]
    for x in so["accepted_examples"]:
        out += [f"- accepted, `{x['id']}` by {x['author']}:", f"  > {x['content']}"]
    out += [""] if so["accepted_examples"] else []
    out += ["| marker | in accepted lessons | in refused lessons | in this run | "
            "required argument |", "|---|---|---|---|---|"]
    for mk in ls["markers"]:
        out.append(f"| {mk['marker']} | {mk['accepted']} | {mk['refused']} | "
                   f"{mk['in this run']} | {mk['required'] or ''} |")
    out += ["", "Lessons by whether one of their markers needs an argument named:", "",
            "| lesson | accepted | refused | share accepted |", "|---|---|---|---|"]
    for k, v in ls["needs_an_argument"].items():
        n = v["accepted"] + v["refused"]
        out.append(f"| {k} | {v['accepted']} | {v['refused']} | "
                   f"{pct(v['accepted'] / n if n else None)} |")
    out += ["", "### By the stage a villager reached", "",
            "| became | accepted | refused |", "|---|---|---|"]
    for k, v in ls["by_stage"].items():
        out.append(f"| {k} | {v['accepted']} | {v['refused']} |")
    out += ["", "### By decade", "", "| years | accepted | refused |", "|---|---|---|"]
    for d in ls["by_decade"]:
        out.append(f"| {d['decade']} | {d['accepted']} | {d['refused']} |")
    out += ["", "### Refused lessons, two of each kind", ""]
    for kind, items in ls["refused_examples"].items():
        for x in items:
            out += [f"- {kind}, by {x['author']} on becoming {x['became']}:",
                    f"  > {x['content']}", f"  - {x['why']}"]
    u = s["use"]
    did = ", ".join(f"{k} {n} ({pct(n / u['choices'])})" for k, n in u["markers_chosen"].items())
    out += ["", "## How the accepted lessons were used", "",
            f"- accepted {u['accepted']}, ever among a decision's logged candidates "
            f"{u['ever_a_candidate']}, ever chosen {u['ever_chosen']}",
            f"- chosen {u['choices']:,} times in {u['decisions']:,} decisions "
            f"({pct(u['choices'] / u['decisions'] if u['decisions'] else None)})",
            f"- what they had villagers do, by choices: {did}", "",
            "| years | decisions | chose a lesson | share |", "|---|---|---|---|"]
    for d in u["by_decade"]:
        n = d["decisions"]
        out.append(f"| {d['decade']} | {n:,} | {d['chose a lesson']:,} | "
                   f"{pct(d['chose a lesson'] / n if n else None)} |")
    out += ["", "### The most chosen", ""]
    for x in u["most_chosen"]:
        out += [f"- `{x['id']}`, by {x['author']} on becoming {x['became']}, chosen {x['n']} "
                f"times, a candidate {x['candidate']} times:", f"  > {x['content']}"]
    out += ["", "### Accepted but never chosen, three at random", ""]
    for x in u["never_chosen_examples"]:
        out += [f"- `{x['id']}`, by {x['author']} on becoming {x['became']}, a candidate "
                f"{x['candidate']} times:", f"  > {x['content']}"]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id")
    parser.add_argument("--out", default=str(ROOT / "results" / "long_run"))
    parser.add_argument("--to-day", type=int, default=None,
                        help="stop before this in-game day, so a later reading of a run "
                             "still going gives the same numbers")
    args = parser.parse_args()
    s = summarise(args.run_id, read(args.run_id, args.to_day))
    s["to_day"] = args.to_day
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "long_run_report.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    text = markdown(s)
    (out / "long_run_report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
