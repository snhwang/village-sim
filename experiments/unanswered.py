#!/usr/bin/env python3
"""Which runs or counterfactual results lost model calls to the server going
down, or were never measured for it. Prints a line for each and exits 1 if
there are any, 0 if every one was measured and clean.

    python experiments/unanswered.py runs/<id>/meta.json ... results/<step>.json
    python experiments/unanswered.py --allow-unmeasured runs/<id>/meta.json ...

A run never stops for a call the server did not answer. It goes on without
the line, passes the news on word for word, or writes no lessons, so a run
the server went down under looks complete (SpeechModel.errors). A run's
meta.json records the count as ``speech_errors``, a counterfactual's results
as ``meta.errors``. One made before the count existed has neither, and one
resumed from such a checkpoint has null. Both count as not measured, never
as clean. experiments/reproduce.sh runs this before anything uses a run.
``--allow-unmeasured`` lets those through, to analyse runs made before the
count, such as the September runs. A run that lost calls is refused anyway.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def unanswered(record: dict) -> int | None:
    """The calls a run or step recorded as unanswered, or None if it was
    not measured."""
    if "speech_errors" in record:                     # a run's meta.json
        return record["speech_errors"]
    return record.get("meta", {}).get("errors")       # a counterfactual's results


def problems(paths: list[str], allow_unmeasured: bool = False) -> list[str]:
    found = []
    for path in paths:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        seed = record.get("config", {}).get("seed")
        what = f"{path}" + (f" (seed {seed})" if seed is not None else "")
        n = unanswered(record)
        if n is None and not allow_unmeasured:
            found.append(f"{what}: not measured for unanswered model calls, so redo it")
        elif n:
            found.append(f"{what}: {n} model calls got no answer from the server, so redo it")
    return found


def main(argv: list[str]) -> int:
    allow = "--allow-unmeasured" in argv
    paths = [a for a in argv if a != "--allow-unmeasured"]
    if not paths:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    found = problems(paths, allow_unmeasured=allow)
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
