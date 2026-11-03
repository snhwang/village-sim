#!/usr/bin/env python3
"""Check every number the paper quotes against the run it came from.

A paper drifts from its logs the moment someone re-runs something. This
recomputes each quoted figure from the results files and fails loudly if the
draft disagrees.

Each claim is checked as a verbatim substring of the draft. Bare small integers
match by accident, so anything that could be a coincidence is checked in the
form the paper states it in ("87/400", "4.2%") rather than on its own.

    python paper/check_numbers.py
    python paper/check_numbers.py --paper long
    python paper/check_numbers.py --run <run_id>

There are two versions. The one to submit is the LaTeX in its own repository,
paper-hearthwick-ACMGames beside this one, a research article of up to 12,000
words since 2026-10-06 (it was a 6,000-word case study before).
hearthwick_case_study_long.md, here, is the longer case-study text. Both are
checked by default.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Each version, and the claims it does not quote, by label prefix. The
# submission quotes drift after one telling and after five, and its Figure 2
# draws the rest. The long version predates the research article's spread
# table, intervals and restored choices. The submission version is the LaTeX
# in its own repository, beside this one, in ACM's template. The long version
# is Markdown, here.
# The submission no longer quotes restored choices: the frozen build sets a
# candidate under the threshold aside for good (BEAR's threshold fix).
# The submission no longer tells the September development run's story
# (Maja's schooling, Gisla's proposal), so it is not checked for it. Its
# lives come from the ten-year runs (long_run_claims).
PAPERS = {"submission": (HERE.parent.parent / "paper-hearthwick-ACMGames",
                         tuple(f"flow: drift at hop {h}" for h in (2, 3, 4, 6, 7, 8, 10))
                         + ("restored:", "development:")),
          "long": (HERE / "hearthwick_case_study_long.md", ("spread:", "restored:", "long:"))}
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
# The first of the paper-v4 measured runs (results/paper_runs.txt), whose
# record gives the corpus and the cost the paper quotes. Before 2026-10-24
# this was a September run, so the check read another corpus.
HEADLINE_RUN = "20261022-070414-seed1"
# Small counts the paper writes as words ("three of the six seeds").
class _Words(list):
    """Numbers as the paper writes them: words to twenty, digits beyond. The
    paper-v3 runs spread 39 to 59 events a run, and indexing past the list
    stopped the check (2026-10-19)."""

    def __getitem__(self, n):
        return super().__getitem__(n) if isinstance(n, int) and 0 <= n < len(self) else str(n)


WORDS = _Words(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                "seventeen", "eighteen", "nineteen", "twenty"])


def read(name: str) -> dict | None:
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def flow_claims(data: dict) -> dict[str, str]:
    """Sections 5 and 6: reach, drift, attrition, and what knowledge unlocked."""
    r, a, u = data["reach"], data["attrition"], data["unlocked"]
    out = {
        "flow: events that spread": str(r["events_that_spread"]),
        "flow: median holders": f"{r['median_holders']:g}",
        "flow: median wordings": f"{r['median_wordings']:g}",
        "flow: longest chain": str(r["deepest_chain"]),
        "flow: offers": f"{a['offers']:,}",
        "flow: already known": f"{a['already_known_pct']}%",
        "flow: refused of what was new": f"{a['refused_of_new_pct']}%",
        "flow: duplicates": f"{a['duplicate']:,} duplicates",
        "flow: caught by root": f"{a['duplicate_by_root']:,}",
        "flow: caught by vector": f"vector similarity caught {a['duplicate_by_vector']}",
        "flow: knowledge-only decisions": f"{u['total']:,}",
        "flow: decisions": f"{u['decisions']:,}",
        "flow: knowledge-only share": f"{round(u['share_pct'], 1)}%",
    }
    kinds = r.get("by_kind") or {}
    if kinds:
        out["flow: sickness reach"] = f"a median of {kinds['sicken']['median_holders']:g} villagers"
        out["flow: traveler reach"] = f"traveler's news {kinds['traveler']['median_holders']:g}"
        out["flow: tale reach"] = f"storyteller's tale {kinds['tale']['median_holders']:g}"
    blight = u["by_instruction"].get("food-farmer-blight")
    if blight:
        out["flow: farmers cut out the blight"] = f"{blight:,} times"
    for row in data["drift"]:
        if row["hop"] == 0:
            continue
        out[f"flow: drift at hop {row['hop']}"] = f"{row['median']:.3f}"
    rc = data.get("reclassified")
    if rc:
        out["flow: facts from a witnessed event"] = f"{rc['facts']:,}"
        out["flow: reclassified"] = f"{rc['changed']:,}"
        out["flow: reclassified pct"] = f"{rc['pct']}%"
        out["flow: toward trouble"] = f"{rc['toward_trouble_pct']}%"
    return out


def action_claims(data: dict) -> dict[str, str]:
    """Section 7, action: quoted as a fraction and as a percentage."""
    rows = {r["what"]: r for r in data["rows"]}
    whole = rows["whole temperament"]
    return {
        "action: whole temperament": f"{whole['changed']}/{whole['compared']}",
        "action: whole temperament pct": f"{whole['pct']}%",
        "action: caution": f"{rows['caution']['pct']}%",
        "action: candor floor": f"{rows['candor']['pct']}%",
    }


def p_text(p: float | None) -> str:
    """A p-value as the paper prints it: below 0.0001 as a bound, otherwise to
    three places. Printed to three places, a bound read "p = 0.000"."""
    if p is None:
        return "p = n/a"
    if p < 0.0001:
        return "p < 0.0001"
    # Printed to three places, p = 0.0001 read "p = 0.000" (paper-v4).
    return "p < 0.001" if p < 0.0005 else f"p = {p:.3f}"


def lens_claims(data: dict) -> dict[str, str]:
    """Section 7, absorption: the loci the paper names, and both floors."""
    rows = {r["what"]: r for r in data["rows"]}
    floors = data["floors"]
    out = {
        "lens: decoder floor": f"{floors['decoder']['pct']}%",
        "lens: inert-tag floor": f"{floors['inert_tag']['pct']}%",
    }
    for name in ("candor", "trust", "curiosity", "whole temperament", "caution"):
        out[f"lens: {name}"] = f"{rows[name]['pct']}%"
    for name in ("candor", "trust", "caution", "curiosity"):
        out[f"lens: keeping, {name} against the inert floor"] = p_text(rows[name]["p_vs_inert"])
    out["lens: keeping, curiosity against the decoder floor"] =         p_text(rows["curiosity"]["p_vs_floor"])
    return out


def divergence_claims(data: dict) -> dict[str, str]:
    rows = {r["what"]: r for r in data["rows"]}
    return {f"rewording: {name}": f"{rows[name]['median']:.3f}"
            for name in ("candor", "trust", "curiosity", "whole temperament", "caution")}


def ablation_claims(data: dict) -> dict[str, str]:
    best = {r["label"]: r for r in data["results"]}
    soft = best["soft tags, BM25"]
    return {
        "ablation: soft tags at t=0.15":
            f"{best['soft tags, service, t=0.15']['similarity_decided_pct']}%",
        "ablation: soft tags on BM25": f"{soft['similarity_decided_pct']}%",
        "ablation: used at t=0.40":
            f"{best['soft tags, service, t=0.40']['instructions_used']}/"
            f"{best['soft tags, service, t=0.40']['actionable_instructions']}",
        "ablation: BM25 talking at 9am": f"{soft['activities_at_9am'].get('talk')} of 30",
    }


ABLATION_SEEDS = "threshold_ablation_v4"


def six_seed_ablation_claims() -> dict[str, str] | None:
    """The ablation over seeds 1 to 6 that chose t for the paper-v4 runs
    (RUNNING_EXPERIMENTS.md step 1), as the means its table shows. None when
    it is absent, and then the single-seed ablation is checked instead."""
    files = sorted((RESULTS / ABLATION_SEEDS).glob("seed*/retrieval_ablation.json"))
    if not files:
        return None
    arms: dict[str, list[dict]] = {}
    for f in files:
        for r in json.loads(f.read_text(encoding="utf-8"))["results"]:
            arms.setdefault(r["label"], []).append(r)

    def mean(label, value):
        rows = arms[label]
        return round(sum(value(r) for r in rows) / len(rows), 1)

    def set_aside(r):
        return 100 * r["decisions_with_set_aside"] / r["audited_decisions"]

    def working(r):
        acts = r.get("activities_at_9am") or {}
        return 100 * acts.get("work", 0) / max(1, sum(acts.values()))

    out = {"ablation: seeds": f"seeds 1 to {len(files)}"}
    for label, short in (("hard gates, service", "hard gates, embedder"),
                         ("soft tags, BM25", "soft tags, BM25"),
                         ("soft tags, service, t=0", "t=0"),
                         ("soft tags, service, t=0.15", "t=0.15"),
                         ("soft tags, service, t=0.40", "t=0.40")):
        out[f"ablation: similarity decided, {short}"] = \
            f"{mean(label, lambda r: r['similarity_decided_pct'])}%"
        out[f"ablation: working at 9am, {short}"] = f"{mean(label, working):.0f}%"
    for label, short in (("soft tags, service, t=0.15", "t=0.15"),
                         ("soft tags, service, t=0.40", "t=0.40")):
        out[f"ablation: set aside, {short}"] = f"{mean(label, set_aside)}%"
    same = sum(a["choices_digest"] == b["choices_digest"] for a, b in
               zip(arms["soft tags, service, t=0"], arms["soft tags, service, t=0.15"]))
    out["ablation: t=0.15 chose as t=0"] = (f"in all {WORDS[same]} seeds" if same == len(files)
                                            else f"in {WORDS[same]} of the {WORDS[len(files)]} seeds")
    return out


def cost_claims(meta: dict) -> dict[str, str]:
    return {
        "cost: speech calls": f"{meta['speech_calls']:,}",
        "cost: embedding calls": f"{meta['embedder']['calls']:,}",
        "cost: embedding cache hits": f"{meta['embedder']['cache_hits']:,}",
    }


def balance_claims(data: dict) -> dict[str, str]:
    """Section 7: how many independent stimuli the absorption result rests on."""
    v = data["vocabulary"]
    world = data["repertoire"]
    return {
        "balance: reframings": f"{v['reframings']:,} reframings",
        "balance: events reframed": f"{v['reframed_events']} events",
        "balance: effective reframed": f"{v['effective_reframed']:.2f}",
        "balance: quiet days": f"{world['quiet_days']} of {world['world_decisions']} days",
    }


def carryover_claims(data: dict) -> dict[str, str]:
    """Section 7: the teller's filing and the listener's, descriptively."""
    rows = {(r["listeners"], r["teller_said_trouble"]): r for r in data["kind"]}
    return {
        "carryover: teller said trouble": f"{rows[('all listeners', True)]['pct']}%",
        "carryover: teller did not": f"{rows[('all listeners', False)]['pct']}%",
    }


def visitor_claims(data: list) -> dict[str, str]:
    """Section 4: how often the world sent a storyteller."""
    seeds = sum(1 for r in data if r["storytellers"])
    return {"visitors: seeds with a storyteller":
            "in all six seeds" if seeds == len(data) == 6 else f"in {WORDS[seeds]} of the six seeds"}


def trades_claims(data: list) -> dict[str, str]:
    """Section 12: graduations and qualifications."""
    graduated = sum(len(r["graduated"]) for r in data)
    qualified = sum(len(r["qualified"]) for r in data)
    # The trades the graduates were taken on in. The paper-v3 text named the
    # merchants, and in the paper-v4 runs no graduate became one.
    trades = {a["trade"] for r in data for a in r["apprenticed"]}
    return {"trades: graduated": f"{WORDS[graduated]} children graduated",
            "trades: trades": f"into {WORDS[len(trades)]} different trades",
            "trades: qualified": f"{WORDS[qualified]} apprentices qualified"}


def by_day_claims(data: dict) -> dict[str, str]:
    """Section 6: what knowledge made reachable, on the first full day and the
    last (the ninth of a ten-day run, the thirty-ninth of a forty-day one)."""
    days = {r["day"]: r for r in data["by_day"]}
    last = max(days)
    rose = data["runs_that_rose"]
    return {"by day: first day": f"{days[1]['share_pct']}%",
            "by day: last day": f"{days[last]['share_pct']}%",
            "by day: runs that rose": ("in all six runs" if rose == 6
                                       else f"in {WORDS[rose]} of the six runs")}


LONG_RUNS = "long_runs_v4"


def long_run_claims() -> dict[str, str] | None:
    """Section 9: the ten-year runs, from each run's report and health check
    in results/long_runs_v4 (RUNNING_EXPERIMENTS.md step 4), seeds in order.
    Births are given per family only, never pooled (the boundary with the
    genetics preprint)."""
    folder = RESULTS / LONG_RUNS
    reports, healths = [], []
    for n in range(1, 4):
        report = folder / "report" / f"seed{n}" / "long_run_report.json"
        health = folder / "health" / f"seed{n}" / "health_check.json"
        if not (report.exists() and health.exists()):
            return None
        reports.append(json.loads(report.read_text(encoding="utf-8")))
        healths.append(json.loads(health.read_text(encoding="utf-8")))

    def listed(values) -> str:
        # One value per seed, three in all, with the serial comma the paper uses.
        return ", ".join(str(v) for v in values[:-1]) + f", and {values[-1]}"

    def said(n: int) -> str:
        return "none" if n == 0 else WORDS[n]

    ends = [r["village"]["end"] for r in reports]
    married = [said(r["village"]["married"]) for r in reports]
    died = [said(r["village"]["died"]) for r in reports]
    ages = [(r["age_at_death"]["n"], r["age_at_death"]["mean"]) for r in reports
            if r["age_at_death"].get("n")]
    mean_age = sum(n * a for n, a in ages) / sum(n for n, _ in ages)
    checks = [{c["check"]: c["figures"] for c in h["checks"]} for h in healths]
    granary = [c["the granary empty for long"] for c in checks]
    empty = [sum(g["empty days by year"].values()) for g in granary]
    streak = max(max(g["longest empty streak by year"].values()) for g in granary)
    per = [list(c["the live memory index growing without end"]["per villager"].values())
           for c in checks]
    later = [v for p in per for v in p[3:]]          # from the fourth year on
    families = [int(k) for r in reports for k in r["children"]["per_family"]]
    grandchildren = any(int(g) > 1 for r in reports for g in r["village"]["generations"])
    out = {"long: people": f"to {listed(ends)} people",
           "long: range": f"between {min(ends)} and {max(ends)} people",
           "long: married": f"{listed(married).capitalize()} couples married",
           "long: deaths": f"There were {listed(died)} deaths, all of old age",
           "long: mean age": f"at a mean age of {mean_age:.0f} years",
           "long: empty days": f"on {listed(empty)} of the 280 days",
           "long: children": (f"from {WORDS[min(families)]} to {WORDS[max(families)]} "
                              "children each"),
           "long: memories": f"between {round(min(later))} and {round(max(later))} memories"}
    if streak <= 7:
        out["long: longest empty"] = "never for more than a week at a time"
    if not grandchildren:
        out["long: grandchildren"] = "none had a child of its own"
    young = [d for h in checks for d in h["deaths before old age"]["young"]]
    if young:
        out.pop("long: deaths")
    return out


FORTY_DAY_AGES = "paper_v4/ages"
TRIAL = "dated_trial"


def old_news_claims() -> dict[str, str] | None:
    """Section 8: old tales in warnings of danger coming, a known defect of
    the paper's build, and the trial of its fix (far_danger_dated, three
    ten-year runs on rtx-lab, results/dated_trial/runs.txt). From
    experiments/warning_ages.py and the health checks."""
    long_ages = sorted((RESULTS / LONG_RUNS / "ages").glob("seed*/warning_ages.json"))
    forty_ages = sorted((RESULTS / FORTY_DAY_AGES).glob("*/warning_ages.json"))
    trial_ages = sorted((RESULTS / TRIAL).glob("ages_seed*/warning_ages.json"))
    long_health = sorted((RESULTS / LONG_RUNS / "health").glob("seed*/health_check.json"))
    trial_health = sorted((RESULTS / TRIAL).glob("health_seed*/health_check.json"))
    if [len(long_ages), len(forty_ages), len(trial_ages), len(long_health),
            len(trial_health)] != [3, 6, 3, 3, 3]:
        return None

    def over_week(files) -> str:
        values = [json.loads(f.read_text(encoding="utf-8"))["percent_of_facts_by_instruction"]
                  ["coming-pass-the-word"]["event over 7 days old"] for f in files]
        return f"{min(values):.1f} to {max(values):.1f}%"

    def most_repeats(files) -> str:
        most = 0
        for f in files:
            check = next(c for c in json.loads(f.read_text(encoding="utf-8"))["checks"]
                         if "same warning to the same listener" in c["check"])
            most = max(most, *check["figures"]["most times in a day, by year"].values())
        return WORDS[most]

    return {"old news: ten-year runs": f"{over_week(long_ages)} were over a week old",
            "old news: forty-day runs": f"against {over_week(forty_ages)} in the forty-day runs",
            "old news: most repeats": f"up to {most_repeats(long_health)} times in a day",
            "old news: trial": f"{over_week(trial_ages)} of these events",
            "old news: trial repeats": f"more than {most_repeats(trial_health)} times in a day"}


def scale_claims(data: list) -> dict[str, str]:
    """Section 9: the 300-villager run."""
    big = next(r for r in data if r["villagers"] == 300)
    return {"scale: wall clock": f"{round(big['seconds'] / 60)} minutes",
            "scale: model calls": f"{big['speech_calls']:,} model calls",
            "scale: embedding calls": f"{big['embedding_calls']:,}",
            "scale: median holders": f"{big['median_holders']:g} of its 300",
            "scale: median wordings": f"{big['median_wordings']:g} wordings",
            "scale: longest chain": f"{big['deepest_chain']} tellings"}


def development_trades_claims(data: list) -> dict[str, str]:
    """Section 12: careers in the forty-day run, and Maja's."""
    run = data[0]
    maja = next(a for a in run["apprenticed"] if a["who"] == "maja")
    graduated = next(g for g in run["graduated"] if g["who"] == "maja")
    under_parent = sum(a["master_is_parent"] for a in run["apprenticed"])
    return {"development: Maja graduated": f"graduated on day {graduated['day']}",
            "development: Maja's master": f"{maja['master'].title()}, an elder",
            "development: Maja's fondness": f"({maja['fondness']:.1f})",
            "development: under a parent":
                f"{'None' if not under_parent else WORDS[under_parent].title()} of the "
                f"{WORDS[len(run['graduated'])]} graduates"}


