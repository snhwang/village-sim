"""A conversation reaches the model as turns, one message a line
(config.chat_turns). As a transcript in one message, a small model lost track
of who had said what and echoed a stranger's words back as its own
(2026-10-02)."""

import asyncio
import json

from hearthwick.__main__ import PROFILES, _saved
from hearthwick.config import SimConfig
from hearthwick.conversation import Conversation
from hearthwick.sim import Simulation


class Ear:
    """A stand-in for the model that keeps what it was asked."""

    available = True

    def __init__(self):
        self.heard = []
        self.calls = self.failures = 0

    async def say(self, system, user, seed, history=None):
        self.calls += 1
        self.heard.append({"system": system, "user": user, "history": history})
        return "Who sent you?"

    def info(self):
        return {"model": "ear"}


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw), Ear())


def awake_adults(sim):
    return [c for c in sorted(sim.characters.values(), key=lambda c: c.id)
            if c.stage == "adult" and not c.resting]


def test_a_stranger_is_answered_turn_by_turn(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = awake_adults(sim)[0]
        sim.players.begin(c.id)
        asyncio.run(sim.players.say("Hi"))
        asyncio.run(sim.players.say("Just walking."))
        first, second = sim.speech.heard[-2:]
        assert first["user"] == "Hi" and first["history"] is None
        assert second["user"] == "Just walking."
        assert second["history"] == [("user", "Hi"), ("assistant", "Who sent you?")]
        assert "You are at" in second["system"] and "Conversation so far" not in second["user"]
    finally:
        sim.close()


def test_without_the_switch_a_stranger_gets_the_transcript_as_before(tmp_path):
    sim = make_sim(tmp_path, chat_turns=False)
    try:
        c = awake_adults(sim)[0]
        sim.players.begin(c.id)
        asyncio.run(sim.players.say("Hi"))
        asyncio.run(sim.players.say("Just walking."))
        last = sim.speech.heard[-1]
        assert last["history"] is None
        assert f"Conversation so far:\nStranger: Hi\n{c.name}: Who sent you?\nStranger: Just walking." \
            in last["user"]
    finally:
        sim.close()


def test_villagers_talk_turn_by_turn(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = awake_adults(sim)[:2]
        conv = Conversation(id="c1", initiator=a.id, partner=b.id, topic="the weather",
                            start_tick=0, turns=4, place=None)
        system, user, _, history = sim.conversations._prompt(a, b, conv)
        assert history == [] and b.name in user and "Start the conversation" in user
        assert "Topic: the weather" in system
        conv.lines = [{"speaker": a.id, "text": "Rain again."},
                      {"speaker": b.id, "text": "The ford will flood."}]
        system, user, _, history = sim.conversations._prompt(a, b, conv)
        assert user == "The ford will flood." and history == [("assistant", "Rain again.")]
        # The listener answers the same lines from its side.
        conv.lines = conv.lines[:1]
        _, user, _, history = sim.conversations._prompt(b, a, conv)
        assert user == "Rain again." and history == []
    finally:
        sim.close()


def test_without_the_switch_villagers_get_the_transcript_as_before(tmp_path):
    sim = make_sim(tmp_path, chat_turns=False)
    try:
        a, b = awake_adults(sim)[:2]
        conv = Conversation(id="c1", initiator=a.id, partner=b.id, topic="the weather",
                            start_tick=0, turns=4, place=None)
        conv.lines = [{"speaker": b.id, "text": "The ford will flood."}]
        _, user, _, history = sim.conversations._prompt(a, b, conv)
        assert history == [] and user.startswith(f"You are talking with {b.name} at ")
        assert user.endswith(f"Conversation so far:\n{b.name}: The ford will flood.\n\nYour next line:")
    finally:
        sim.close()


def test_old_runs_and_the_paper_keep_the_transcript(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({"config": {"seed": 3, "village": "greater"}}))
    config = SimConfig(runs_dir=tmp_path)
    assert _saved(config, "old-run")[0].chat_turns is False
    assert _saved(config, "old-run", ["chat_turns"])[0].chat_turns is True
    assert PROFILES["paper"]["chat_turns"] is False
