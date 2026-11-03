# The paper's September results

Copied here on 2026-10-07, before the research article's reruns
(RUNNING_EXPERIMENTS.md) overwrite `results/`. They are the results of the
six measured runs of 2026-09-27 (Hearthwick 19611f5, tag `paper-runs`), the
300-villager run (also 19611f5) and the forty-day run (5a25290, tag
`paper-development`), as the paper quoted them up to its commit 9a843ed.

They were made with BEAR before its threshold fix (bear-dev 226c659), when
the threshold never filtered a gated instruction. `experiments/threshold_replay.py`
measures what the fix changes in those runs' decisions.

The runs themselves stay in `runs/`, under the ids in `paper_runs.txt`,
`scale_runs.txt` and `development/runs.txt`.
