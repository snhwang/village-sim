#!/usr/bin/env python3
"""Does a change leave a run with its switches off as it was? Run the
greater village without the model for a fixed number of ticks and write
every decision, with everyone's position and the granary after each tick,
so two checkouts can be compared line for line.

    python experiments/replay_fingerprint.py <checkout> [--ticks 72] [--out FILE]

Run it once with the new code and once with a checkout of the commit before
the change (a detached ``git worktree add <dir> <commit>``), both in WSL with
the embedding service up, then compare the two files with cmp. It uses the
embedding service as real runs do. BM25 would score differently, and only
the service shows the batch effect that made gated instructions change other
instructions' vectors (corpus.SWITCHED_DIRS). Prints the line count and a
short hash.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkout", type=Path, help="the repository whose hearthwick package to run")
    ap.add_argument("--ticks", type=int, default=72)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--with", dest="turn_on", action="append", default=[],
                    help="a switch to turn on, such as bear_memory, to check that it "
                         "changes nothing it should not. Repeatable")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(args.checkout.resolve()))
    from hearthwick.config import SimConfig
    from hearthwick.sim import Simulation

    sim = Simulation(SimConfig(seed=args.seed, village="greater", llm_base_url=None,
                               runs_dir=Path(tempfile.mkdtemp()),
                               **{name: True for name in args.turn_on}), None)
    lines: list[str] = []

    async def go() -> None:
        for _ in range(args.ticks):
            await sim.step()
            for cid in sorted(sim.decisions):
                d = sim.decisions[cid]
                if d["t"] == sim.clock.tick - 1:
                    lines.append(json.dumps({"t": d["t"], "c": cid, "chosen": d.get("chosen"),
                                             "actions": d.get("actions"), "tags": d.get("tags")},
                                            sort_keys=True))
            lines.append(json.dumps({"t": sim.clock.tick, "pos": sorted(
                (c.id, list(c.pos)) for c in sim.characters.values() if c.alive),
                "food": round(sim.world_agent.state.food.store, 6)}, sort_keys=True))

    asyncio.run(go())
    sim.close()
    text = "\n".join(lines)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(args.checkout, len(lines), hashlib.sha256(text.encode()).hexdigest()[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
