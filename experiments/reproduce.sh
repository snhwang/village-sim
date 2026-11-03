#!/usr/bin/env bash
# Reproduce every number in the case study (paper-hearthwick-ACMGames, and
# paper/hearthwick_case_study_long.md here), and the results
# on food, traveling storytellers, school and trades in SPECIFICATION.md.
#
#   bash experiments/reproduce.sh                  # six new runs, then every analysis
#   RUNS="<id> <id> ..." bash experiments/reproduce.sh   # reuse runs that exist
#
# Needs the speech model (port 8355) and the embedder (port 8360) running, and
# the project venv at .venv. Six new runs take about an hour, and the analyses
# about another hour and a half, most of it the two counterfactuals.
#
# Each step writes results/<name>.json and .md, so a step that finished does
# not need running again if a later one fails. A new set of runs will not give
# identical numbers. The runs sample speech at temperature 0.8, and the model
# server is not bitwise deterministic, so expect the same findings with nearby
# values. paper/check_numbers.py then shows which quoted numbers moved.
#
# A run or counterfactual that lost model calls to the server going down
# stops the script before anything uses it, and says what to redo. So does a
# run made before those calls were counted, unless ALLOW_UNMEASURED=1 (to
# analyse such runs, the September ones among them).
#
# The research article's reruns (RUNNING_EXPERIMENTS.md) set these. Left
# unset, the script makes the September runs' configuration.
#   DAYS=40            in-game days per run (default 10)
#   DAYS_PER_YEAR=28   year length (default the simulation's, 8)
#   PROFILE=paper      every mechanic added since the paper switched off
#   THRESHOLD=0.15     the similarity threshold (default the simulation's)
#   SEEDS="1 2 3"      which seeds (default 1 to 6)
#   LLM_ARGS="..."     the model server, e.g. "--llm-url ... --model ... --llm-key-env ..."
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
quiet() { grep -vE "^INFO (httpx|hearthwick.llm)" || true; }
RUN_ARGS="--days ${DAYS:-10}"
if [ -n "${DAYS_PER_YEAR:-}" ]; then RUN_ARGS="$RUN_ARGS --days-per-year $DAYS_PER_YEAR"; fi
if [ -n "${PROFILE:-}" ]; then RUN_ARGS="$RUN_ARGS --profile $PROFILE"; fi
if [ -n "${THRESHOLD:-}" ]; then RUN_ARGS="$RUN_ARGS --threshold $THRESHOLD"; fi
RUN_ARGS="$RUN_ARGS ${LLM_ARGS:-}"

if [ -z "${RUNS:-}" ]; then
  echo "=== 1. runs of the greater village ($RUN_ARGS) ==="
  RUNS=""
  for seed in ${SEEDS:-1 2 3 4 5 6}; do
    out=$($PY -m hearthwick run $RUN_ARGS --seed "$seed" --village greater \
          --llm-concurrency 8 2>&1 | quiet)
    echo "$out" | tail -1
    RUNS="$RUNS $(echo "$out" | sed -nE 's/^run ([^:]+):.*/\1/p' | tail -1)"
  done
fi
RUNS=$(echo $RUNS)
FIRST=${RUNS%% *}
echo "runs: $RUNS"
# Every run, new or reused, must have been measured and have lost no model
# call to the server going down (experiments/unanswered.py). All the seeds
# run first, so one outage costs one run, not the night.
METAS=""
for run in $RUNS; do METAS="$METAS runs/$run/meta.json"; done
if ! $PY experiments/unanswered.py ${ALLOW_UNMEASURED:+--allow-unmeasured} $METAS; then
  echo "redo those seeds with SEEDS=\"...\", then analyse all six with RUNS=\"...\"" >&2
  exit 1
fi
echo "$RUNS" > results/paper_runs.txt

echo "=== 2. knowledge flow (sections 5 and 6, Figure 1) ==="
$PY experiments/knowledge_flow.py $RUNS 2>&1 | quiet | tail -20
echo "=== 3. world balance (sections 4 and 7) ==="
$PY experiments/world_balance.py $RUNS 2>&1 | quiet | tail -16
echo "=== 4. memory carryover (section 5) ==="
$PY experiments/memory_carryover.py $RUNS 2>&1 | quiet
echo "=== 5. figures (Figures 2 and 3) ==="
# The provenance figure follows the event's deepest chain. The paper-v3 runs
# named two villagers on theirs (--follow osric thea).
$PY experiments/figures.py "$FIRST" 2>&1 | quiet | tail -6
echo "=== 6. action counterfactual (section 7), every run, a random donor per decision ==="
$PY experiments/counterfactual.py $RUNS --sample 400 2>&1 | quiet | tail -10
echo "=== 7. absorption counterfactual (section 7) ==="
$PY experiments/diffusion_counterfactual.py $RUNS --sample 400 --concurrency 8 2>&1 \
  | quiet | grep -v "calls$" | tail -12
$PY experiments/unanswered.py results/diffusion_counterfactual.json
echo "=== 8. rewording (section 7) ==="
$PY experiments/lens_divergence.py 2>&1 | quiet | tail -10
echo "=== 9. two-step counterfactual (section 7) ==="
$PY experiments/two_step_counterfactual.py $RUNS --concurrency 8 2>&1 \
  | quiet | grep -v "calls$" | tail -14
$PY experiments/unanswered.py results/two_step_counterfactual.json
echo "=== 10. retrieval ablation (section 8) ==="
$PY experiments/retrieval_ablation.py --village greater \
    ${DAYS_PER_YEAR:+--days-per-year $DAYS_PER_YEAR} ${PROFILE:+--profile $PROFILE} \
    2>&1 | quiet | tail -8
echo "=== 11. food, storytellers, school and trades (spec 2.4a, 2.7a, 2.8b) ==="
# On the same six runs as everything else, so every result shares one village.
$PY experiments/food_economy.py $RUNS 2>&1 | quiet | grep -E "^## |^- harvest|fields grew|hungry" || true
$PY experiments/visitors.py $RUNS 2>&1 | quiet | grep -E "^## |^\*\*|No storyteller" || true
$PY experiments/trades.py $RUNS 2>&1 | quiet | grep -E "^## |graduated|qualified" || true
for f in food_runs visitor_runs trades_runs; do echo "$RUNS" > "results/$f.txt"; done
echo "=== 11a. knowledge by day, couples and families (sections 5.3 and 5.7) ==="
$PY experiments/knowledge_by_day.py $RUNS 2>&1 | quiet | tail -4
# Births are listed per family, never pooled (the boundary with the ALife paper).
$PY experiments/couples.py $RUNS 2>&1 | quiet | tail -4 || true
$PY experiments/family.py $RUNS 2>&1 | quiet | tail -4 || true
echo "=== 12. spread across the runs, and choices the threshold restored (sections 3 and 5) ==="
$PY experiments/run_spread.py 2>&1 | quiet | sed -n '5,15p'
echo "=== 13. check the paper against these results ==="
$PY paper/check_numbers.py --run "$FIRST" || true
echo "=== done ==="