def development_couples_claims(data: list) -> dict[str, str]:
    """Section 12: the first marriage in the forty-day run, and its house."""
    run = data[0]
    first = run["proposals"][0]
    house = run["houses"][0]
    return {"development: proposal": f"{first['asker'].title()} qualified as a crafter "
                                     f"at midnight on day {first['day']}",
            "development: proposal fondness": f"({first['affinity']:.1f})",
            "development: plot laid out by": f"{run['sites_started'][0]['by'].title()} laid out",
            "development: house day": f"finished on the morning of day {house['day']}"}


def development_family_claims(data: list) -> dict[str, str]:
    """Section 12: births in the forty-day run, by family, and the handler's
    refusals. Births are listed per family, never pooled (the boundary with
    the genetics preprint)."""
    run = data[0]
    families: dict[tuple[str, str], int] = {}
    for b in run["births"]:                     # in order of first birth
        key = (b["mother"].title(), b["father"].title())
        families[key] = families.get(key, 0) + 1
    ones = [f"{m} and {f}" for (m, f), n in families.items() if n == 1]
    more = [f"{m} and {f} had {WORDS[n]}" for (m, f), n in families.items() if n > 1]
    single = ", ".join(ones[:-1]) + f", and {ones[-1]}" if len(ones) > 1 else "".join(ones)
    asked = run["decision_chosen"] + run["decision_refused"]
    return {"development: births by family":
                f"{single} each had a child" + "".join(f", and {m}" for m in more),
            "development: refused to have a child":
                f"Of {asked} requests to have one, the handler refused {run['decision_refused']}"}


