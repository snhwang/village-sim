"""A traveling storyteller comes, tells, listens, and goes (hearthwick/visitors.py)."""

import asyncio
import json

import pytest
from bear import MarkerAction

from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, WorldMarkerContext, build_registry, build_world_registry
from hearthwick.sim import Simulation
from hearthwick.visitors import NEWS_CARRIED, VISITOR_GAP_DAYS


def make_sim(tmp_path):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def arrive(sim):
    sim._apply_world_action(MarkerAction("visitor", {"kind": "storyteller", "place": "east_road"}))
    return sim.visitors.present()[-1]


def events(sim):
    sim.log.flush()
    return [json.loads(line) for line in open(sim.log.dir / "events.jsonl", encoding="utf-8")]


def resolve(sim, who, content):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters,
                        sim.rng_for("t", "t"), sim.config.near_radius)
    return build_registry().process(content, context=ctx)[1]


def test_a_storyteller_arrives_with_news_from_beyond(sim):
    s = arrive(sim)
    assert s.visitor and s.alive and s.role == "storyteller" and s.home == "inn"
    assert sim.world.places["east_road"].contains(*s.pos)
    tales = [f for f in sim.diffuser.store_for(s.id).facts if f.root.startswith("tale:")]
    assert len(tales) == NEWS_CARRIED and len({f.root for f in tales}) == NEWS_CARRIED
    assert all(f.hop == 0 and f.teller is None for f in tales)
    assert sim.corpus.get(f"persona-{s.id}") is not None
    assert any(e["type"] == "roster" and e["characters"][0]["id"] == s.id for e in events(sim))
    # its temperament is what its own two copies of each gene express
    assert set(s.genotype) == set(s.temperament)


def test_the_world_sends_one_at_a_time(sim):
    handler = build_world_registry()
    ctx = WorldMarkerContext(sim.world, sim.clock, sim.world_agent.state)
    assert handler.process("[!visitor(storyteller)]", context=ctx)[1]
    s = arrive(sim)
    assert handler.process("[!visitor(storyteller)]", context=ctx)[1] == []
    sim.visitors.depart(s, sim.clock.tick)
    assert handler.process("[!visitor(storyteller)]", context=ctx)[1] == []
    sim.clock.tick += VISITOR_GAP_DAYS * sim.clock.ticks_per_day
    assert handler.process("[!visitor(storyteller)]", context=ctx)[1]


def test_villagers_see_a_stranger_and_can_seek_it_out(sim):
    s = arrive(sim)
    villager = next(c for c in sim.characters.values() if not c.visitor and c.stage == "adult")
    villager.pos = s.pos
    assert "near_stranger" in sim.brain.context_tags(villager, sim.characters)
    assert "near_stranger" not in sim.brain.context_tags(s, sim.characters)
    talk = resolve(sim, villager, "[!talk(target=stranger)]")
    assert talk and talk[0].data["target"] == s.id


def test_a_storyteller_leaves_when_its_stay_is_over(sim):
    s = arrive(sim)
    assert "leaving" not in sim.brain.context_tags(s, sim.characters)
    sim.clock.tick = s.leaves_at
    assert "leaving" in sim.brain.context_tags(s, sim.characters)
    resident = next(c for c in sim.characters.values() if not c.visitor)
    assert resolve(sim, resident, "[!depart]") == []
    s.activity = None
    s.queue.extend(sim._activity(a, "visitor-leave") for a in resolve(sim, s, "[!depart]"))
    sim._advance(s)
    assert not s.alive and s.id not in sim.world_agent.state.visitors_here
    assert any(e["type"] == "visitor_departed" and e["character"] == s.id for e in events(sim))


def test_what_a_storyteller_heard_goes_with_it(sim):
    s = arrive(sim)
    villager = next(c for c in sim.characters.values() if not c.visitor and c.stage == "adult")
    news = sim.diffuser.witness("sicken", "well", [villager.id], {"place": "well"}, sim.clock.tick)
    asyncio.run(sim.diffuser.offer(news[0], villager, s))
    sim.visitors.depart(s, sim.clock.tick)
    departed = next(e for e in events(sim) if e["type"] == "visitor_departed")
    assert news[0].root in departed["takes"]


def test_nobody_stays_for_ever(sim):
    s = arrive(sim)
    sim.clock.tick = s.leaves_at + sim.clock.ticks_per_day
    sim._physics()
    assert not s.alive


def test_a_storyteller_is_not_in_frames_once_gone(sim):
    s = arrive(sim)
    frame = asyncio.run(sim.step())
    assert s.id in [row[0] for row in frame["c"]]
    sim.visitors.depart(s, sim.clock.tick)
    frame = asyncio.run(sim.step())
    assert s.id not in [row[0] for row in frame["c"]]


def test_a_storyteller_survives_a_checkpoint(sim, tmp_path):
    s = arrive(sim)
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        back = resumed.characters[s.id]
        assert back.visitor and back.alive and back.leaves_at == s.leaves_at
        assert back.temperament == s.temperament
        assert resumed.world_agent.state.visitors_here == [s.id]
        assert resumed.visitors.arrived == 1
        assert {f.root for f in resumed.diffuser.store_for(s.id).facts} == \
            {f.root for f in sim.diffuser.store_for(s.id).facts}
    finally:
        resumed.close()


def resolve_with_news(sim, who, content):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters,
                        sim.rng_for("t", "t"), sim.config.near_radius,
                        news=sim.brain._news_roots)
    return build_registry().process(content, context=ctx)[1]


def test_nobody_goes_back_to_a_stranger_with_nothing_new(sim):
    s = arrive(sim)
    villager = next(c for c in sim.characters.values() if not c.visitor and c.stage == "adult")
    villager.pos = s.pos
    assert resolve_with_news(sim, villager, "[!talk(target=stranger)]")
    for fact in list(sim.diffuser.store_for(s.id).facts):
        asyncio.run(sim.diffuser.offer(fact, s, villager))
    assert resolve_with_news(sim, villager, "[!talk(target=stranger)]") == []


def test_a_storyteller_looks_for_someone_who_has_not_heard(sim):
    s = arrive(sim)
    near = sorted((c for c in sim.characters.values() if not c.visitor and c.stage == "adult"),
                  key=lambda c: c.id)[:2]
    for c in near:
        c.pos = s.pos
    for fact in list(sim.diffuser.store_for(s.id).facts):
        asyncio.run(sim.diffuser.offer(fact, s, near[0]))
    talk = resolve_with_news(sim, s, "[!talk(target=listener)]")
    assert talk and talk[0].data["target"] == near[1].id


def test_a_storyteller_tells_what_it_brought_first(sim):
    s = arrive(sim)
    villager = next(c for c in sim.characters.values() if not c.visitor and c.stage == "adult")
    # The storyteller has heard of the sick well, which every villager brings up first.
    well = sim.diffuser.witness("sicken", "well", [villager.id], {"place": "well"}, sim.clock.tick)
    asyncio.run(sim.diffuser.offer(well[0], villager, s))
    told = sim.diffuser._to_tell(s, villager.id)
    assert told and all(f.root.startswith("tale:") for f in told)
    # and once a listener holds every tale, the usual order comes back, the
    # village's own hazards first
    for fact in [f for f in sim.diffuser.store_for(s.id).facts if f.root.startswith("tale:")]:
        asyncio.run(sim.diffuser.offer(fact, s, villager))
    assert sim.diffuser._to_tell(s, villager.id)[0].root == well[0].root

