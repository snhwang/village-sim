"""Follow a run through its log files, so it can be watched without being touched.

A long run is a headless ``python -m hearthwick run`` that checkpoints and
resumes. It writes one frame per tick to ``frames.jsonl`` and every event to
``events.jsonl``, and flushes both each tick. Watching it means reading those
files as they grow. The viewer and the simulation share nothing but the files,
so opening, closing or crashing a browser tab cannot stop, slow or corrupt a
run, and a run started last week can be watched today.

The same reader replays a finished run from its first frame, at whatever rate
the viewer asks for, and switches to following the live end once it catches up.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path

from hearthwick.world import Place, World

# A run counts as live when its frames have been written to recently. Finished
# runs record "finished" in meta.json, but a run killed by a power cut never
# does, so the file's age is the test that cannot be wrong for long.
LIVE_WITHIN_SECONDS = 60


class Tail:
    """Complete JSON lines appended to a file since the last read."""

    def __init__(self, path: Path, offset: int = 0):
        self.path = path
        self.offset = offset
        self._partial = b""

    def at_end(self) -> "Tail":
        self.offset = self.path.stat().st_size if self.path.exists() else 0
        self._partial = b""
        return self

    def read(self, limit: int = 1 << 20) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            chunk = f.read(limit)
        self.offset += len(chunk)
        data = self._partial + chunk
        lines = data.split(b"\n")
        # The last piece is either empty or a line still being written.
        self._partial = lines.pop()
        out = []
        for line in lines:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


def last_lines(path: Path, count: int, block: int = 1 << 16) -> list[dict]:
    """The last ``count`` complete JSON lines of a file, read from the end."""
    if not path.exists() or count <= 0:
        return []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        data, pos = b"", end
        while pos > 0 and data.count(b"\n") <= count:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    lines = [line for line in data.split(b"\n") if line.strip()]
    if not data.endswith(b"\n") and lines:
        lines.pop()                      # still being written
    out = []
    for line in lines[-count:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def reversed_events(path: Path, block: int = 1 << 16) -> Iterator[dict]:
    """Events from the newest backwards, without reading the whole file."""
    if not path.exists():
        return
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos, rest = f.tell(), b""
        while pos > 0:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + rest
            lines = data.split(b"\n")
            rest = lines.pop(0)          # may continue in the previous block
            for line in reversed(lines):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        if rest.strip():
            try:
                yield json.loads(rest)
            except json.JSONDecodeError:
                pass


def is_live(run_dir: Path) -> bool:
    """Being written to now: frames recently written, and not since closed.

    A run that ends records "finished" in meta.json at its last write. A run
    that is resumed keeps that stamp but writes after it, so the stamp only
    counts when it is at least as new as the frames.
    """
    import time
    from datetime import datetime

    frames = run_dir / "frames.jsonl"
    if not frames.exists():
        return False
    written = frames.stat().st_mtime
    if time.time() - written >= LIVE_WITHIN_SECONDS:
        return False
    try:
        finished = json.loads((run_dir / "meta.json").read_text(encoding="utf-8")).get("finished")
        if finished and datetime.fromisoformat(finished).timestamp() >= written - 2:
            return False
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return True


def world_for(run_dir: Path, data_dir: Path, grown: bool = True) -> World:
    """The map a run was simulated on, from the village its config names.

    Villagers clear new ground and crafters build houses, so the map changes
    during a run. With ``grown`` the places are as they stand now, and without
    it as they began, for a viewer replaying the run from its start.
    """
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    village = (meta.get("config") or {}).get("village") or meta.get("village")
    if village and village != "hearthwick" and (data_dir / "villages" / village).is_dir():
        world = World.from_yaml(data_dir / "villages" / village / "village.yaml")
    else:
        world = World.from_yaml(data_dir / "world" / "village.yaml")
    if grown and (run_dir / "events.jsonl").exists():
        # The events that change the map, kept by the run's record, so a
        # viewer's arrival does not read the whole log again. When it was
        # read in full each time, the live village's log of 2.4 GB held the
        # server for two minutes per viewer (2026-10-01), and the village
        # stopped with it.
        for e in _record(run_dir).map_events:
            _change_map(world, e)
    return world


def _change_map(world: World, e: dict) -> None:
    kind = e["type"]
    if kind == "place_grown":
        world.set_rect(e["place"], e["rect"])
    elif kind == "place_added":
        world.add_place(Place.from_dict(e["place"]))
    elif kind == "place_removed":
        world.remove_place(e["place"])
    elif kind == "land_grown":
        world.width = e["width"]
        for rid, rect in e["roads"].items():
            world.set_rect(rid, rect)


def roster(run_dir: Path) -> list[dict]:
    """Every villager the run has had, from its roster events. The roster is
    written when a run starts and again when one resumes, and a visitor adds
    itself when it arrives, so all of them are kept, by the run's record."""
    return list(_record(run_dir).people.values())