def two_step_claims(data: dict) -> dict[str, str]:
    """Section 7: B's temperament swapped, C's memory measured."""
    candor = next(r for r in data["rows"] if r["what"] == "candor")
    return {
        "two-step: chains": f"{data['meta']['chains']:,} chains",
        "two-step: inert floor": f"({data['floors']['inert_tag']['pct']}%)",
        "two-step: decoder floor": f"({data['floors']['decoder']['pct']}%)",
        "two-step: events": f"{data['events']['distinct']} events",
        "two-step: effective events": f"an effective sample of {data['events']['effective']}",
        "two-step: candor": f"in {candor['memory_changed_pct']}% of chains",
        "two-step: candor p": p_text(candor["p_vs_inert"]),
    }


def spread_claims(data: dict) -> dict[str, str]:
    """The research article's spread table, run-level ranges, intervals and
    restored choices (experiments/run_spread.py)."""
    s = data["spread"]
    pct = {"offers already known (%)", "new news refused (%)", "facts reclassified (%)",
           "reclassified toward trouble (%)", "knowledge-only decisions (%)"}
    out = {}
    for label, v in s.items():
        span = (f"{v['min']:.1f}--{v['max']:.1f}" if label in pct
                else f"{v['min']:g}--{v['max']:g}")
        out[f"spread: {label}"] = f"{v['mean']} ({v['sd']}) & {span}"
    events, holders = s["events that spread"], s["median holders of an event"]
    out["spread: events per run"] = (f"between {WORDS[int(events['min'])]} and "
                                     f"{WORDS[int(events['max'])]} events")
    out["spread: median reach per run"] = (f"between {holders['min']:g} and "
                                           f"{holders['max']:g} villagers")
    refused = s["new news refused (%)"]
    out["spread: refusals per run"] = f"from {refused['min']}% to {refused['max']}%"
    share = s["knowledge-only decisions (%)"]
    out["spread: knowledge-only per run"] = f"from {share['min']}% to {share['max']}%"
    out["spread: toward danger in every run"] = (
        f"at least {s['reclassified toward trouble (%)']['min']:g}% of changes")
    rows = {r["what"]: r for r in data["action_intervals"]["rows"]}
    for name in ("whole temperament", "candor"):
        lo, hi = rows[name]["wilson95"]
        out[f"spread: Wilson interval, {name}"] = f"{lo}--{hi}%"
    r = data["restored"]
    out["restored: decisions"] = (f"{r['chose_restored']:,} of {r['decisions']:,} "
                                  f"decisions ({r['pct']}%)")
    return out


