"""Villagers die of old age, and the village goes on (hearthwick/mortality.py)."""

import json

import pytest

from hearthwick import checkpoint, courtship, grounding, mortality, trades
from hearthwick.config import SimConfig
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def test_a_lifespan_is_drawn_once_and_in_range(sim):
    spans = {c.id: mortality.lifespan(c, 0) for c in sim.characters.values()}
    assert all(mortality.LIFESPAN[0] <= v <= mortality.LIFESPAN[1] for v in spans.values())
    assert len(set(spans.values())) == len(spans)                   # each its own
    mabel = sim.characters["mabel"]
    assert mortality.lifespan(mabel, 0) == spans["mabel"]            # fixed at birth
    assert mortality.lifespan(mabel, 1) != spans["mabel"]            # and by the seed
    assert max(c.age for c in sim.characters.values()) < mortality.LIFESPAN[0]


def test_a_villager_dies_at_the_first_midnight_past_its_span(sim):
    mabel = sim.characters["mabel"]
    span = mortality.lifespan(mabel, sim.config.seed)
    mabel.age = span - 0.01
    sim.mortality.new_day()
    assert mabel.alive
    mabel.age = span
    sim.mortality.new_day()
    assert not mabel.alive
    assert all(c.alive for c in sim.characters.values() if c.id != "mabel")


def test_a_death_is_known_by_those_it_lived_with(sim):
    mabel = sim.characters["mabel"]
    household = sorted(o.id for o in sim.characters.values() if o.alive and o.id != "mabel"
                       and o.home == mabel.home and o.stage != "infant")
    assert household
    sim.mortality.die(mabel, sim.clock.tick)
    assert not mabel.alive
    [died] = events(sim, "died")
    assert died["character"] == "mabel" and died["partner"] == "edek"
    for who in household:
        facts = [f for f in sim.diffuser.store_for(who).facts if f.root == "death:mabel"]
        assert facts and facts[0].text == "Mabel died in the night." and facts[0].hop == 0
    frame = sim.log.frame(sim.clock.tick, sim.clock.to_dict(),
                          [c.frame() for c in sim.characters.values() if c.alive])
    assert all(row[0] != "mabel" for row in frame["c"])


def test_a_widow_may_marry_again_and_remembers(sim):
    ch = sim.characters
    edek, mabel = ch["edek"], ch["mabel"]
    assert not courtship.free(edek, ch)
    sim.mortality.die(mabel, sim.clock.tick)
    assert courtship.free(edek, ch)
    assert edek.partner == "mabel"                   # the record stays
    assert "Your partner, Mabel, has died." in grounding.life(sim, edek)


def test_apprentices_go_to_the_master_they_are_fondest_of(sim):
    ch = sim.characters
    master = next(m for m in trades.working(ch) if trades.apprentices_of(m.id, ch))
    [apprentice, *_] = trades.apprentices_of(master.id, ch)
    others = [m for m in trades.practitioners(apprentice.trade, ch)
              if m.id != master.id
              and len(trades.apprentices_of(m.id, ch)) < trades.MAX_APPRENTICES]
    if not others:
        pytest.skip("no other master of that trade with room in this village")
    fondest = others[-1]
    sim.courtship.affinity[courtship.pair(apprentice.id, fondest.id)] = 9.0
    sim.mortality.die(master, sim.clock.tick)
    assert apprentice.mentor == fondest.id
    [moved] = [e for e in events(sim, "new_master") if e["character"] == apprentice.id]
    assert moved["was"] == master.id and moved["master"] == fondest.id


def test_with_mortality_off_nobody_dies(tmp_path):
    s = make_sim(tmp_path, mortality=False)
    try:
        for c in s.characters.values():
            c.age = 90.0
        s.mortality.new_day()
        assert all(c.alive for c in s.characters.values())
    finally:
        s.close()


def test_runs_recorded_before_mortality_resume_without_it(sim):
    saved = {"seed": 3, "village": "greater"}
    assert SimConfig.from_saved(saved, sim.config).mortality is False
    assert SimConfig.from_saved({**saved, "mortality": True}, sim.config).mortality is True


def test_the_dead_stay_dead_across_a_checkpoint(tmp_path):
    s = make_sim(tmp_path)
    s.mortality.die(s.characters["mabel"], s.clock.tick)
    path = checkpoint.save(s)
    s.close()
    t = make_sim(tmp_path)
    try:
        t.resume_from(path)
        assert not t.characters["mabel"].alive and t.mortality.died == 1
        assert courtship.free(t.characters["edek"], t.characters)
    finally:
        t.close()
