"""Run logging: one JSONL event stream, one JSONL frame stream, run metadata.

Every figure and every replay is built from these files alone.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from hearthwick.config import ROOT


def git_commit(path: Path) -> str | None:
    """The commit a checkout is at, with ``-dirty`` if tracked files are modified.

    Untracked files are not code, and scanning them is what made this fail:
    BEAR's ``git status`` took 17 seconds from WSL, past the timeout, and
    the paper's runs of 2026-09-27 recorded no bear commit at all. So the
    check ignores untracked files, and a check that still times out keeps the
    commit and says the state is unknown rather than dropping both.
    """
    try:
        commit = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not commit:
        return None
    try:
        dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain",
                                "--untracked-files=no"],
                               capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return f"{commit}-unknown"
    return f"{commit}-dirty" if dirty else commit


def code_versions() -> dict:
    import bear

    bear_root = Path(bear.__file__).resolve().parent.parent
    return {
        "hearthwick": git_commit(ROOT),
        "bear": git_commit(bear_root),
        "bear_version": getattr(bear, "__version__", None),
    }


class RunLog:
    def __init__(self, runs_dir: Path, seed: int, meta: dict):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{stamp}-seed{seed}"
        self.dir = runs_dir / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta = {"run_id": self.run_id, "started": datetime.now().isoformat(timespec="seconds"),
                     **meta, "code": code_versions()}
        self.write_meta()
        self._events = open(self.dir / "events.jsonl", "w", encoding="utf-8")
        self._frames = open(self.dir / "frames.jsonl", "w", encoding="utf-8")
        self._pending: list[dict] = []
        self.recent: list[dict] = []

    def adopt(self, run_dir: Path, turn_on: list[str] | None = None) -> None:
        """Continue an earlier run's log instead of the fresh one just opened.

        A run interrupted six times should be one record, not seven. The new
        directory this log made is discarded, and the old files are reopened
        for appending -- appending, because they were opened for writing, and
        resuming into "w" would erase the hours the checkpoint exists to save.

        ``turn_on`` names mechanics this run takes up from now on. They are
        written into its recorded settings, so a later resume keeps them, and
        the resumption notes when they began.
        """
        self._events.close()
        self._frames.close()
        fresh = self.dir
        self.run_id = run_dir.name
        self.dir = run_dir
        self._events = open(self.dir / "events.jsonl", "a", encoding="utf-8")
        self._frames = open(self.dir / "frames.jsonl", "a", encoding="utf-8")
        existing = json.loads((self.dir / "meta.json").read_text(encoding="utf-8"))
        resumed = {"at": datetime.now().isoformat(timespec="seconds"),
                   "code": code_versions()}
        if turn_on:
            resumed["turned_on"] = sorted(set(turn_on))
            existing.setdefault("config", {}).update({m: True for m in turn_on})
        existing.setdefault("resumed", []).append(resumed)
        self.meta = existing
        self.write_meta()
        for name in ("events.jsonl", "frames.jsonl", "meta.json"):
            (fresh / name).unlink(missing_ok=True)
        fresh.rmdir()

    def write_meta(self) -> None:
        (self.dir / "meta.json").write_text(json.dumps(self.meta, indent=2), encoding="utf-8")

    def event(self, tick: int, type: str, **data: Any) -> dict:
        record = {"t": tick, "type": type, **data}
        self._events.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._pending.append(record)
        self.recent.append(record)
        if len(self.recent) > 500:
            del self.recent[:100]
        return record

    def frame(self, tick: int, clock: dict, characters: list[list],
              building: dict | None = None, money: dict | None = None) -> dict:
        record = {"t": tick, "clock": clock, "c": characters}
        # The house going up (hearthwick/building.py), only while there is one.
        if building:
            record["b"] = building
        # Each villager's coins and what its goods would fetch
        # (hearthwick/economy.py), each in-game hour.
        if money:
            record["m"] = money
        self._frames.write(json.dumps(record, separators=(",", ":")) + "\n")
        return record

    def drain(self) -> list[dict]:
        out, self._pending = self._pending, []
        return out

    def flush(self) -> None:
        self._events.flush()
        self._frames.flush()

    FILES = ("events.jsonl", "frames.jsonl")

    def sizes(self) -> dict[str, int]:
        """How much of each log is written, for a checkpoint to record."""
        self.flush()
        return {name: (self.dir / name).stat().st_size for name in self.FILES}

    def truncate_to(self, sizes: dict[str, int]) -> None:
        """Cut the logs back to what they held when a checkpoint was taken.

        A run killed outright, by a reboot or a crash, has logged ticks past
        its last checkpoint, and the resumed run would log them again. Cut
        back, the log stays one record. Never longer: a log shorter than the
        record is left alone.
        """
        self.flush()
        for name, handle in (("events.jsonl", "_events"), ("frames.jsonl", "_frames")):
            path = self.dir / name
            if name in sizes and path.stat().st_size > sizes[name]:
                getattr(self, handle).close()
                with open(path, "r+b") as f:
                    f.truncate(sizes[name])
                setattr(self, handle, open(path, "a", encoding="utf-8"))

    def close(self, **final: Any) -> None:
        if self._events.closed:
            return          # closing twice is not an error
        self.flush()
        self._events.close()
        self._frames.close()
        self.meta["finished"] = datetime.now().isoformat(timespec="seconds")
        self.meta.update(final)
        self.write_meta()