def instruction_files(commit: str | None) -> list[tuple[str, str]]:
    """(directory, text) of every instruction file, at ``commit`` if given.

    The paper describes the corpus its runs used. Counted from the disk, a
    corpus that grew after the runs would make the paper describe
    instructions no reported run had.
    """
    import subprocess
    if commit and subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                                 capture_output=True).returncode != 0:
        # The public repository has its own commits. Its paper-v4 tag holds
        # the same data/ as the development commit the runs recorded.
        print(f"note: commit {commit} is not in this repository, so the corpus is "
              "counted from the files checked out (use the paper-v4 tag)")
        commit = None
    if commit:
        names = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", commit,
                                "data/instructions"], capture_output=True, text=True,
                               check=True).stdout.split()
        return [(Path(n).parent.name,
                 subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{n}"],
                                capture_output=True, text=True, check=True).stdout)
                for n in sorted(names) if n.endswith(".yaml")]
    return [(path.parent.name, path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "data" / "instructions").rglob("*.yaml"))]


def corpus_claims(commit: str | None = None, recorded: dict | None = None) -> dict[str, str]:
    """Section 2: the corpus the headline run used.

    From the run's own record of what it loaded (meta.json ``corpus``) when it
    has one. Runs made before that record existed are read from their
    commit's instruction files, which they loaded whole.
    """
    import yaml

    from bear import parse_actions

    if recorded:
        by_dir = dict(recorded["by_dir"])
        total, actionable = recorded["authored"], recorded["with_action_markers"]
    else:
        by_dir = {}
        total = actionable = 0
        for directory, text in instruction_files(commit):
            spec = (yaml.safe_load(text) or {}).get("instructions") or []
            by_dir[directory] = by_dir.get(directory, 0) + len(spec)
            total += len(spec)
            actionable += sum(1 for i in spec if parse_actions(i.get("content", "")))
    # In the form the paper states them, since bare numbers match by accident
    # ("116" matched "116 chains" while the corpus said otherwise).
    label = {"stages": "life-stage", "knowledge": "knowledge", "temperament": "temperament",
             "world": "world", "roles": "role", "visitors": "visitor",
             "culture": "school", "trades": "trade", "family": "family",
             "elderwork": "elders' work", "market": "market", "coming": "coming danger"}
    out = {"corpus: authored": f"{total} authored",
           "corpus: with action markers": f"{actionable} carry an action marker"}
    for name, count in sorted(by_dir.items()):
        out[f"corpus: {name}"] = f"{count} {label.get(name, name)}"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", default=HEADLINE_RUN)
    parser.add_argument("--paper", choices=["both", *PAPERS], default="both",
                        help="which version to check (default both)")
    args = parser.parse_args()

    run_dir = ROOT / "runs" / args.run
    if not run_dir.exists():
        print(f"run {args.run} is not in runs/ — regenerate it with:")
        print(f"  python -m hearthwick run --days 10 --seed "
              f"{args.run.split('seed')[-1]} --village greater")
        return 2

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    names = list(PAPERS) if args.paper == "both" else [args.paper]
    # The paper's LaTeX lives in its own repository beside this one, and the
    # long version is not published with the code, so either may be absent.
    present = [n for n in names if PAPERS[n][0].exists()]
    for name in names:
        if name not in present:
            print(f"note: {PAPERS[name][0]} is not here, so the {name} version is unchecked")
    if not present:
        return 2
    return max(check(PAPERS[n][0], PAPERS[n][1], meta, args.run) for n in present)


