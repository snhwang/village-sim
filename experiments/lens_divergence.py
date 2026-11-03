#!/usr/bin/env python3
"""When a villager keeps what it heard anyway, does the lens change the words?

On the four-sentence world the lens measurement asked whether a fact was kept,
and temperament moved that. On the widened world it cannot: the news is
concrete and consequential -- a blight in the crop, a raid, grain gone over --
and roughly nine offers in ten are kept whatever lens is applied. The
keep/discard rate is at a ceiling and discriminates nothing.

So this asks the other half of the same question. Among the pairs where both
the villager and its counterfactual kept the fact, how far apart are the two
rewordings? Distance is 1 - cosine between the stored sentences.

Significance is a rank-sum test against the loci that carry no lens of their
own, pooled, which is the same floor the keep/discard measurement uses. Reads
the raw pairs saved by diffusion_counterfactual.py, so it needs the embedding
service but no language model.

    python experiments/lens_divergence.py

Writes results/lens_divergence.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hearthwick.character import LOCI  # noqa: E402
from hearthwick.config import ROOT, SimConfig  # noqa: E402
from hearthwick.corpus import make_embedder  # noqa: E402
from hearthwick.diffusion import compose_lens  # noqa: E402  (kept for parity of imports)

NO_LENS = ("sociability", "diligence")
NULL = "same prompt"


def cosine(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


def rank_sum(a: list[float], b: list[float]) -> tuple[float, float]:
    """Mann-Whitney U and a normal-approximation two-sided p.

    Written out rather than imported: the whole analysis should run from the
    saved pairs and the embedding service, with no extra dependency.
    """
    if not a or not b:
        return 0.0, 1.0
    combined = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks: dict[int, float] = {}
    i = 0
    rank_a = 0.0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        average = (i + j + 2) / 2          # ranks are 1-based; ties share
        for k in range(i, j + 1):
            if combined[k][1] == 0:
                rank_a += average
        i = j + 1
    n1, n2 = len(a), len(b)
    u = rank_a - n1 * (n1 + 1) / 2
    mean = n1 * n2 / 2
    sd = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sd == 0:
        return u, 1.0
    z = (u - mean) / sd
    p = math.erfc(abs(z) / math.sqrt(2))   # two-sided
    return u, p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default=str(ROOT / "results" / "diffusion_counterfactual.json"))
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    raw = payload.get("raw")
    if not raw:
        raise SystemExit("that results file has no raw pairs; re-run "
                         "diffusion_counterfactual.py to save them")

    embedder = make_embedder("service", SimConfig.embed_url)
    if embedder is None:
        raise SystemExit("this needs the embedding service on :8360")

    by_event: dict[int, dict[str, dict]] = {}
    for row in raw:
        by_event.setdefault(row["event"], {})[row["condition"]] = row

    cache: dict[str, list[float]] = {}

    def vector(text: str):
        if text not in cache:
            cache[text] = embedder.embed_single(text, is_query=False)
        return cache[text]

    labels = [NULL, "whole temperament", *LOCI]
    spread: dict[str, list[float]] = {label: [] for label in labels}
    for _, conditions in by_event.items():
        base = conditions.get("as heard")
        if base is None or not base["kept"]:
            continue
        for label in labels:
            other = conditions.get(label)
            if other is None or not other["kept"]:
                continue
            spread[label].append(1.0 - cosine(vector(base["text"]), vector(other["text"])))

    floor = [v for locus in NO_LENS for v in spread[locus]]
    rows = []
    for label in labels:
        values = spread[label]
        u, p = ((0.0, None) if label == NULL or label in NO_LENS
                else rank_sum(values, floor))
        rows.append({
            "what": label,
            "n": len(values),
            "median": round(float(statistics.median(values)), 4) if values else None,
            "mean": round(float(statistics.fmean(values)), 4) if values else None,
            "changed_at_all_pct": (round(100 * sum(1 for v in values if v > 1e-6)
                                         / len(values), 1) if values else None),
            "p_vs_no_lens": None if p is None else round(p, 4),
            "no_lens": label in NO_LENS,
            "null": label == NULL,
        })

    print(f"{'condition':22}{'n':>5}{'median':>9}{'mean':>9}{'reworded%':>11}{'p':>10}")
    for row in rows:
        p = "" if row["p_vs_no_lens"] is None else format(row["p_vs_no_lens"], ".4f")
        star = " *" if row["p_vs_no_lens"] is not None and row["p_vs_no_lens"] < 0.05 else ""
        print(f"{row['what']:22}{row['n']:>5}{row['median']:>9}{row['mean']:>9}"
              f"{row['changed_at_all_pct']:>11}{p:>10}{star}")

    out = Path(args.out)
    data = {"meta": {**payload["meta"], "date": datetime.now().strftime("%Y-%m-%d")},
            "no_lens_loci": list(NO_LENS), "rows": rows}
    (out / "lens_divergence.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "# Does the lens change the words, when the fact is kept either way?", "",
        f"{data['meta']['villagers']} villagers, "
        f"{data['meta']['reframings_replayed']} reframings, {data['meta']['date']}.", "",
        "On the widened world roughly nine offers in ten are kept whatever lens "
        "is applied, so the keep/discard rate is at a ceiling and cannot "
        "discriminate. This measures the other half: among pairs where both "
        "sides kept the fact, how far apart the two rewordings are "
        "(1 - cosine). Rank-sum against the loci carrying no lens of their own, "
        "pooled.", "",
        "| Swapped | n | median | mean | reworded at all | vs no-lens floor |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        name = row["what"]
        if row["null"]:
            name = "**" + name + " (floor)**"
        elif row["no_lens"]:
            name = "*" + name + " (no lens of its own)*"
        p = ("—" if row["p_vs_no_lens"] is None else
             ("**p=" + format(row["p_vs_no_lens"], ".4f") + "**"
              if row["p_vs_no_lens"] < 0.05 else "p=" + format(row["p_vs_no_lens"], ".3f")))
        lines.append(f"| {name} | {row['n']} | {row['median']} | {row['mean']} | "
                     f"{row['changed_at_all_pct']}% | {p} |")
    (out / "lens_divergence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out / 'lens_divergence.json'} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
