"""Materials and money: goods, the places they come from, coins, and the
merchant as the market (hearthwick/goods.py, hearthwick/economy.py)."""

import json

import pytest

from hearthwick import building, checkpoint
from hearthwick.__main__ import PROFILES, _saved
from hearthwick.character import Activity
from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation

def make_sim(tmp_path, speech=None, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw), speech)


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    s.economy.ensure(0)
    yield s
    s.close()


def resolve(sim, who, marker):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        courtship=sim.courtship, building=sim.building)
    return build_registry().process(marker, context=ctx)[1]


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def someone(sim, role):
    return next(c for c in sim.characters.values()
                if c.role == role and c.stage in ("adult", "elder") and c.alive)


def crafter(sim):
    return next(c for c in sim.characters.values()
                if building.is_builder(c) and c.stage in ("adult", "elder"))


def at(sim, c, place_id):
    c.pos = sim.world.places[place_id].tiles()[0]
    c.path = []


def stint(sim, c, marker, ticks=None):
    """Decide, walk there at once, and do the stint, a tick at a time."""
    [action] = resolve(sim, c, marker)
    c.activity = Activity(action.kind, dict(action.data))
    sim._begin(c)
    at(sim, c, action.data["place"])
    for _ in range(ticks or action.data.get("ticks", 1)):
        if c.activity is None:
            break
        if c.activity.kind == "sell":
            sim._advance(c)
            break
        sim._craft_work(c, sim.world.place_at(c.pos))
        c.activity.ticks_left -= 1
        if c.activity.ticks_left <= 0:
            sim._finish(c)


# -- goods ------------------------------------------------------------------

def test_without_materials_no_places_are_added(tmp_path):
    s = make_sim(tmp_path, materials=False)
    try:
        assert s.building.needs_of_a_house() == {"timber": building.TIMBER_PER_HOUSE}
        s.economy.ensure(0)
        assert "quarry" not in s.world.places
    finally:
        s.close()


def test_the_places_materials_need_are_added_near_their_kind(sim):
    for pid, near in (("quarry", "forest"), ("clay_pit", "fields"), ("forge", "mill")):
        assert sim.world.places[pid].kind == pid
    added = [e["place"]["id"] for e in events(sim, "place_added")]
    assert added == ["quarry", "clay_pit", "forge"]
    sim.economy.ensure(1)
    assert len(events(sim, "place_added")) == 3                       # only once


# -- the crafters gather what a house needs -----------------------------------

def test_a_house_takes_timber_alone_which_the_crafters_fell(sim):
    sim.courtship.waiting.append(("dunn", "gisla"))
    c = crafter(sim)
    tags = sim.building.tags(c)
    assert "timber_short" in tags and "clay_short" not in tags and "timber_ready" not in tags
    assert resolve(sim, c, "[!gather(what=clay, for=building)]") == []   # none needed
    assert resolve(sim, c, "[!smelt]") == []
    assert sim.building.tags(someone(sim, "merchant")) == []          # nothing from the road
    for _ in range(20):
        if "timber_short" not in sim.building.tags(c):
            break
        stint(sim, c, "[!fell(ticks=12)]")
    # A stint that would add nothing ends, so there is no more than a tick's over.
    assert building.TIMBER_PER_HOUSE <= sim.building.timber < building.TIMBER_PER_HOUSE + 1.5
    assert resolve(sim, c, "[!fell]") == []
    assert "timber_ready" in sim.building.tags(c)
    site = sim.building.start(c, sim.clock.tick)
    c.pos = sim.world.places[site].tiles()[0]
    for tick in range(2000):
        sim.building.work(c, 1.0, tick)
        if sim.building.site is None:
            break
    assert events(sim, "house_built") and sim.building.timber < 1.0
    assert sim.economy.coins("dunn") == 10.0                          # houses are free


# -- earning and selling ------------------------------------------------------

def test_purses_open_for_everyone_living_when_money_begins(sim):
    [opened] = events(sim, "purses_opened")
    assert opened["coins"] == 10.0
    assert all(sim.economy.coins(c.id) == 10.0 for c in sim.characters.values()
               if c.alive and not c.visitor)