def latex_text(project: Path, name: str = "paper.tex") -> str:
    """A LaTeX paper as plain text: its \\input files expanded, comments and
    commands dropped, and the escapes a number can carry undone ("14.0\\%")."""
    def expand(path: Path) -> str:
        source = path.read_text(encoding="utf-8")
        return re.sub(r"\\input\{([^}]+)\}",
                      lambda m: expand(project / (m.group(1).removesuffix(".tex") + ".tex")),
                      source)
    text = expand(project / name)
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = expand_macros(text, macros(text))
    for old, new in (("\\%", "%"), ("\\_", "_"), ("\\&", "&"), ("\\textless{}", "<"),
                     ("\\textgreater{}", ">"), ("{,}", ","), ("~", " ")):
        text = text.replace(old, new)
    return text


def macros(text: str) -> dict[str, str]:
    """Plain-text macros the paper defines, such as the system's name
    (``\\newcommand{\\sysname}{Village Sim}``)."""
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^{}]*)\}", text))


def expand_macros(text: str, defs: dict[str, str]) -> str:
    """Each use of a plain-text macro replaced by its text, so that it is
    counted as the words it prints. The definitions themselves stay."""
    for name, body in defs.items():
        text = re.sub(r"(?<!\\newcommand\{)\\" + name + r"(?![A-Za-z])(?:\{\})?",
                      lambda m, body=body: body, text)
    return text


