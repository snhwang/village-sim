"""Every villager speaks from the facts of its own life and village
(hearthwick/grounding.py)."""

import pytest

from hearthwick import grounding
from hearthwick.config import SimConfig
from hearthwick.conversation import Conversation
from hearthwick.sim import Simulation


@pytest.fixture
def sim(tmp_path):
    s = Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", retrieval_threshold=0.0))
    yield s
    s.close()


def test_a_villager_knows_its_own_life(sim):
    mabel = sim.characters["mabel"]
    life = grounding.life(sim, mabel)
    assert "Your partner is Edek." in life
    assert "You have two children: Corin, an apprentice, Hilde28, a child." in life
    assert "Your parents live elsewhere, outside Hearthwick." in life      # a founder
    assert "Your work is at the fields." in life
    corin = sim.characters["corin"]
    assert "Your parents are Edek and Mabel." in grounding.life(sim, corin)
    assert "You are learning your trade from" in grounding.life(sim, corin)


def test_a_villager_knows_its_village(sim):
    places = grounding.places(sim)
    assert "the east road" in places and "13 houses" in places
    people = grounding.people(sim, sim.characters["mabel"])
    assert "Sten (merchant)" in people and "Mabel" not in people   # everyone else, not itself


def test_a_large_village_names_only_those_close(sim, monkeypatch):
    monkeypatch.setattr(grounding, "NAME_EVERYONE_UP_TO", 5)
    people = grounding.people(sim, sim.characters["mabel"])
    assert "Edek" in people and "Corin" in people                  # household
    assert "Sten" not in people                                    # not close to her


def test_every_conversation_prompt_carries_the_foundation(sim):
    mabel, sten = sim.characters["mabel"], sim.characters["sten"]
    conv = Conversation(id="c1", initiator="mabel", partner="sten", topic="the weather",
                        start_tick=0, turns=2, place=None)
    system, *_ = sim.conversations._prompt(mabel, sten, conv)
    assert "Your partner is Edek." in system and "the east road" in system
    assert grounding.CONDUCT in system
    sim.players.begin("mabel")
    system, *_ = sim.players._prompt(mabel, "How are your parents?")
    assert "Your parents live elsewhere" in system and grounding.CONDUCT in system
