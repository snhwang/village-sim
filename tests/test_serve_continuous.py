"""A village left running: an idle pace, saved as it goes and when stopped,
and resumed in its own log (hearthwick/server.py, hearthwick/checkpoint.py)."""

import json
import time

from fastapi.testclient import TestClient

from hearthwick import checkpoint
from hearthwick.config import SimConfig
from hearthwick.server import create_app
from hearthwick.sim import Simulation


def config(tmp_path):
    return SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                     embedder="bm25", retrieval_threshold=0.0)


async def _no_speech(_config):
    return None


def frame_ticks(run_dir) -> list[int]:
    with open(run_dir / "frames.jsonl", encoding="utf-8") as f:
        return [json.loads(line)["t"] for line in f if line.strip()]


def only_run(tmp_path):
    (run,) = [d for d in tmp_path.iterdir() if d.is_dir()]
    return run


def test_an_unwatched_village_keeps_its_idle_pace(tmp_path):
    app = create_app(config(tmp_path), live=True, speed=2.0, make_speech=_no_speech,
                     idle_speed=4.0)
    with TestClient(app):
        time.sleep(1.5)
    assert 1 <= len(frame_ticks(only_run(tmp_path))) <= 9


def test_a_village_saved_on_stop_resumes_in_its_own_log(tmp_path):
    app = create_app(config(tmp_path), live=True, speed=2.0, make_speech=_no_speech,
                     checkpoint_every=1.0)
    with TestClient(app):
        time.sleep(1.5)
    run = only_run(tmp_path)
    saved = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
    stopped_at = saved["tick"]
    assert stopped_at == len(frame_ticks(run)) > 0
    time.sleep(1.1)                  # a run's directory is named to the second

    app = create_app(config(tmp_path), live=True, speed=2.0, make_speech=_no_speech,
                     checkpoint_every=1.0, resume=run.name)
    with TestClient(app):
        time.sleep(1.5)
    assert only_run(tmp_path) == run                  # one village, one log
    ticks = frame_ticks(run)
    assert ticks == list(range(len(ticks))) and len(ticks) > stopped_at
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    assert meta["plan"]["serve"] and len(meta["resumed"]) == 1


def test_a_resume_after_a_hard_stop_cuts_the_log_back(tmp_path):
    import asyncio

    async def steps(sim, n):
        for _ in range(n):
            await sim.step()

    s = Simulation(config(tmp_path))
    asyncio.run(steps(s, 5))
    path = asyncio.run(s.save())
    asyncio.run(steps(s, 7))           # logged, then lost to a reboot
    s.log.flush()
    s.log._events.close()
    s.log._frames.close()
    run = s.log.dir
    assert len(frame_ticks(run)) == 12
    time.sleep(1.1)

    t = Simulation(config(tmp_path))
    try:
        t.log.adopt(run)
        assert t.resume_from(path) == 5
        assert frame_ticks(run) == list(range(5))
        asyncio.run(steps(t, 3))
        t.log.flush()
        assert frame_ticks(run) == list(range(8))
        with open(run / "events.jsonl", encoding="utf-8") as f:
            kinds = [json.loads(line)["type"] for line in f]
        assert kinds.count("checkpoint") == 1 and kinds.count("resumed") == 1
    finally:
        t.close()


def test_a_checkpoint_restored_into_another_run_leaves_that_log_alone(tmp_path):
    import asyncio

    s = Simulation(config(tmp_path))
    asyncio.run(s.step())
    path = checkpoint.save(s)
    s.close()
    time.sleep(1.1)
    t = Simulation(config(tmp_path))
    try:
        before = (t.log.dir / "events.jsonl").stat().st_size
        t.resume_from(path)
        t.log.flush()
        assert (t.log.dir / "events.jsonl").stat().st_size >= before
    finally:
        t.close()