def test_work_at_a_place_yields_what_is_made_there_whoever_does_it(sim):
    farmer, guard, merchant = someone(sim, "farmer"), someone(sim, "guard"), someone(sim, "merchant")
    sim.economy.worked(farmer, "fields", 1.0)
    sim.economy.worked(merchant, "fields", 1.0)                        # not its trade, still grain
    sim.economy.worked(farmer, "mill", 1.0)
    sim.economy.worked(guard, "watchpost", 1.0)                        # a watch makes nothing
    assert sim.economy.carrying(farmer.id) == {"grain": pytest.approx(0.1), "flour": pytest.approx(0.08)}
    assert sim.economy.carrying(merchant.id) == {"grain": pytest.approx(0.1)}
    assert sim.economy.carrying(guard.id) == {}


def test_goods_are_sold_at_the_market_less_the_merchants_cut(sim):
    farmer = someone(sim, "farmer")
    merchants = [c for c in sim.characters.values() if c.role == "merchant" and c.alive]
    for _ in range(40):
        sim.economy.worked(farmer, "fields", 1.0)
    assert "carrying_goods" in sim.economy.tags(farmer)
    stint(sim, farmer, "[!sell]")
    [sold] = events(sim, "sold")
    assert sold["goods"] == {"grain": 4.0} and sold["coins"] == pytest.approx(3.6)
    assert sim.economy.coins(farmer.id) == pytest.approx(13.6)
    assert sim.economy.coins(merchants[0].id) == pytest.approx(10.0 + 0.4 / len(merchants))
    assert sim.economy.carrying(farmer.id) == {} and "carrying_goods" not in sim.economy.tags(farmer)


def test_nothing_is_wanted_so_nothing_is_bought_or_saved_for(sim):
    farmer = someone(sim, "farmer")
    sim.economy.purse[farmer.id] = 100.0
    assert "want_unpaid" not in sim.economy.tags(farmer)
    assert resolve(sim, farmer, "[!buy(what=want)]") == []
    assert resolve(sim, farmer, "[!save]") == []


# -- death, checkpoints, switches ----------------------------------------------

def test_what_a_villager_had_goes_to_its_partner_or_children(sim):
    farmer = someone(sim, "farmer")
    sim.economy.worked(farmer, "fields", 1.0)
    partner = sim.characters.get(farmer.partner) if farmer.partner else None
    heirs_before = {h: sim.economy.coins(h) for h in sim.economy.purse}
    sim.mortality.die(farmer, 0)
    [inherited] = events(sim, "inherited")
    assert inherited["coins"] == 10.0 and farmer.id not in sim.economy.purse
    if partner is not None and partner.alive:
        assert inherited["heirs"] == [partner.id]
    for heir in inherited["heirs"]:
        assert sim.economy.coins(heir) > heirs_before[heir]


def test_money_and_goods_survive_a_checkpoint(tmp_path):
    s = make_sim(tmp_path)
    s.economy.ensure(0)
    farmer = someone(s, "farmer")
    s.economy.worked(farmer, "fields", 1.0)
    s.economy.purse[farmer.id] = 17.5
    s.building.gather("clay", 4.0)
    path = checkpoint.save(s)
    s.close()
    resumed = make_sim(tmp_path)
    try:
        resumed.resume_from(path)
        assert resumed.economy.coins(farmer.id) == 17.5 and resumed.economy.funded
        assert resumed.economy.carrying(farmer.id) == {"grain": pytest.approx(0.1)}
        assert resumed.building.stock["clay"] == 4.0
        assert "quarry" in resumed.world.places
        resumed.economy.ensure(1)
        assert len([p for p in resumed.world.places if p == "quarry"]) == 1
    finally:
        resumed.close()


def test_the_frames_carry_the_purses_each_hour(sim):
    frame = sim.log.frame(0, sim.clock.to_dict(), [], None, sim.economy.summary())
    farmer = someone(sim, "farmer")
    assert frame["m"][farmer.id] == [10.0, 0.0]


def test_old_runs_and_the_paper_have_neither(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({"config": {"seed": 3, "village": "greater"}}))
    config = SimConfig(runs_dir=tmp_path)
    saved = _saved(config, "old-run")[0]
    assert saved.materials is False and saved.money is False
    both = _saved(config, "old-run", ["materials", "money"])[0]
    assert both.materials and both.money
    assert PROFILES["paper"]["materials"] is False and PROFILES["paper"]["money"] is False


def test_without_money_there_are_no_purses(tmp_path):
    s = make_sim(tmp_path, money=False)
    try:
        s.economy.ensure(0)
        assert not events(s, "purses_opened") and s.economy.tags(someone(s, "farmer")) == []
        assert resolve(s, someone(s, "farmer"), "[!gather(what=stone)]") == []
    finally:
        s.close()
