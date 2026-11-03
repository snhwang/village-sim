"""A human talks with a villager as a stranger (hearthwick/player.py)."""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from hearthwick.config import SimConfig
from hearthwick.player import PLAYER_ID
from hearthwick.server import create_app
from hearthwick.sim import Simulation


def config(tmp_path):
    return SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                     embedder="bm25", retrieval_threshold=0.0)


@pytest.fixture
def sim(tmp_path):
    s = Simulation(config(tmp_path))
    yield s
    s.close()


def awake_adult(sim):
    return next(c for c in sorted(sim.characters.values(), key=lambda c: c.id)
                if c.stage == "adult" and not c.resting)


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def test_a_stranger_can_talk_to_an_awake_villager_and_holds_it(sim):
    c = awake_adult(sim)
    conv = sim.players.begin(c.id)
    assert c.conversation_id == conv.id and sim.players.talking
    other = next(o for o in sim.characters.values() if o.id != c.id and not o.resting)
    assert "already talking" in sim.players.refusal(other.id)


def test_who_cannot_be_talked_to(sim):
    assert sim.players.refusal("nobody") is not None
    from hearthwick.character import Activity
    c = awake_adult(sim)
    c.activity = Activity(kind="rest", data={"until": "morning"}, instruction_id=None)
    assert "asleep" in sim.players.refusal(c.id)


def test_what_the_stranger_said_is_the_villagers_to_keep_and_pass_on(sim):
    """Without a speech model the lens keeps what it hears as it heard it, so
    the chain from the stranger through two villagers can be checked."""
    c = awake_adult(sim)
    sim.players.begin(c.id)
    reply = asyncio.run(sim.players.say("Wolves were seen at the forest edge last night."))
    assert reply is None                                   # no speech model here
    result = asyncio.run(sim.players.end())
    assert result["kept"] and c.conversation_id is None and not sim.players.talking
    held = [f for f in sim.diffuser.store_for(c.id).facts if f.root.startswith("player:")]
    assert len(held) == 1 and held[0].teller == PLAYER_ID and held[0].hop == 1
    assert any(f.kind == "met" and "stranger" in f.text
               for f in sim.diffuser.store_for(c.id).facts)
    lines = events(sim, "utterance")
    assert lines and lines[-1]["speaker"] == PLAYER_ID
    # and a neighbour can hear it from the villager
    neighbour = next(o for o in sim.characters.values()
                     if o.id != c.id and o.stage == "adult")
    asyncio.run(sim.diffuser.offer(held[0], c, neighbour))
    passed = [f for f in sim.diffuser.store_for(neighbour.id).facts
              if f.root == held[0].root]
    assert passed and passed[0].hop == 2 and passed[0].teller == c.id


def test_the_world_stands_still_while_a_stranger_talks(tmp_path):
    app = create_app(config(tmp_path), live=True, speed=2.0, make_speech=_no_speech)
    with TestClient(app) as client, client.websocket_connect("/ws") as viewer:
        viewer.receive_text()                       # hello: someone is watching now
        sim = app.state.village.sim
        villager = None
        for _ in range(40):
            awake = [c.id for c in sim.characters.values()
                     if c.stage == "adult" and not c.resting and c.conversation_id is None]
            r = client.post("/api/talk/start", json={"villager": awake[0]}) if awake else None
            if r is not None and r.status_code == 200:
                villager = r.json()
                break
            time.sleep(0.1)
        assert villager is not None
        assert client.get("/api/live").json()["talking_with"] == villager["villager"]
        ticks = _ticks(tmp_path)
        time.sleep(1.5)
        assert _ticks(tmp_path) == ticks, "the world moved while a stranger talked"
        r = client.post("/api/talk/say", json={"token": villager["token"], "text": "Good day."})
        assert r.status_code == 200
        assert client.post("/api/talk/say", json={"token": "wrong", "text": "x"}).status_code == 409
        assert client.post("/api/talk/end", json={"token": villager["token"]}).status_code == 200
        time.sleep(1.5)
        assert _ticks(tmp_path) > ticks, "the world did not go on after the stranger left"


async def _no_speech(_config):
    return None


def _ticks(runs_dir) -> int:
    (run,) = [d for d in runs_dir.iterdir() if d.is_dir()]
    with open(run / "frames.jsonl", encoding="utf-8") as f:
        return sum(1 for _ in f)
