#!/usr/bin/env python3
"""How much the paper's measures vary from run to run, and their intervals.

The paper pools six ten-day runs. A pooled figure hides how much one seed
differs from the next, so this reports each measure run by run, with its mean,
standard deviation and range across the six. It reuses the analysis that made
the pooled figures (``knowledge_flow.analyse``) one run at a time, so there is
no second definition of any measure. Before reporting, it reruns the pooled
analysis and checks it against ``results/knowledge_flow.json``, so a change to
the analysis since the paper cannot pass unnoticed.

Wording drift is left out. It needs the embedding service, and the pooled
drift is already reported by ``knowledge_flow.py``.

It also gives Wilson 95% intervals for the action counterfactual
(``results/counterfactual.json``). Those replays are clustered by villager and
by run, so the intervals are a lower bound on the uncertainty, not a test.

And it counts decisions that chose a restored candidate. BEAR's retriever sets
aside a candidate whose similarity is below the threshold and none of whose
soft tags match, and then puts back every instruction whose hard gates pass,
scored by priority alone with a similarity of exactly 0. A restored candidate
therefore usually ranks first. The logs record similarity to four decimals,
and only a restored candidate has exactly 0.

    python experiments/run_spread.py

Reads the runs in results/paper_runs.txt. Writes results/run_spread.{json,md}.
"""

from __future__ import annotations

import collections
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hearthwick.config import ROOT  # noqa: E402
from knowledge_flow import analyse, knowledge_gated, load  # noqa: E402

RESULTS = ROOT / "results"

# (label, how to read it from analyse()'s output)
MEASURES = [
    ("events that spread", lambda d: d["reach"]["events_that_spread"]),
    ("median holders of an event", lambda d: d["reach"]["median_holders"]),
    ("median wordings of an event", lambda d: d["reach"]["median_wordings"]),
    ("longest chain", lambda d: d["reach"]["deepest_chain"]),
    ("offers already known (%)", lambda d: d["attrition"]["already_known_pct"]),
    ("new news refused (%)", lambda d: d["attrition"]["refused_of_new_pct"]),
    ("facts reclassified (%)", lambda d: d["reclassified"]["pct"]),
    ("reclassified toward trouble (%)", lambda d: d["reclassified"]["toward_trouble_pct"]),
    # From the counts, to one decimal like the rest. The pooled share_pct is
    # kept to two, and rounding that again can land the other way.
    ("knowledge-only decisions (%)",
     lambda d: round(100 * d["unlocked"]["total"] / d["unlocked"]["decisions"], 1)),
]

# Pooled fields compared with the committed results before anything is reported.
CHECKED = [("reach", "events_that_spread"), ("reach", "median_holders"),
           ("reach", "median_wordings"), ("reach", "deepest_chain"),
           ("attrition", "offers"), ("attrition", "duplicate"), ("attrition", "refused"),
           ("reclassified", "facts"), ("reclassified", "changed"),
           ("unlocked", "decisions"), ("unlocked", "total")]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials, as percentages."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(100 * (centre - half), 1), round(100 * (centre + half), 1))


def restored(run: dict, gated: set[str]) -> dict:
    """Villagers' decisions that chose a candidate restored at priority alone.

    ``over_knowledge`` counts those where the restored choice ranked above an
    instruction that only knowledge makes available (``gated``), which the
    decision did not refuse. Neither direction is exact. Only the twelve
    logged candidates are seen, which undercounts. And the decision stops
    checking once four candidates can be carried out, so one below them was
    never checked and may not have been feasible, which overcounts.
    """
    decisions = chose = over_knowledge = 0
    by_instruction: collections.Counter = collections.Counter()
    for event in run["events"]:
        if event["type"] != "decision" or event["character"] == "world":
            continue
        decisions += 1
        retrieved = event.get("retrieved", [])
        similarity = {r["id"]: r.get("similarity") for r in retrieved}
        chosen = event.get("chosen")
        if chosen and similarity.get(chosen) == 0.0:
            chose += 1
            by_instruction[chosen] += 1
            refused = set(event.get("refused") or ())
            ids = [r["id"] for r in retrieved]
            below = ids[ids.index(chosen) + 1:] if chosen in ids else []
            if any(i in gated and i not in refused for i in below):
                over_knowledge += 1
    return {"decisions": decisions, "chose_restored": chose,
            "over_knowledge": over_knowledge, "by_instruction": by_instruction}


