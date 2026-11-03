"""School, then a trade chosen on graduating, a master, and getting better (hearthwick/trades.py)."""

import pytest

from hearthwick import trades
from hearthwick.character import Activity
from hearthwick.config import SimConfig
from hearthwick.food import FIELDS, GATHER_PER_TICK
from hearthwick.growth import GATES, TICKS_PER_LEVEL
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def resolve(sim, who, content):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters,
                        sim.rng_for("t", "t"), sim.config.near_radius, news=sim.brain._news_roots)
    return build_registry().process(content, context=ctx)[1]


def graduate(sim):
    """A child who has just left school, with no trade yet."""
    child = next(c for c in sorted(sim.characters.values(), key=lambda c: c.id)
                 if c.stage == "child" and c.parents)
    child.stage, child.trade, child.mentor = "apprentice", None, None
    return child


def at_day(sim, day, hour=10):
    sim.clock.tick = (day * 24 + hour - sim.clock.start_hour) * 60 // sim.clock.minutes_per_tick


# --- founders ------------------------------------------------------------------

def test_founders_have_their_trades_and_their_years_behind_them(sim):
    for c in sim.characters.values():
        if c.stage in ("adult", "elder") and c.role:
            assert c.trade == c.role
            assert trades.level_at(c, trades.site_of(c.role, sim.world)) >= 2
        if c.stage == "apprentice":
            assert c.trade == sim.characters[c.mentor].role
    old = max((c for c in sim.characters.values() if c.stage == "child"), key=lambda c: c.age)
    assert old.growth.practice.get(trades.SCHOOL, 0) > 0


def test_school_is_in_the_corpus(sim):
    assert sim.corpus.get("child-school") is not None and sim.corpus.get("elder-teach") is not None


# --- choosing a trade -------------------------------------------------------------

def test_a_graduate_sees_what_it_leans_toward(sim):
    g = graduate(sim)
    tags = sim.brain.context_tags(g, sim.characters)
    assert "graduating" in tags
    parent_roles = {sim.characters[p].role for p in g.parents if sim.characters[p].role}
    assert {f"parent_{r}" for r in parent_roles} <= set(tags)
    assert any(t.startswith("needed_") for t in tags)


def test_a_master_is_found_and_a_parent_comes_first(sim):
    g = graduate(sim)
    parent = next(sim.characters[p] for p in g.parents if sim.characters[p].role)
    action = resolve(sim, g, f"[!apprentice(trade={parent.role})]")
    assert action and action[0].data == {"trade": parent.role, "master": parent.id}


def test_a_graduate_goes_to_the_master_it_is_fondest_of(sim):
    """Fondness decides before kinship. With none to go on, a parent comes
    first, as the test above shows."""
    from hearthwick.courtship import pair
    g = graduate(sim)
    parent = next(sim.characters[p] for p in g.parents if sim.characters[p].role)
    other = next(m for m in trades.practitioners(parent.role, sim.characters)
                 if m.id != parent.id and m.id not in g.parents)
    sim.courtship.affinity[pair(g.id, other.id)] = 5.0
    sim.courtship.affinity[pair(g.id, parent.id)] = 2.0
    ctx = MarkerContext(sim.world, sim.clock, g, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        courtship=sim.courtship)
    action = build_registry().process(f"[!apprentice(trade={parent.role})]", context=ctx)[1]
    assert action and action[0].data == {"trade": parent.role, "master": other.id}


def test_a_trade_with_no_free_master_is_refused(sim):
    g = graduate(sim)
    (storyteller,) = trades.practitioners("storyteller", sim.characters)
    assert resolve(sim, g, "[!apprentice(trade=storyteller)]")
    others = [c for c in sim.characters.values()
              if c.stage == "apprentice" and c.id != g.id][:trades.MAX_APPRENTICES]
    for c in others:
        c.mentor = storyteller.id
    assert resolve(sim, g, "[!apprentice(trade=storyteller)]") == []


def test_only_a_graduate_can_take_up_a_trade(sim):
    adult = next(c for c in sim.characters.values() if c.stage == "adult")
    assert resolve(sim, adult, "[!apprentice(trade=farmer)]") == []
    g = graduate(sim)
    assert resolve(sim, g, "[!apprentice(trade=alchemist)]") == []


def test_a_graduate_chooses_by_retrieval_and_is_taken_on(sim):
    g = graduate(sim)
    at_day(sim, 1)
    decision, actions = sim.brain.decide(g, sim.characters)
    chosen = [a for a in actions if a.kind == "apprentice"]
    assert chosen, f"chose {decision.chosen} instead of a trade"
    assert decision.chosen.startswith("trade-")
    g.activity = None
    g.queue.extend(sim._activity(a, decision.chosen) for a in chosen)
    sim._advance(g)
    assert g.trade == chosen[0].data["trade"] and g.mentor == chosen[0].data["master"]
    assert "graduating" not in sim.brain.context_tags(g, sim.characters)


# --- getting better ------------------------------------------------------------

def test_an_apprentice_learns_twice_as_fast_beside_its_master(sim):
    apprentice = next(c for c in sim.characters.values() if c.stage == "apprentice")
    master = sim.characters[apprentice.mentor]
    site = trades.site_of(apprentice.trade, sim.world)
    tile = sim.world.places[site].tiles()[0]
    apprentice.pos, apprentice.path = tile, []
    apprentice.activity = Activity("work", {"place": site, "ticks": 5}, ticks_left=5)
    master.pos, master.path = (0, 0), []
    assert sim._practice_ticks(apprentice, site) == 1
    master.pos = tile
    master.activity = Activity("work", {"place": site, "ticks": 5}, ticks_left=5)
    assert sim._practice_ticks(apprentice, site) == trades.MASTER_SPEEDUP


def test_a_skilled_hand_brings_in_more(sim):
    at_day(sim, 4)                           # autumn
    food = sim.world_agent.state.food
    food.crop = 100.0
    farmer = max((c for c in sim.characters.values() if c.role == "farmer"),
                 key=lambda c: trades.level_at(c, FIELDS))
    helper = next(c for c in sim.characters.values() if c.role == "guard")
    gains = []
    for who in (farmer, helper):
        who.pos, who.path = sim.world.places[FIELDS].tiles()[0], []
        who.activity = Activity("work", {"place": FIELDS, "ticks": 5}, ticks_left=5)
        before = food.store
        sim._field_work(who, food, "autumn")
        gains.append(food.store - before)
    per_tick = food.rich * GATHER_PER_TICK            # richer fields yield more (food.RICH_FIELDS)
    assert gains[0] > per_tick > gains[1]
    assert gains[1] == pytest.approx(trades.output_factor(0) * per_tick)


def test_a_qualified_apprentice_takes_up_its_trade(tmp_path):
    sim = make_sim(tmp_path, growth=True)
    try:
        apprentice = next(c for c in sim.characters.values() if c.stage == "apprentice")
        gate = GATES["apprentice"]
        apprentice.age = gate.min_age + 1
        for i in range(gate.knowledge):
            apprentice.growth.learned(f"event:{i}")
        for i in range(gate.experience):
            apprentice.growth.lived_through(f"kind{i}")
        site = trades.site_of(apprentice.trade, sim.world)
        apprentice.growth.practice[site] = TICKS_PER_LEVEL * gate.trade_skill
        sim._grow()
        assert apprentice.stage == "adult" and apprentice.role == apprentice.trade
    finally:
        sim.close()