# The events that change the map (world_for), in the order they happened.
MAP_EVENTS = ("place_grown", "place_added", "place_removed", "land_grown")
# What changes who a villager is after its roster line was written.
PERSON_EVENTS = ("persona", "stage_change", "took_up_trade", "apprenticed")
_WANTED = tuple(f'"{k}"'.encode() for k in ("roster",) + MAP_EVENTS + PERSON_EVENTS)


class _Record:
    """Who a run's villagers are, and what changed the map, read from its
    log so far."""

    def __init__(self) -> None:
        self.offset = 0
        self.map_events: list[dict] = []
        self.people: dict[str, dict] = {}             # every villager the run has had

    def read(self, raw: bytes) -> None:
        if not any(k in raw for k in _WANTED):
            return
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            return
        kind = e.get("type")
        if kind in MAP_EVENTS:
            self.map_events.append(e)
        elif kind == "roster":
            for c in e.get("characters", []):
                self.people[c["id"]] = c
        elif kind in PERSON_EVENTS and e.get("character") in self.people:
            # A villager's roster line is written when it is born or arrives,
            # so who it has become since comes from these (grown personas,
            # hearthwick/family.py), and a viewer arriving now sees it as it is.
            person = self.people[e["character"]]
            if kind == "persona":
                person.update(persona=e["persona"], stage=e["stage"], role=e.get("role"),
                              trade=e.get("trade"))
            elif kind == "stage_change":
                person["stage"] = e["now"]
            elif kind == "took_up_trade":
                person["role"] = e["trade"]
            else:
                person.update(trade=e["trade"], mentor=e.get("master"))


_records: dict[str, _Record] = {}
# One reader at a time: viewers arrive on worker threads (server.py).
_reading = threading.Lock()


def _record(run_dir: Path) -> _Record:
    """A run's record, read on from where the last call stopped, so a viewer
    arriving at a run a week old does not read the whole log again."""
    path = run_dir / "events.jsonl"
    key = str(path.resolve())
    with _reading:
        size = path.stat().st_size if path.exists() else 0
        rec = _records.get(key)
        if rec is None or size < rec.offset:
            # New, or cut back to a checkpoint on resume: read it from the start.
            rec = _records[key] = _Record()
        if size > rec.offset:
            with open(path, "rb") as f:
                f.seek(rec.offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break           # a line still being written
                    rec.offset += len(raw)
                    rec.read(raw)
        return rec


def reading(run_dir: Path) -> tuple[int, int]:
    """How far a run's record has read its log, and how long the log is, for
    a viewer waiting on the first read. Not locked: it only looks."""
    path = run_dir / "events.jsonl"
    size = path.stat().st_size if path.exists() else 0
    rec = _records.get(str(path.resolve()))
    return (min(rec.offset, size) if rec else 0), size


def snapshot(run_dir: Path, recent: int = 200) -> dict:
    """What a viewer needs on arrival: the latest frame, weather, decisions."""
    frames = last_lines(run_dir / "frames.jsonl", 1)
    weather, food, decisions, tail = None, None, {}, []
    for event in reversed_events(run_dir / "events.jsonl"):
        if len(tail) < recent:
            tail.append(event)
        if food is None and event.get("type") == "food":
            food = event
        if event.get("type") == "decision" and event.get("character") not in decisions:
            decisions[event["character"]] = event
        if weather is None and event.get("type") == "world_event" and event.get("event") == "weather":
            weather = (event.get("data") or {}).get("kind")
        if weather and food and len(tail) >= recent and len(decisions) >= 30:
            break
    return {"frame": frames[0] if frames else None, "weather": weather or "clear",
            "food": food, "decisions": decisions, "recent": list(reversed(tail))}
