"""Watching a run through its log files, live or replayed."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hearthwick.config import SimConfig
from hearthwick.follow import Tail, is_live, last_lines
from hearthwick.server import create_app


def frame(t: int) -> dict:
    return {"t": t, "clock": {"tick": t, "day": 0, "year": 0, "hour": 6 + t / 6, "part": "morning"},
            "c": [["ada", t % 40, 3, "go", "adult", 12.0]]}


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "runs" / "20260101-000000-seed1"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"run_id": d.name, "config": {"village": "greater"}}))
    with open(d / "events.jsonl", "w") as f:
        f.write(json.dumps({"t": 0, "type": "roster", "characters": [
            {"id": "ada", "name": "Ada", "stage": "adult", "role": "healer", "temperament": {}}]}) + "\n")
    with open(d / "frames.jsonl", "w") as f:
        for t in range(3):
            f.write(json.dumps(frame(t)) + "\n")
    return d


def test_a_line_still_being_written_is_not_read(tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text('{"t": 1}\n{"t": 2')
    tail = Tail(path)
    assert tail.read() == [{"t": 1}]
    with open(path, "a") as f:
        f.write('}\n')
    assert tail.read() == [{"t": 2}]
    assert last_lines(path, 1) == [{"t": 2}]


def test_a_run_that_has_closed_is_not_live(run_dir):
    assert is_live(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text())
    meta["finished"] = (datetime.now() + timedelta(seconds=1)).isoformat(timespec="seconds")
    (run_dir / "meta.json").write_text(json.dumps(meta))
    assert not is_live(run_dir)


def test_a_viewer_follows_frames_as_they_are_written(run_dir):
    app = create_app(SimConfig(runs_dir=run_dir.parent), live=False, speed=2.0,
                     make_speech=lambda c: None)
    stop = threading.Event()

    def write():
        t = 3
        while not stop.is_set() and t < 40:
            with open(run_dir / "frames.jsonl", "a") as f:
                f.write(json.dumps(frame(t)) + "\n")
            t += 1
            time.sleep(0.05)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/follow?run=latest&start=live") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["live"]
            assert hello["frame"]["t"] == 2
            writer = threading.Thread(target=write)
            writer.start()
            try:
                seen = [ws.receive_json() for _ in range(5)]
            finally:
                stop.set()
                writer.join()
    ticks = [m["frame"]["t"] for m in seen if m["type"] == "tick"]
    assert ticks and ticks == sorted(ticks) and ticks[0] >= 3


def test_a_replay_starts_at_the_first_frame_and_can_skip_ahead(run_dir):
    app = create_app(SimConfig(runs_dir=run_dir.parent), live=False, speed=2.0,
                     make_speech=lambda c: None)
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/follow?run={run_dir.name}&start=begin&rate=200") as ws:
            assert ws.receive_json()["type"] == "hello"
            assert [ws.receive_json()["frame"]["t"] for _ in range(3)] == [0, 1, 2]
        with client.websocket_connect(f"/ws/follow?run={run_dir.name}&start=begin&rate=200&from=2") as ws:
            ws.receive_json()
            assert ws.receive_json()["frame"]["t"] >= 1


def test_a_waiting_viewer_can_see_how_far_the_log_has_been_read(run_dir):
    """The first read after a restart takes minutes, and the viewer shows how
    far along it is rather than a bare spinner (client/village3d.js)."""
    from hearthwick.follow import _record, _records, reading

    _records.clear()
    size = (run_dir / "events.jsonl").stat().st_size
    assert reading(run_dir) == (0, size)
    app = create_app(SimConfig(runs_dir=run_dir.parent), live=False, speed=2.0,
                     make_speech=lambda c: None)
    with TestClient(app) as client:
        assert client.get("/api/loading").json() == {"run_id": run_dir.name, "read": 0, "size": size}
        _record(run_dir)
        assert client.get(f"/api/loading?run={run_dir.name}").json()["read"] == size

