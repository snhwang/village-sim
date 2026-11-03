#!/usr/bin/env bash
# Run a command and record it in the research article's run log
# ($RUN_LOG, results/paper_v2/RUN_LOG.md unless set, and
# results/paper_v3/RUN_LOG.md for the paper-v3 freeze): when, in which
# directory, with which code and settings, the command as the shell ran it
# (variables expanded), the runs it made, and how it ended. Its full output
# goes to logs/ beside the run log.
#
#   bash <repository>/experiments/logged.sh <command> [args ...]
#
# It lives on main and is called by its full path, so the frozen worktree
# (tag paper-v2) needs no copy. A key given on the command line is written
# as (set), never as its value.
set -uo pipefail

# The repository this script lives in, so the default run log is its own.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOG=${RUN_LOG:-$HERE/results/paper_v2/RUN_LOG.md}
OUTDIR=$(dirname "$LOG")/logs
mkdir -p "$OUTDIR"

# The process id too, since commands started in the same second, such as the
# three long runs started together on 2026-10-21, otherwise shared one file.
stamp=$(date '+%Y%m%d-%H%M%S')-$$
out="$OUTDIR/$stamp.log"
# The command as entered, with any key on the command line redacted.
cmd=$(printf '%q ' "$@" | sed -E 's/(--(llm|embed)-api-key) [^ ]+/\1 (set)/g')
hearthwick=$(git -C "$PWD" describe --tags --always --dirty 2>/dev/null || echo "not a checkout")
bear_dir=${PYTHONPATH:-}
bear_dir=${bear_dir%%:*}
bear=$( [ -n "$bear_dir" ] && git -C "$bear_dir" rev-parse --short HEAD 2>/dev/null || echo "the venv's own")

{
  echo ""
  echo "### $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo ""
  echo "- directory: \`$PWD\`"
  echo "- Hearthwick here: $hearthwick, BEAR: $bear"
  for name in PYTHONPATH PY LLM_ARGS DAYS DAYS_PER_YEAR PROFILE THRESHOLD SEEDS RUNS; do
    if [ -n "${!name:-}" ]; then echo "- $name=\`${!name}\`"; fi
  done
  echo "- output: \`${out#"$HERE"/}\`"
  echo ""
  echo '```'
  echo "$cmd"
  echo '```'
} >> "$LOG"

"$@" 2>&1 | tee "$out"
status=${PIPESTATUS[0]}

runs=$(grep -oE '^run [0-9]{8}-[0-9]{6}-seed[0-9]+' "$out" | awk '{print $2}' | tr '\n' ' ')
{
  if [ -n "$runs" ]; then echo "- runs made: $runs"; fi
  echo "- ended $(date '+%Y-%m-%d %H:%M:%S %Z') with exit status $status"
} >> "$LOG"
exit "$status"
