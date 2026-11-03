# Run log for the research article's reruns

Every command run for the reruns, in order, with each shell command as the
shell ran it, variables expanded. The steps are those of RUNNING_EXPERIMENTS.md. Entries from
2026-10-09 on are appended by `experiments/logged.sh`, which also saves each
command's full output in `logs/`. Entries before it were written by hand from
the session's record.

## Preparation (2026-10-07, by Claude, no results kept)

The BEAR clone the runs use, made by WSL's git so that each run records its
commit:

```
cd /mnt/c/tmp
git clone -q --no-checkout /mnt/c/Users/Scott/Documents/Work/bear-dev bear-hearthwick-paper
cd bear-hearthwick-paper
git fetch -q /mnt/c/Users/Scott/Documents/Work/bear-dev refs/remotes/origin/main
git checkout -q --detach FETCH_HEAD          # 5334e1e
```

Checks while preparing, each written to a temporary directory and not kept:
- the retrieval ablation's new arms and counts, three arms for 0.3 in-game
  days, seed 0 (t=0 with and without the old behavior gave the same choices,
  and t=0.15 set something aside in 37 of 144 decisions)
- the action counterfactual over two September runs, 30 decisions each, with
  random donors
- `experiments/threshold_replay.py` on September seed 1 (99.6% reproduced,
  15.9% changed with the fix)
- a run of 0.1 in-game days without the model, to check what meta.json records
- Hearthwick's tests, 522 passing with this BEAR and with f9b509c

## Freeze (2026-10-09 05:44 EDT, by Claude)

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git commit -m "RUNNING_EXPERIMENTS.md: the freeze is done, and a short trial with the model comes first"   # f48811c
git tag paper-v2 f48811c
git worktree add -q --detach ../hearthwick-paper-v2 paper-v2
ln -s ../hearthwick-evolving-village/runs ../hearthwick-paper-v2/runs
cd /mnt/c/tmp/bear-hearthwick-paper
git checkout -q --detach 5334e1e
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v2
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper \
  /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python \
  -c 'from hearthwick.events import code_versions; print(code_versions())'
# {'hearthwick': 'f48811c', 'bear': '5334e1e', 'bear_version': '0.2.0'}
```

f48811c differs from 381c216, the commit the tests passed on, only in
RUNNING_EXPERIMENTS.md. `experiments/logged.sh` was added on main after the
freeze. It records commands and does not touch the frozen code.

## Commands

### 2026-10-09 05:50 to 05:58 EDT, by Scott (written by hand, superseded)

The threshold ablation, run before `experiments/logged.sh` existed, so this
entry was written afterwards. Scott pasted these commands exactly as Claude
gave them, in a WSL shell:

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-paper-v2
export PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper
export PY=/mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python
for seed in 0 1 2; do
  $PY experiments/retrieval_ablation.py --village greater --days-per-year 28 \
      --seed $seed --out results/threshold_ablation/seed$seed
done
```

- Hearthwick f48811c (`paper-v2`), BEAR 5334e1e, both recorded clean in each
  result's meta
- runs made, seven arms per seed:
  - seed 0: 20261009-055034 to 20261009-055242
  - seed 1: 20261009-055316 to 20261009-055530
  - seed 2: 20261009-055604 to 20261009-055811
- results: `results/threshold_ablation/seed{0,1,2}` in the worktree
- the two t=0 arms gave identical choices in every seed, and t=0.15 set
  something aside in 9.4%, 14.5% and 12.1% of decisions without changing a
  choice

Superseded. `experiments/retrieval_ablation.py` built its configuration
without the paper profile, so these arms ran with every mechanic of v0.2
switched on (money, materials, wants, search, vehicles, designs, mortality
and more), which is not the paper's village. Checking them also showed that
the paper profile still loaded the instructions of those mechanics, and
ranked six of them. Both are fixed on main (the ablation's `--profile`, and
instructions loaded only with their switch), and the ablation is to be run
again on the re-frozen build. The superseded results are kept in
`results/superseded/threshold_ablation_all_mechanics_on/` in the worktree.

### 2026-10-09 06:10 EDT, by Claude (checks, no results kept)

- One in-game day with the paper profile at 28-day years, without the model,
  in a temporary directory: no instruction added since the paper-development
  build was chosen, but six wants and search instructions took 479 places in
  the logged top-12 rankings of 342 decisions.
- `corpus_composition` for the paper profile after the fix: 153 authored
  instructions, 114 with an action marker, the same 153 as the
  paper-development build (5a25290).

### 2026-10-09 06:47 EDT, by Claude (re-freeze)

After committing the fix as c378c7f, with all 527 tests passing on BEAR
5334e1e and on f9b509c:

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git tag paper-v2.1 c378c7f
cd ../hearthwick-paper-v2
mkdir -p results/superseded
mv results/threshold_ablation results/superseded/threshold_ablation_all_mechanics_on
git checkout -q --detach paper-v2.1
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper \
  /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python \
  -c 'from hearthwick.events import code_versions; print(code_versions())'