def plain_words(text: str) -> int:
    """Words as a reader counts them: commands and markup symbols left out,
    along with what the anonymized PDF does not print (a figure's description
    for screen readers, and the acknowledgements)."""
    text = re.sub(r"\\ifanon\\else.*?\\fi", "", text, flags=re.S)
    text = re.sub(r"\\ifanon(.*?)\\fi", r"\1", text, flags=re.S)
    text = re.sub(r"\\Description\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:cite|ref|label|includegraphics|input|bibliography\w*)(\[[^\]]*\])?\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    return len([w for w in text.split() if re.search(r"[A-Za-z0-9]", w)])


def reference_words(bbl: str) -> int:
    """The printed reference list, from BibTeX's output without its markup."""
    bbl = bbl[bbl.find("\\bibitem"):]
    bbl = re.sub(r"(?m)^%.*$", "", bbl)
    bbl = re.sub(r"\\bibitem\[[^\]]*\]%?\s*\{[^}]*\}", "", bbl)
    bbl = re.sub(r"\\bib(?:info|field)\{[^}]*\}", "", bbl)
    bbl = re.sub(r"\\show\w+(\[[^\]]*\])?", "", bbl)
    return plain_words(bbl)


def check(paper: Path, skip: tuple[str, ...], meta: dict, run: str) -> int:
    if paper.is_dir():
        text = latex_text(paper)
        body = text[text.index("\\begin{abstract}"):]
        bbl = paper / "main.bbl"
        refs = (reference_words(expand_macros(bbl.read_text(encoding="utf-8"), macros(text)))
                if bbl.exists() else 0)
        words = plain_words(body) + refs
        counted = (f"word count {words}, references included"
                   + ("" if bbl.exists() else " (main.bbl is missing, so not the references)"))
    else:
        text = paper.read_text(encoding="utf-8")
        words = len(re.sub(r"```.*?```", "", text, flags=re.S).split())
        counted = f"word count {words}, references and markdown symbols included"
    # A number can break across a line anywhere in the source.
    text = re.sub(r"\s+", " ", text)
    claims: dict[str, str] = {}
    commit = ((meta.get("code") or {}).get("hearthwick") or "").removesuffix("-dirty") or None
    claims.update(corpus_claims(commit, meta.get("corpus")))
    claims.update(cost_claims(meta))
    for name, fn in (("knowledge_flow.json", flow_claims),
                     ("counterfactual.json", action_claims),
                     ("diffusion_counterfactual.json", lens_claims),
                     ("lens_divergence.json", divergence_claims),
                     ("retrieval_ablation.json", ablation_claims),
                     ("world_balance.json", balance_claims),
                     ("memory_carryover.json", carryover_claims),
                     ("two_step_counterfactual.json", two_step_claims),
                     ("run_spread.json", spread_claims),
                     ("visitors.json", visitor_claims),
                     ("trades.json", trades_claims),
                     ("knowledge_by_day.json", by_day_claims),
                     ("scale.json", scale_claims),
                     ("development/trades.json", development_trades_claims),
                     ("development/couples.json", development_couples_claims),
                     ("development/family.json", development_family_claims)):
        data = read(name)
        if data is None:
            print(f"note: results/{name} is absent, so those numbers are unchecked")
            continue
        claims.update(fn(data))
    lives = long_run_claims()
    if lives is None:
        print(f"note: results/{LONG_RUNS} is incomplete, so the ten-year runs are unchecked")
    else:
        claims.update(lives)
    old = old_news_claims()
    if old is None:
        print("note: the warning ages or the trial's checks are incomplete, so the old "
              "news in warnings is unchecked")
    else:
        claims.update(old)
    six = six_seed_ablation_claims()
    if six is not None:
        claims = {label: value for label, value in claims.items()
                  if not label.startswith("ablation:")}
        claims.update(six)
    claims = {label: value for label, value in claims.items()
              if not label.startswith(skip)}

    print(f"paper: {paper.name}\nrun:   {run}\n")
    missing = []
    for label, value in claims.items():
        quoted = value in text
        print(f"  {'found  ' if quoted else 'MISSING'}  {label:34} {value}")
        if not quoted:
            missing.append((label, value))

    print(f"\n  {counted} (ACM Games research article: up to 12,000 including references)")
    if missing:
        print(f"\n{len(missing)} value(s) not found verbatim - check the wording, "
              "or the numbers have moved:")
        for label, value in missing:
            print(f"    {label}: {value}")
        return 1
    print("\nevery quoted number matches the logs\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
