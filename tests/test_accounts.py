"""What the villagers call each visitor (hearthwick/accounts.py), and a chat
with a visitor who has a name (hearthwick/player.py)."""

import asyncio
import json

from fastapi.testclient import TestClient

from hearthwick.accounts import EMAIL_HEADER, TOKEN_HEADER, Accounts
from hearthwick.config import SimConfig
from hearthwick.server import create_app
from hearthwick.sim import Simulation

EMAIL = "someone@example.org"
TOKEN = "0123456789abcdef0123456789abcdef"


def test_a_visitor_is_known_by_a_salted_hash_of_its_account(tmp_path):
    accounts = Accounts(tmp_path / "accounts.json")
    key = accounts.key({EMAIL_HEADER: "Someone@Example.org "})
    assert key.startswith("cf:") and EMAIL not in key
    assert key == accounts.key({EMAIL_HEADER: EMAIL})                 # case and spaces aside
    assert accounts.key({TOKEN_HEADER: TOKEN}).startswith("browser:")
    assert accounts.key({EMAIL_HEADER: EMAIL, TOKEN_HEADER: TOKEN}) == key   # the login wins
    assert accounts.key({}) is None and accounts.key({TOKEN_HEADER: "short"}) is None


def test_a_name_is_kept_and_the_email_never_is(tmp_path):
    path = tmp_path / "accounts.json"
    accounts = Accounts(path)
    key = accounts.key({EMAIL_HEADER: EMAIL})
    accounts.set(key, "Scott")
    again = Accounts(path)
    assert again.name_of(again.key({EMAIL_HEADER: EMAIL})) == "Scott"
    assert EMAIL not in path.read_text(encoding="utf-8")


def test_what_will_not_do_for_a_name(tmp_path):
    accounts = Accounts(tmp_path / "accounts.json")
    taken = {"Alda287", "Ivar283"}
    assert accounts.refusal("Scott", taken) is None
    assert accounts.refusal("Mary-Jane O'Neil", taken) is None
    assert accounts.refusal("", taken)
    assert accounts.refusal("x" * 25, taken)
    assert accounts.refusal("Scott2", taken)                           # no digits
    assert accounts.refusal("alda287", taken)                          # a villager's name


def test_the_page_asks_for_a_name_once_and_keeps_it(tmp_path):
    app = create_app(SimConfig(runs_dir=tmp_path), live=False, speed=2.0, make_speech=lambda c: None)
    with TestClient(app) as client:
        me = {EMAIL_HEADER: EMAIL}
        assert client.get("/api/me", headers=me).json() == {"name": None, "known": True}
        assert client.post("/api/me", json={"name": "Sc0tt"}, headers=me).status_code == 400
        assert client.post("/api/me", json={"name": "  Scott  "}, headers=me).json() == {"name": "Scott"}
        assert client.get("/api/me", headers=me).json()["name"] == "Scott"
        assert client.get("/api/me").json() == {"name": None, "known": False}
        assert client.post("/api/me", json={"name": "Scott"}).status_code == 400


class Ear:
    available = True

    def __init__(self):
        self.heard = []
        self.calls = self.failures = 0

    async def say(self, system, user, seed, history=None):
        self.calls += 1
        self.heard.append({"system": system, "user": user, "history": history})
        return "Good morning."

    def info(self):
        return {"model": "ear"}


def test_a_named_visitor_is_talked_to_and_remembered_by_name(tmp_path):
    sim = Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0), Ear())
    try:
        c = next(c for c in sorted(sim.characters.values(), key=lambda c: c.id)
                 if c.stage == "adult" and not c.resting)
        sim.players.begin(c.id, "Scott")
        asyncio.run(sim.players.say("hi"))
        asyncio.run(sim.players.say("How are you?"))
        first, second = sim.speech.heard[-2:]
        assert "Scott, who is from outside the village, has come up to talk with you." in first["system"]
        assert "talked with Scott before" not in first["system"]
        assert second["user"] == "Scott: How are you?"
        assert second["history"] == [("user", "Scott: hi"), ("assistant", "Good morning.")]
        asyncio.run(sim.players.end())
        assert sim.players.stranger.name == "a stranger"               # the next visitor is nobody yet
        met = [f.text for f in sim.diffuser.store_for(c.id).facts if f.kind == "met"]
        assert any(t.startswith("I talked with Scott, who is from outside the village, at ") for t in met)
        # Back again, the villager knows it has met Scott.
        sim.players.begin(c.id, "Scott")
        asyncio.run(sim.players.say("Hello again."))
        assert "You have talked with Scott before." in sim.speech.heard[-1]["system"]
        asyncio.run(sim.players.end())
        sim.log.flush()
        with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
            said = [e for e in map(json.loads, f) if e["type"] == "utterance" and e["speaker"] == "stranger"]
        assert said and all(e["visitor"] == "Scott" for e in said)
    finally:
        sim.close()