# {'hearthwick': 'c378c7f', 'bear': '5334e1e', 'bear_version': '0.2.0'}
```

The worktree keeps its name, `hearthwick-paper-v2`, and now holds `paper-v2.1`.

### 2026-10-09 06:58 to 07:06 EDT, by Claude (check, no results kept)

The long run's self-written lessons were mostly refused, because consolidation
showed the model bare marker names (results/long_run/REPORT.md). Before
changing it, a scratch script replayed 30 of the long run's consolidations
through the model on 8355, with the paper profile's 18 markers shown as bare
names and then as signatures, 60 calls in all, and checked every lesson:

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper .venv/bin/python \
    <scratchpad>/signature_check.py
```

- bare names: 24 accepted, 66 refused
- signatures: 75 accepted, none refused

A check before the fix, not a result. The same replay is now
`experiments/signature_check.py`, whose run is logged below.

### 2026-10-09 07:38 EDT, by Claude (re-freeze)

After committing the consolidation fix as dae4771, with all 527 tests passing
on BEAR 5334e1e and on f9b509c (and the 7 new ones run on both apart):

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git tag paper-v2.2 dae4771
cd ../hearthwick-paper-v2
git checkout -q --detach paper-v2.2
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper \
  /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python \
  -c 'from hearthwick.events import code_versions; print(code_versions())'
# {'hearthwick': 'dae4771', 'bear': '5334e1e', 'bear_version': '0.2.0'}
```

Nothing had been run on `paper-v2.1`, so nothing is set aside. The worktree
now holds `paper-v2.2`.

### 2026-10-09 07:39:00 EDT

- directory: `/mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village`
- Hearthwick here: paper-v2.2, BEAR: 5334e1e
- PYTHONPATH=`/mnt/c/tmp/bear-hearthwick-paper`
- output: `results/paper_v2/logs/20261009-073856.log`

```
.venv/bin/python experiments/signature_check.py 20261003-093714-seed1 
```
- ended 2026-10-09 07:45:24 EDT with exit status 0

### 2026-10-12 23:38 EDT, by Claude (re-freeze)

The model server on 8355 stopped filling in omitted sampling values from the
model card (model-server 4a91a04). The September runs had sent only a
temperature and got top-p 0.95 and top-k 20 that way. So Hearthwick now sends
all three itself, committed as c5900b3. The replay with every switch off was
unchanged (`experiments/replay_fingerprint.py . --ticks 144`, 500 lines,
90b674e3f38c32c5), and all tests passed on BEAR 5334e1e (553, 4 skipped) and
on 599554c (578).

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git tag paper-v2.3 c5900b3
cd ../hearthwick-paper-v2
git checkout -q --detach paper-v2.3
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper \
  /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python \
  -c 'from hearthwick.events import code_versions; print(code_versions())'
# {'hearthwick': 'c5900b3', 'bear': '5334e1e', 'bear_version': '0.2.0'}
```

Nothing had been run on `paper-v2.2`, so nothing is set aside. The worktree
now holds `paper-v2.3`.

### 2026-10-13 04:35 EDT, by Claude (re-freeze)

A run never stops for a model call the server does not answer. It goes on
without the line, passes the news on word for word, or writes no lessons, and
`paper-v2.3` recorded that nowhere that was checked. 8355 crashed three times
on 2026-10-12 and keeps the speculative decoding behind those crashes. So
Hearthwick now counts those calls (`speech_errors` in each run's `meta.json`,
kept across resumes), and `reproduce.sh` and `experiments/unanswered.py`
refuse any run or counterfactual that has one or was never measured
(5775fa2, then acded7e after bear-dev-16 found that a missing count read as
zero). The replay with every switch off was unchanged
(`experiments/replay_fingerprint.py . --ticks 144`, 500 lines,
90b674e3f38c32c5), and all tests passed on BEAR 5334e1e (560, 4 skipped) and
on 599554c (585).

8355 went back to generation-config `auto` at 04:24 EDT (bear-dev-16), with
MTP kept.

```
cd /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village
git tag paper-v2.4 acded7e
cd ../hearthwick-paper-v2
git checkout -q --detach paper-v2.4
PYTHONPATH=/mnt/c/tmp/bear-hearthwick-paper \
  /mnt/c/Users/Scott/Documents/Work/hearthwick-evolving-village/.venv/bin/python \
  -c 'from hearthwick.events import code_versions; print(code_versions())'
# {'hearthwick': 'acded7e', 'bear': '5334e1e', 'bear_version': '0.2.0'}
```

Nothing had been run on `paper-v2.3`, so nothing is set aside. The worktree
now holds `paper-v2.4`.
