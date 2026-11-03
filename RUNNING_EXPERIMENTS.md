# Running the research article's experiments

The commands that make every result in the research article (the paper in
`paper-hearthwick-ACMGames`). Scott runs them by hand, so that what is run is
what a reader would run. First prepared on 2026-10-07, rewritten on
2026-10-18 for the `paper-v3` freeze, and again on 2026-10-22 for
`paper-v4`. The plan behind it, with its decisions, is `PAPER_RUN_PLAN.md`.

To run them yourself, check out the commit tagged `paper-v4` and set up as
the README says, with public BEAR v0.3.0, which releases commit 1ceebc7 of BEAR's
development repository, named below. Serve the paper's models from `serving/`, with `SGLANG_IMAGE` set as
its `.env.example` shows to serve them exactly as these runs were served. In
the shell set-up below, point `RUN_TREE` and `ANALYSIS_TREE` at your
checkout (one checkout can be both), `PY`, `RUN_LOG` and `LOGGED` at yours,
and leave out `PYTHONPATH`. `experiments/reproduce.sh`, which the paper's
appendix gives, runs step 3's simulations and every analysis in one go.

Settled with Scott on 2026-10-17 and 2026-10-18:
- one frozen build for everything, so the paper reports one build
- `--profile illustrative` (README section 6), which sets every switch and
  28-day years: creation and leisure off, the economy on, the memory gene off
- six measured runs, seeds 1 to 6 of the greater village, 40 in-game days each
- three long runs, seeds 1 to 3, 280 days (ten years) each
- the village of 300, ten days
- the threshold chosen from the ablation in step 1, under this profile
- one model server for every run and every replay, since the replays
  measure that server's own nondeterminism
- the paper describes only this build, and none of the earlier runs

Settled on 2026-10-21 ("fix and rerun. stop the 300 run."): the `paper-v3`
runs had a warning loop (SPECIFICATION-warnings.md section 13), so the fix
goes in, the build is frozen again as `paper-v4`, and every step is run
again. None of the `paper-v3` runs go into the paper. Their record stays in
`results/paper_v3/`.

Runs are made in one frozen checkout and analysed in another, so the run
checkout stays clean (step 0). Every step that writes results writes them
under `results/` of the analysis checkout, and step 6 brings them to main.

## 0. Freeze and check (done 2026-10-22)

- Hearthwick: tag `paper-v4` (0313244). Against `paper-v3.1` it adds
  `fresh_warnings`, on in the illustrative profile: a warning is about the
  fresh news that unlocked it, passes on only that, and goes only to someone
  the warner has not told it. The health check gains two warning checks.
