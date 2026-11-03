"""Villagers' memories as BEAR items (config.bear_memory, hearthwick/memory.py).

The first promise is that nothing changes: the knowledge tags BEAR gives are
the ones Hearthwick's own store gives, with fading on and off, at the edge of
a fade and after something is witnessed again. Skipped on a BEAR without
items and the importance floor (BEAR v0.3.0)."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from hearthwick.__main__ import PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.knowledge import FADE_YEARS  # noqa: E402
from hearthwick.memory import BearKnowledgeStore  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, bear_memory=True):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                bear_memory=bear_memory))


@pytest.fixture
def pair(tmp_path):
    """The same village twice, its memories in BEAR and in Hearthwick's store."""
    bear, own = make_sim(tmp_path / "bear"), make_sim(tmp_path / "own", bear_memory=False)
    yield bear, own
    bear.close()
    own.close()


def fade_for(sim):
    year = sim.clock.ticks_per_day * sim.clock.days_per_year
    return {kind: int(years * year) for kind, years in FADE_YEARS.items()}


def witness(sim, who, event, place, tick):
    return sim.diffuser.witness(event, place, [who], {"place": place}, tick)


def test_off_unless_asked_for():
    assert SimConfig().bear_memory is False
    assert PROFILES["paper"]["bear_memory"] is False


def test_the_store_is_bear_only_with_the_switch(pair):
    bear, own = pair
    who = next(iter(bear.characters))
    assert isinstance(bear.diffuser.store_for(who), BearKnowledgeStore)
    assert not isinstance(own.diffuser.store_for(who), BearKnowledgeStore)


def test_the_same_knowledge_tags_with_and_without_fading(pair):
    bear, own = pair
    who = next(iter(bear.characters))
    fade = fade_for(bear)
    # A hazard, a sickness and a rumour-free piece of news, learned at
    # different times, then the well's sickness witnessed again later.
    for sim in pair:
        witness(sim, who, "raid", "east_road", 0)
        witness(sim, who, "sicken", "well", 100)
        witness(sim, who, "festival", "inn", 200)
    year = bear.clock.ticks_per_day * bear.clock.days_per_year
    moments = sorted({0, 100, 200, fade["sickness"] + 100, fade["sickness"] + 101,
                      fade["hazard"], fade["hazard"] + 1, 3 * year})
    for now in moments:
        assert bear.diffuser.store_for(who).tags(now=now, fade=fade) == \
            own.diffuser.store_for(who).tags(now=now, fade=fade), now
    assert bear.diffuser.store_for(who).tags() == own.diffuser.store_for(who).tags()


def test_a_fact_is_dropped_at_exactly_the_tick_the_old_rule_dropped_it(pair):
    bear, own = pair
    who = next(iter(bear.characters))
    fade = fade_for(bear)
    for sim in pair:
        witness(sim, who, "sicken", "well", 0)
    edge = fade["sickness"]
    for now in (edge, edge + 1):
        assert bear.diffuser.store_for(who).tags(now=now, fade=fade) == \
            own.diffuser.store_for(who).tags(now=now, fade=fade)
    assert "knows_sickness_well" in bear.diffuser.store_for(who).tags(now=edge, fade=fade)
    assert "knows_sickness_well" not in bear.diffuser.store_for(who).tags(now=edge + 1, fade=fade)


def test_witnessing_again_restarts_the_clock(pair):
    bear, own = pair
    who = next(iter(bear.characters))
    fade = fade_for(bear)
    edge = fade["sickness"]
    for sim in pair:
        witness(sim, who, "sicken", "well", 0)
        witness(sim, who, "sicken", "well", edge // 2)     # the same news, lived again
    for now in (edge + 1, edge // 2 + edge, edge // 2 + edge + 1):
        assert bear.diffuser.store_for(who).tags(now=now, fade=fade) == \
            own.diffuser.store_for(who).tags(now=now, fade=fade), now
    assert "knows_sickness_well" in bear.diffuser.store_for(who).tags(now=edge + 1, fade=fade)


def test_a_refreshed_fact_counts_again_in_both(pair):
    """Without the embedding service a second witnessing is a second fact, so
    the refresh the duplicate test would make is made directly."""
    bear, own = pair
    who = next(iter(bear.characters))
    fade = fade_for(bear)
    edge = fade["sickness"]
    facts = [witness(sim, who, "sicken", "well", 0)[0] for sim in pair]
    for sim, fact in zip(pair, facts):
        sim.diffuser.store_for(who).reinforce(fact, refreshed=edge)
    for now in (edge + 1, 2 * edge, 2 * edge + 1):
        assert bear.diffuser.store_for(who).tags(now=now, fade=fade) == \
            own.diffuser.store_for(who).tags(now=now, fade=fade), now
    assert "knows_sickness_well" in bear.diffuser.store_for(who).tags(now=edge + 1, fade=fade)
    assert "knows_sickness_well" not in bear.diffuser.store_for(who).tags(now=2 * edge + 1,
                                                                            fade=fade)


def test_each_villager_asks_only_its_own_memory(pair):
    bear, _ = pair
    a, b = list(bear.characters)[:2]
    witness(bear, a, "raid", "east_road", 0)
    assert bear.diffuser.store_for(a).tags()
    assert bear.diffuser.store_for(b).tags() == []


def test_memories_survive_a_checkpoint(tmp_path):
    sim = make_sim(tmp_path)
    try:
        who = next(iter(sim.characters))
        witness(sim, who, "raid", "east_road", 0)
        witness(sim, who, "sicken", "well", 50)
        fade = fade_for(sim)
        before = [sim.diffuser.store_for(who).tags(now=n, fade=fade) for n in (60, fade["sickness"] + 51)]
        path = asyncio.run(sim.save())
        resumed = make_sim(tmp_path / "again")
        try:
            resumed.resume_from(path)
            after = [resumed.diffuser.store_for(who).tags(now=n, fade=fade)
                     for n in (60, fade["sickness"] + 51)]
            assert after == before
            held = sum(len(s.facts) for s in resumed.diffuser.stores.values())
            assert len(resumed.diffuser.memory.retriever.corpus) == held
        finally:
            resumed.close()
    finally:
        sim.close()
