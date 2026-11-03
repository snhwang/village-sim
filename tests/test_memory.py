"""What a villager remembers of its own life, and what it must not.

Experience -- a conversation it had, a thing it did -- is held in the same
store as news, because "I saw it myself" is how first-hand news already
arrives. But it must not behave like news: it cannot be told to anyone, and it
cannot gate behaviour through a knows_ tag. Both of those would put one
villager's afternoon inside another villager's head.
"""

import numpy as np
import pytest

from hearthwick.knowledge import EXPERIENCE_KINDS, Fact, KnowledgeStore


def fact(**kw) -> Fact:
    base = dict(id="f1", holder="rosa", text="The well has turned.", kind="sickness",
                place="well", root="sicken:well:100", parent=None, teller=None,
                hop=0, tick=100)
    return Fact(**{**base, **kw})


def vec(*values) -> np.ndarray:
    return np.array(values, dtype=float)


# --- experience is not knowledge about the world ---------------------------

def test_experience_carries_no_tag():
    """A knows_ tag says the world is a certain way. Having chatted does not."""
    assert fact().tag == "knows_sickness_well"
    for kind in EXPERIENCE_KINDS:
        assert fact(kind=kind, text="I talked with Bryn.").tag is None


def test_experience_stays_out_of_the_context():
    store = KnowledgeStore("rosa")
    store.add(fact())
    store.add(fact(id="f2", kind="met", text="I talked with Bryn at the well."))
    assert store.tags() == ["knows_sickness_well"]


def test_experience_is_never_offered_to_anyone():
    """Telling someone your afternoon would give them a memory they did not live."""
    store = KnowledgeStore("rosa")
    store.add(fact(id="f1", kind="met", text="I talked with Bryn.", tick=200))
    store.add(fact(id="f2", kind="did", text="I worked the mill.", tick=201))
    assert store.tellable(2) == []

    store.add(fact(id="f3", tick=150))
    assert [f.id for f in store.tellable(2)] == ["f3"]


# --- recall brings the right thing to mind ---------------------------------

def test_recall_prefers_what_bears_on_the_moment():
    store = KnowledgeStore("rosa")
    store.add(fact(id="well", vector=vec(1.0, 0.0), tick=1))
    store.add(fact(id="road", vector=vec(0.0, 1.0), tick=2, place="east_road",
                   kind="hazard", text="Raiders came to the east road."))

    assert [f.id for f in store.recall(vec(1.0, 0.0), 1)] == ["well"]
    assert [f.id for f in store.recall(vec(0.0, 1.0), 1)] == ["road"]


def test_recall_falls_back_to_recency_without_a_vector():
    """No embedder, or relevance switched off, must still return something."""
    store = KnowledgeStore("rosa")
    store.add(fact(id="old", tick=1))
    store.add(fact(id="new", tick=99))
    assert [f.id for f in store.recall(None, 1)] == ["new"]


def test_news_is_recalled_before_experience():
    """A villager accumulates far more afternoons than news.

    Scored together, the one thing that gates behaviour is buried under an
    endless supply of who it chatted to, so news takes the slots first.
    """
    store = KnowledgeStore("rosa")
    store.add(fact(id="news", vector=vec(0.0, 1.0), tick=1))
    for i in range(10):
        store.add(fact(id=f"met{i}", kind="met", tick=10 + i,
                       text="I talked with Bryn.", vector=vec(1.0, 0.0)))

    # The query points straight at the conversations, and news still comes first.
    recalled = store.recall(vec(1.0, 0.0), 2)
    assert recalled[0].id == "news"
    assert recalled[1].kind == "met"


def test_recall_returns_nothing_from_an_empty_store():
    assert KnowledgeStore("rosa").recall(vec(1.0, 0.0), 2) == []


# --- the same repeated experience is one memory, not many ------------------

def test_repeating_an_experience_should_not_grow_the_store(monkeypatch):
    """Twelve chats with the same neighbour is one memory with a count."""
    store = KnowledgeStore("rosa", duplicate_above=0.85)
    first = fact(id="m1", kind="met", text="I talked with Bryn.", vector=vec(1.0, 0.0))
    store.add(first)

    duplicate, score = store.duplicate_of(vec(1.0, 0.0))
    assert duplicate is first and score == pytest.approx(1.0)
    store.reinforce(duplicate)
    assert first.reinforced == 2
    assert len(store) == 1


# --- relevance must actually be switched on ------------------------------

def test_the_brain_can_really_embed_a_situation(tmp_path):
    """Relevance was inert for a day and nothing said so.

    _recall_vector reached into the retriever for an ``embedder`` attribute
    that does not exist -- it is ``_embedder`` -- so it got None every time and
    recall quietly fell back to recency. The hand-written recall tests above
    still passed, because they pass a vector in themselves.
    """
    from hearthwick.config import SimConfig
    from hearthwick.sim import Simulation

    sim = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path,
                               village="greater"))
    try:
        if sim.embedder is None:
            pytest.skip("needs the embedding service")
        assert sim.brain.embedder is not None, "the brain was given no embedder"
        vector = sim.brain._recall_vector("It is morning. Ada is at the well.")
        assert vector is not None, "relevance recall is inert"
        assert len(vector) > 0

        sim.config.memory_by_relevance = False
        assert sim.brain._recall_vector("anything") is None, \
            "the recency control arm should switch relevance off"
    finally:
        sim.close()
