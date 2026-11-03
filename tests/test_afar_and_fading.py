"""News from afar (config.afar_news) and fading hazards (config.news_fades).
In the open-ended run, 1,883 of 2,020 hazard facts came from storytellers'
tales pinned to the east road, and warnings grew from 4% of decisions in year
1 to 28% in year 16 from rumours that never faded."""

import json

from hearthwick.config import SimConfig
from hearthwick.knowledge import Fact, KnowledgeStore
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw), None)


def fact(**kw):
    base = dict(id="f1", holder="a", text="Raiders on the east road.", kind="hazard",
                place="east_road", root="raid:east_road:0", parent=None, teller=None, hop=0, tick=0)
    base.update(kw)
    return Fact(**base)


def test_a_traveller_s_news_is_held_as_from_afar(tmp_path):
    for on in (False, True):
        sim = make_sim(tmp_path / str(on), afar_news=on)
        try:
            witnesses = [c.id for c in sorted(sim.characters.values(), key=lambda c: c.id)][:2]
            stored = sim.diffuser.witness("traveler", "east_road", witnesses, {"topic": "news"}, 5)
            assert stored and all(f.from_afar is on for f in stored)
            if on:
                assert all(f.tag.endswith("_afar") for f in stored)
            raid = sim.diffuser.witness("raid", "east_road", witnesses, {}, 6)
            assert raid and not any(f.from_afar for f in raid)
        finally:
            sim.close()


def test_an_old_hazard_stops_driving_behaviour_but_is_still_held():
    store = KnowledgeStore("a")
    store.add(fact())
    year = 144 * 8
    fade = {"hazard": 2 * year}
    assert store.tags(now=year, fade=fade) == ["knows_hazard_east_road"]
    assert store.tags(now=3 * year, fade=fade) == []
    assert store.tags() == ["knows_hazard_east_road"] and len(store) == 1


def test_living_it_again_restarts_the_clock_but_hearing_it_again_does_not():
    store = KnowledgeStore("a")
    f = fact()
    store.add(f)
    year = 144 * 8
    store.reinforce(f)
    assert f.refreshed is None and f.reinforced == 2
    store.reinforce(f, refreshed=2 * year)
    assert store.tags(now=3 * year, fade={"hazard": 2 * year}) == ["knows_hazard_east_road"]


def test_the_brain_drops_a_faded_hazard_only_with_the_switch(tmp_path):
    for on in (False, True):
        sim = make_sim(tmp_path / str(on), news_fades=on)
        try:
            c = next(c for c in sorted(sim.characters.values(), key=lambda c: c.id)
                     if c.stage == "adult")
            sim.diffuser.store_for(c.id).add(fact(holder=c.id))
            sim.clock.tick = 3 * 144 * 8
            tags = sim.brain.context_tags(c, sim.characters)
            assert ("knows_hazard_east_road" in tags) is (not on)
        finally:
            sim.close()


def test_new_fields_are_recorded_only_when_set():
    plain = fact().to_dict()
    assert "tags" not in plain and "from_afar" not in plain and "refreshed" not in plain
    full = fact(tags=("family",), from_afar=True, refreshed=9).to_dict()
    assert full["tags"] == ["family"] and full["from_afar"] is True and full["refreshed"] == 9
    json.dumps(full)
