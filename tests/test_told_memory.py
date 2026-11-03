"""Villagers remember which news they have shared with whom, and pass on only
what the listener has not had from them (config.told_memory,
SPECIFICATION-warnings.md section 3)."""

import asyncio

import pytest

from hearthwick.__main__ import PROFILES
from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path, told_memory=True):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                told_memory=told_memory))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def adults(sim, n):
    found = [c for c in sim.characters.values()
             if c.alive and not c.visitor and c.stage in ("adult", "elder")]
    return found[:n]


def hears(sim, who, event, place):
    """``who`` witnesses an event, and returns what it now holds of it."""
    return sim.diffuser.witness(event, place, [who.id], {"place": place}, sim.clock.tick)[0]


def tell(sim, fact, teller, receiver):
    return asyncio.run(sim.diffuser.offer(fact, teller, receiver))


def test_off_unless_asked_for():
    assert SimConfig().told_memory is False
    assert PROFILES["paper"]["told_memory"] is False


def test_a_villager_does_not_tell_what_it_has_already_shared(sim):
    a, b = adults(sim, 2)
    well = hears(sim, a, "sicken", "well")
    raid = hears(sim, a, "raid", "east_road")
    assert {f.root for f in sim.diffuser._to_tell(a, b.id)} == {well.root, raid.root}
    tell(sim, raid, a, b)
    later = [f.root for f in sim.diffuser._to_tell(a, b.id)]
    assert raid.root not in later and well.root in later


def test_hearing_it_counts_too(sim):
    """Who told you something knows it, so it is not told back to them."""
    a, b = adults(sim, 2)
    raid = hears(sim, a, "raid", "east_road")
    tell(sim, raid, a, b)
    assert raid.root in sim.diffuser.known_to(b.id, a.id)
    assert raid.root not in {f.root for f in sim.diffuser._to_tell(b, a.id)}


def test_news_of_the_place_a_topic_names_comes_first(sim):
    a, b = adults(sim, 2)
    raid = hears(sim, a, "raid", "east_road")       # a hazard, told first as a rule
    mill = hears(sim, a, "sicken", "mill")
    assert sim.diffuser._to_tell(a, b.id)[0].root == raid.root
    assert sim.diffuser._to_tell(a, b.id, "the grain at the mill")[0].root == mill.root


def test_without_the_switch_the_same_news_comes_up_again(tmp_path):
    s = make_sim(tmp_path, told_memory=False)
    try:
        a, b = adults(s, 2)
        raid = hears(s, a, "raid", "east_road")
        tell(s, raid, a, b)
        assert s.diffuser._to_tell(a, b.id)[0].root == raid.root
        assert s.diffuser.told == {}
    finally:
        s.close()


def test_a_warning_goes_to_someone_not_yet_told(sim):
    a, near, far = adults(sim, 3)
    for other in sim.characters.values():
        if other.id != a.id:
            other.pos = (a.pos[0] + 40, a.pos[1] + 40)       # out of reach
    near.pos = (a.pos[0] + 1, a.pos[1])
    far.pos = (a.pos[0] + 2, a.pos[1])
    assert not near.resting and not far.resting
    raid = hears(sim, a, "raid", "east_road")

    def warned():
        ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                            sim.config.near_radius, news=sim.brain._news_roots,
                            known_to=sim.diffuser.known_to)
        actions = build_registry().process(
            "Warn them. [!warn(target=nearby, topic=the raiders on the east road)]", context=ctx)[1]
        return actions[0].data["target"] if actions else None

    assert warned() == near.id
    tell(sim, raid, a, near)
    assert warned() == far.id
    tell(sim, raid, a, far)
    assert warned() is None


def test_what_was_shared_survives_a_checkpoint(sim, tmp_path):
    a, b = adults(sim, 2)
    raid = hears(sim, a, "raid", "east_road")
    tell(sim, raid, a, b)
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        assert resumed.diffuser.known_to(a.id, b.id) == {raid.root}
        assert resumed.diffuser.known_to(b.id, a.id) == {raid.root}
    finally:
        resumed.close()


def test_a_warner_cannot_see_into_the_listeners_head(sim):
    """Someone who saw it for themselves still gets warned, since the warner
    has no way to know they did. Reading their store was the old rule."""
    a, near = adults(sim, 2)
    for other in sim.characters.values():
        if other.id != a.id:
            other.pos = (a.pos[0] + 40, a.pos[1] + 40)
    near.pos = (a.pos[0] + 1, a.pos[1])
    raid = hears(sim, a, "raid", "east_road")
    hears(sim, near, "raid", "east_road")

    def warned(known_to):
        ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                            sim.config.near_radius, news=sim.brain._news_roots,
                            known_to=known_to)
        actions = build_registry().process(
            "Warn them. [!warn(target=nearby, topic=the raiders on the east road)]", context=ctx)[1]
        return actions[0].data["target"] if actions else None

    assert raid.root in sim.brain._news_roots(near.id)
    assert warned(None) is None                          # the old rule read near's store
    assert warned(sim.diffuser.known_to) == near.id      # the warner can only remember