def summarise(values: list[float]) -> dict:
    return {"mean": round(statistics.fmean(values), 1),
            "sd": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
            "min": min(values), "max": max(values)}


def main() -> int:
    names = (RESULTS / "paper_runs.txt").read_text(encoding="utf-8").split()
    runs = [load(ROOT / "runs" / name) for name in names]

    pooled = analyse(runs, None)
    committed = json.loads((RESULTS / "knowledge_flow.json").read_text(encoding="utf-8"))
    differ = [f"{a}.{b}: {pooled[a][b]} here, {committed[a][b]} committed"
              for a, b in CHECKED if pooled[a][b] != committed[a][b]]
    if differ:
        print("The pooled analysis no longer matches results/knowledge_flow.json:")
        print("\n".join(f"  {line}" for line in differ))
        return 1

    per_run = []
    for run in runs:
        data = analyse([run], None)
        per_run.append({"run": run["name"],
                        **{label: read(data) for label, read in MEASURES}})
    spread = {label: summarise([r[label] for r in per_run]) for label, _ in MEASURES}

    action = json.loads((RESULTS / "counterfactual.json").read_text(encoding="utf-8"))
    intervals = [{"what": r["what"], "changed": r["changed"], "compared": r["compared"],
                  "pct": r["pct"], "wilson95": wilson(r["changed"], r["compared"])}
                 for r in action["rows"]]

    gated = knowledge_gated()
    counts = [restored(run, gated) for run in runs]
    pooled_restored = {
        "decisions": sum(c["decisions"] for c in counts),
        "chose_restored": sum(c["chose_restored"] for c in counts),
        "over_knowledge": sum(c["over_knowledge"] for c in counts),
        "by_instruction": dict(sum((c["by_instruction"] for c in counts),
                                   start=collections.Counter()).most_common()),
    }
    pooled_restored["pct"] = round(100 * pooled_restored["chose_restored"]
                                   / pooled_restored["decisions"], 1)

    out = {"meta": {"runs": names, "date": datetime.now().strftime("%Y-%m-%d"),
                    "checked_against": "results/knowledge_flow.json"},
           "per_run": per_run, "spread": spread,
           "action_intervals": {"runs": action["meta"].get("runs") or [action["meta"]["run"]],
                                "rows": intervals},
           "restored": {**pooled_restored,
                        "per_run": [{"run": r["name"], "decisions": c["decisions"],
                                     "chose_restored": c["chose_restored"],
                                     "over_knowledge": c["over_knowledge"]}
                                    for r, c in zip(runs, counts)]}}
    (RESULTS / "run_spread.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    lines = ["# Run-to-run spread of the paper's measures", "",
             f"Runs: {', '.join(names)}. The pooled analysis matched "
             "`results/knowledge_flow.json` before these were computed.", "",
             "| measure | mean | SD | min | max |", "|---|---|---|---|---|"]
    lines += [f"| {label} | {s['mean']} | {s['sd']} | {s['min']:g} | {s['max']:g} |"
              for label, s in spread.items()]
    lines += ["", "## Each run", "",
              "| run | " + " | ".join(label for label, _ in MEASURES) + " |",
              "|---|" + "---|" * len(MEASURES)]
    lines += ["| " + r["run"] + " | " + " | ".join(f"{r[label]:g}" for label, _ in MEASURES)
              + " |" for r in per_run]
    lines += ["", f"## Action counterfactual, Wilson 95% intervals "
              f"({', '.join(out['action_intervals']['runs'])})", "",
              "Decisions are clustered by villager, so these understate the uncertainty.", "",
              "| swapped | changed | % | 95% interval |", "|---|---|---|---|"]
    lines += [f"| {r['what']} | {r['changed']}/{r['compared']} | {r['pct']} | "
              f"{r['wilson95'][0]}--{r['wilson95'][1]} |" for r in intervals]
    rs = out["restored"]
    lines += ["", "## Decisions that chose a restored candidate", "",
              f"{rs['chose_restored']:,} of {rs['decisions']:,} villagers' decisions "
              f"({rs['pct']}%) chose a candidate the threshold set aside and BEAR "
              "restored at priority alone. In "
              f"{rs['over_knowledge']:,} of them it ranked above an unrefused instruction "
              "that only knowledge makes available.", "",
              "| instruction | times chosen |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in list(rs["by_instruction"].items())[:10]]
    (RESULTS / "run_spread.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