- BEAR: unchanged, commit 1ceebc7 of its development repository, in the WSL clone
  `/mnt/c/tmp/bear-paper-v3`, so each run records the commit. Its public
  release is [snhwang/bear](https://github.com/snhwang/bear) v0.3.0
  (2398e5a, its release of 1ceebc7), which is what a reader installs
  in place of the clone.
- The trials that led to it: `results/fresh_trial/` (56 days, seeds 1 to 3,
  twice). The second, on the fixed build, flags nothing.
- Checked in the run checkout before any run: all 656 tests pass with this
  BEAR, and the switches-off replay matches its reference (500 lines,
  90b674e3f38c32c5). The checkout stayed clean.
- Two checkouts of `paper-v4`, both with `runs/` linked to main's. The
  analyses write into files git tracks under `results/`, which makes a
  checkout count as modified, and a run started there would record its
  commit as `-dirty`. So the long runs and the village of 300 are made in
  `/mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v4`, which no analysis
  writes into, and everything else in
  `/mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v4-analysis`. The six
  measured runs are made there too, by the script that then analyses them,
  since it writes nothing until all six are done.

How it was done, in WSL:

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git tag paper-v4 0313244
git worktree add --detach ../hearthwick-paper-v4 paper-v4
ln -s ../hearthwick-evolving-village/runs ../hearthwick-paper-v4/runs
git worktree add --detach ../hearthwick-paper-v4-analysis paper-v4
ln -s ../hearthwick-evolving-village/runs ../hearthwick-paper-v4-analysis/runs
```

Then, in every shell used for steps 1 to 6:

```
export RUN_TREE=/mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v4
export ANALYSIS_TREE=/mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v4-analysis
export PYTHONPATH=/mnt/c/tmp/bear-paper-v3
export PY=/mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python
export RUN_LOG=/mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/results/paper_v4/RUN_LOG.md
export LOGGED="bash /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/experiments/logged.sh"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export LLM_ARGS="--llm-url http://localhost:8355/v1 --model Qwen3.8-27B"
export THRESHOLD=0.15
cd $RUN_TREE
$PY -c 'from hearthwick.events import code_versions; print(code_versions())'
cd $ANALYSIS_TREE
$PY -c 'from hearthwick.events import code_versions; print(code_versions())'
```

Both lines must show 0313244 and BEAR 1ceebc7, neither ending in `-dirty`.
`PYTHONPATH` puts the frozen BEAR ahead of the venv's own, which is
installed editable from BEAR's development repository and moves when it does. Never rely
on it. The thread limits keep a large village from spreading each memory
lookup over every core. `THRESHOLD` is the paper-v3 choice. Step 1 checks
it still holds.

Every command goes through `$LOGGED`, which appends it to
`results/paper_v4/RUN_LOG.md` on main, as the shell ran it (variables
expanded), with the time, directory, code versions and settings, the runs it
made and how it ended. A command run without it should be added to that log
by hand. The log lives on main, never in a checkout that runs start in,
since appending to a tracked file there would mark the runs `-dirty`.

The model server is 8355: SGLang serving `unsloth/Qwen3.8-27B-NVFP4` as
`Qwen3.8-27B`, with DFlash speculative decoding (`serving/`, profile
`llm`). The embedder is Nemotron on 8360 (profile `embed`). Every
call sends temperature 0.8, top-p 0.95 and top-k 20, so the sampling does not
depend on the server's defaults.

Exactly what served the paper-v4 runs (images, model revisions, every launch
argument, and SGLang issue 37817 in that build) is in
`results/paper_v4/SERVING.md`. Its two images are tagged `paper-v4/...` so
that they survive the move to SGLang v0.5.21. Keep them, and the model
snapshots it names, in case the paper's runs are ever served again.

If a server stops answering, a run waits for it, up to 30 minutes, and
carries on when it is back. A lockstep run's outcome does not change, and
its record counts the outage. The model server restarts itself after a GPU
reset, and the embedder does too. A model call
the server never answered after that wait costs a redone run, since every
step below refuses a run with one (`experiments/unanswered.py`). A run that
stops on a failure keeps its last checkpoint taken between ticks, and the
long runs resume from it (step 4).

Run the steps one after another, so that the replays in step 3 have the
model server to themselves, as they did for every earlier set.

## 1. The threshold ablation (no model, about 45 minutes)

In the analysis checkout:

```
cd $ANALYSIS_TREE
for seed in 1 2 3 4 5 6; do
  $LOGGED $PY experiments/retrieval_ablation.py --village greater \
      --profile illustrative --seed $seed --out results/threshold_ablation_v4/seed$seed
done
```

Done when `results/threshold_ablation_v4/seed{1..6}/retrieval_ablation.json`
exist. Two checks before reading anything else:
- In each seed, the arms `soft tags, service, t=0` and
  `soft tags, service, t=0, restored` have the same `choices_digest`. At t=0
  nothing is set aside, so the old behavior cannot matter. If they differ,
  stop: something other than the threshold differs between the arms.
- The `Set aside` column is 0% at t=0 and above 0% at 0.15 and 0.40, so the
  threshold fired where it should.

Under `paper-v3`, t=0.15 made exactly the same choices as t=0 in every seed
(the same `choices_digest`), so it set aside only candidates that would not
have won, and Scott chose `THRESHOLD=0.15`. If the `t=0` and `t=0.15` arms
again have the same `choices_digest` in every seed, keep it. If not, stop
and choose again before step 2.

Done on 2026-10-22 on `paper-v4`. All six seeds pass both checks, none fell
back to BM25, and t=0.15 again made the same choices as t=0 in every seed,
so `THRESHOLD=0.15` stays. Similarity decided 75.0 to 76.9% at t=0, 72.7 to
76.9% at t=0.15 and 57.8 to 63.4% at t=0.40. Decisions with something set
aside were 0%, 4.9 to 11.7% and 89.5 to 90.4%.

## 2. A short trial with the model (about 5 minutes)

Two in-game days on the frozen build, in the run checkout, before hours are
spent. Two, because under this profile no news is passed on during the
first day, so the lens first rewords news on the second:

```
cd $RUN_TREE
$LOGGED $PY -m hearthwick run --days 2 --profile illustrative \
    --threshold $THRESHOLD --seed 0 --village greater --llm-concurrency 8 $LLM_ARGS
$LOGGED $PY - <<'EOF'
import glob, json, os
d = max(glob.glob("runs/*"), key=os.path.getmtime)
m = json.load(open(f"{d}/meta.json"))
kinds = [json.loads(l)["type"] for l in open(f"{d}/events.jsonl")]
print(d, "finished:", m.get("finished"), "code:", m["code"])
print("speech calls:", m.get("speech_calls"), "failures:", m.get("speech_failures"),
      "unanswered:", m.get("speech_errors"), "seconds:", m.get("speech_seconds"))
print("utterances:", kinds.count("utterance"), "lens calls:", kinds.count("lens"))
EOF
```

It passes when the run has a `finished` time, both commits are clean, there
are utterances and lens calls, failures are few, and no call went
unanswered. The trial run stays in `runs/` but is not one of the paper's
runs.

Done on 2026-10-22 on `paper-v4`: `20261022-065449-seed0` passed, with 260
model calls, none failed or unanswered, 259 utterances and a lens call on the
second day, in 165 seconds.

## 3. The six measured runs (model, about 4 hours, then about 2.5 hours of analysis)

In the analysis checkout, which is clean until all six are done:

```
cd $ANALYSIS_TREE
DAYS=40 DAYS_PER_YEAR=28 PROFILE=illustrative THRESHOLD=$THRESHOLD \
  setsid nohup $LOGGED bash experiments/reproduce.sh \
  > runs/paper_v4_measured.log 2>&1 < /dev/null &
```

`reproduce.sh` reads `PY` and `LLM_ARGS` from the environment. It runs seeds
1 to 6 one after another, writes their ids to `results/paper_runs.txt`, then
runs every analysis, the counterfactuals included, and ends with
`paper/check_numbers.py`. Each run is done when its `runs/<id>/meta.json` has
a `finished` time. To follow it, `tail -f runs/paper_v4_measured.log`. If
the script stops partway, rerun it with the finished ids, which skips the
runs and redoes only the analysis:

```
RUNS="<id> <id> ..." DAYS_PER_YEAR=28 PROFILE=illustrative THRESHOLD=$THRESHOLD \
  $LOGGED bash experiments/reproduce.sh
```

`reproduce.sh` checks every run with `experiments/unanswered.py`, reused ones
included. It finishes all the seeds, then stops before the analysis and names
the ones to redo. Redo them with `SEEDS="<seeds>"` in place of the default,
then analyse all six with `RUNS=` as above. It stops the same way after
either counterfactual if that lost calls, and rerunning with `RUNS=` redoes
it.

Then, still in the analysis checkout:

```
for run in $(cat results/paper_runs.txt); do
  $LOGGED $PY experiments/health_check.py $run --out results/paper_v4/health/$run
done
```

Each health check must flag nothing, or the flag gets a written reason in
`results/paper_v4/notes.md` before the run is used.

Done on 2026-10-22 on `paper-v4`, from 07:04 to 11:39 EDT, with exit status
0. The runs are `20261022-070414-seed1`, `20261022-073709-seed2`,
`20261022-080916-seed3`, `20261022-083715-seed4`, `20261022-090533-seed5`
and `20261022-093732-seed6`, 29 to 37 minutes each, none with an unanswered
call. Decisions only knowledge made possible were 20.7% of all decisions
(35,542 of 172,064), against 31.3% on `paper-v3`, and warnings among them
23,188 against 49,926.

## 4. The three long runs (model, about 12 hours, all three at once)

In the run checkout:

```
cd $RUN_TREE
for seed in 1 2 3; do
  setsid nohup $LOGGED $PY -m hearthwick run --profile illustrative \
      --threshold $THRESHOLD --days 280 --seed $seed --village greater \
      --checkpoint-every 1 $LLM_ARGS \
      > runs/paper_v4_long_seed$seed.log 2>&1 < /dev/null &
done
```

Write the three run ids, one per line, into the analysis checkout's
`results/long_runs_v4/runs.txt`, with a note of when they started. To follow
one, `tail -f` its log. To stop one, `kill -INT` its Python process, and it
finishes the tick, saves and exits. To resume one, with the same environment:

```
setsid nohup $LOGGED $PY -m hearthwick run --resume <run_id> $LLM_ARGS \
    >> runs/paper_v4_long_seed<N>.log 2>&1 < /dev/null &
```

Once all three have finished, in the analysis checkout, for each run and
seed:

```
cd $ANALYSIS_TREE
$LOGGED $PY experiments/unanswered.py runs/<id>/meta.json
$LOGGED $PY experiments/health_check.py <id> --log runs/paper_v4_long_seed<N>.log \
    --out results/long_runs_v4/health/seed<N>
$LOGGED $PY experiments/long_run_report.py <id> --to-day 280 \
    --out results/long_runs_v4/report/seed<N>
$LOGGED $PY experiments/lesson_use.py <id> --out results/long_runs_v4/lesson_use_seed<N>.md
```

The first must end with exit status 0, and the health check must flag
nothing, or the flag gets a written reason in `results/long_runs_v4/runs.txt`.

Done on 2026-10-23 on `paper-v4`. The runs are `20261023-012700-seed1`,
`-seed2` and `-seed3`, started together at 01:26 EDT and finished at 12:56,
12:25 and 11:33 EDT with 59, 56 and 46 people, none with an unanswered call.
Their checks ran on 2026-10-24 with exit status 0. Each health check flags
one thing, the same warning to the same listener again and again in a day,
from storytellers' months-old tales passed on as fresh. Scott counts it a
known defect, fixed after the paper and named in it as future work
(SPECIFICATION-warnings.md section 13), and the reason is written in
`results/long_runs_v4/runs.txt`.

## 5. The village of 300 (model, about 3 hours)

```
cd $RUN_TREE
$LOGGED $PY -m hearthwick run --days 10 --profile illustrative \
    --threshold $THRESHOLD --seed 1 --village town300 --llm-concurrency 8 $LLM_ARGS
cd $ANALYSIS_TREE
$LOGGED $PY experiments/unanswered.py runs/<id>/meta.json
$LOGGED $PY experiments/health_check.py <id> --out results/paper_v4/health/<id>
$LOGGED $PY experiments/scale.py runs/<id>
```

The second command must end with exit status 0, or the run is redone. Done
when `results/scale.json` exists. Record the id and the build in
`results/scale_runs.txt`.

Done on 2026-10-24 on `paper-v4`: `20261024-005651-seed1`, started at 00:56
EDT in the background (`setsid nohup`, log `runs/paper_v4_town300.log`) and
finished at 02:14 EDT, 1,440 ticks in 85 minutes. 11,480 model calls, none
unanswered, and its health check flags nothing.

## 6. Bring the results to main and check the paper

```
$LOGGED cp -r $ANALYSIS_TREE/results/. /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/results/
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
$LOGGED .venv/bin/python paper/check_numbers.py --paper submission
```

`check_numbers.py` lists every number the paper quotes that has moved. The
paper's text is then updated from the new results, and the runs, logs and
results are archived together.

Done on 2026-10-24 at 03:37 EDT. `check_numbers.py` ended with exit status 1,
as expected while the paper still quotes the `paper-v3` runs. Its list is the
start of the paper's update.

## The paper-v3 set (2026-10-18 to 2026-10-21, not used)

Tag `paper-v3` (3207d90), then `paper-v3.1` (a5a1e04), which added only a
figure colour. Steps 1 to 4 were done: the ablation (which chose t=0.15),
the six measured runs and their analysis, and the three long runs, with
their checks. Seed 3's long run flagged a villager stuck in one place, which
led to the warning loop. The village of 300 was stopped at tick 345 of 1440
on 2026-10-21. The commands and their outputs are in
`results/paper_v3/RUN_LOG.md`.
