"""The village eats what its villagers grow and bring in (hearthwick/food.py)."""

import asyncio
import json

import pytest
from bear import Context

from hearthwick.character import Activity
from hearthwick.config import SimConfig
from hearthwick.food import (CLEAR_TICKS_PER_STRIP, CROP_PER_TILE, FIELDS, GATHER_PER_TICK,
                             TEND_TICKS_PER_TILE, Food, days_to_harvest_end, need_per_day)
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation
from hearthwick.trades import level_at, output_factor


def make_sim(tmp_path, village="greater"):
    return Simulation(SimConfig(seed=0, village=village, llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def at_day(sim, day, hour=10):
    sim.clock.tick = (day * 24 + hour - sim.clock.start_hour) * 60 // sim.clock.minutes_per_tick


# --- the arithmetic ------------------------------------------------------------

def test_tending_grows_the_crop_up_to_what_the_fields_hold():
    food = Food()
    for _ in range(TEND_TICKS_PER_TILE * 10 * 2):
        food.work("spring", tiles=10)
    assert food.crop == pytest.approx(10 * CROP_PER_TILE)
    assert food.store == 0


def test_only_hands_in_the_fields_bring_the_harvest_in():
    food = Food(crop=1.0)
    food.work("autumn", tiles=10)
    assert food.store == pytest.approx(GATHER_PER_TICK)
    for _ in range(100):
        food.work("autumn", tiles=10)
    assert food.store == pytest.approx(1.0) and food.crop == 0


def test_what_is_still_standing_at_winter_is_lost():
    food = Food(store=50, crop=40, gathered=30)
    brought_in = food.dawn("winter", "autumn", need=10, blighted=False)
    assert brought_in == 30
    assert food.crop == 0 and food.store == 40 and food.last_harvest == 30


def test_frost_and_blight_spoil_the_crop():
    food = Food(crop=100)
    food.frost()
    assert food.crop == 50
    food.dawn("summer", "summer", need=0, blighted=True)
    assert food.crop < 50


def test_the_granary_is_never_negative():
    food = Food(store=3)
    food.dawn("spring", "spring", need=10, blighted=False)
    assert food.store == 0


def test_the_next_harvest_is_in_at_the_end_of_autumn():
    # eight-day years, two days a season: autumn is days 4 and 5
    assert days_to_harvest_end(0, 8) == 6
    assert days_to_harvest_end(5, 8) == 1
    assert days_to_harvest_end(6, 8) == 8


def test_what_villagers_see():
    tags = Food(store=0).tags("spring", 0, 8, need=10, tiles=100, season_progress=0.5)
    assert {"hungry", "food_low", "crop_behind"} <= set(tags)
    tags = Food(store=1000, crop=5).tags("autumn", 4, 8, need=10, tiles=100, season_progress=1)
    assert "harvest_ripe" in tags and "food_low" not in tags
    assert "fields_small" in Food().tags("winter", 6, 8, need=30, tiles=99, season_progress=1)
    assert "fields_small" not in Food().tags("winter", 6, 8, need=10, tiles=99, season_progress=1)


# --- the village ---------------------------------------------------------------

def test_the_founding_granary_lasts_until_the_first_harvest(sim):
    food, need = sim.world_agent.state.food, need_per_day(sim.characters.values())
    assert food.store / need >= days_to_harvest_end(0, sim.clock.days_per_year)


def test_the_greater_village_cannot_feed_itself_on_its_founding_fields(sim, tmp_path):
    need = need_per_day(sim.characters.values())
    tiles = len(sim.world.places[FIELDS].tiles())
    assert Food().capacity(tiles) < need * sim.clock.days_per_year
    hamlet = make_sim(tmp_path / "hamlet", village=None)
    try:
        need = need_per_day(hamlet.characters.values())
        assert Food().capacity(len(hamlet.world.places[FIELDS].tiles())) > need * 8
    finally:
        hamlet.close()


def test_work_in_the_fields_feeds_the_village(sim):
    at_day(sim, 4)                     # autumn
    food = sim.world_agent.state.food
    food.crop, before = 50.0, food.store
    farmer = next(c for c in sim.characters.values() if c.role == "farmer")
    farmer.pos = sim.world.places[FIELDS].tiles()[0]
    farmer.activity = Activity("work", {"place": FIELDS, "ticks": 5}, ticks_left=5)
    farmer.path = []
    sim._physics()
    skill = output_factor(level_at(farmer, FIELDS))      # a farmer of years does more
    assert food.store == pytest.approx(before + skill * food.rich * GATHER_PER_TICK)


def test_the_harvest_is_what_was_brought_in_and_becomes_news(sim):
    food = sim.world_agent.state.food
    food.gathered = 1.0                # a thin harvest
    at_day(sim, 6, hour=6)             # the first dawn of winter
    sim._world_turn()
    harvest = [a for _, a in sim._pending_events if a.kind == "harvest"]
    assert harvest and harvest[0].data == {"yield": "poor", "brought_in": 1.0}
    sim._apply_world_action(harvest[0])
    assert sim.world_agent.state.last_harvest == "poor"


def test_the_world_no_longer_decides_the_harvest(sim):
    world_ids = [i.id for i in sim.corpus if "world" in (i.scope.required_tags or [])]
    assert not any("[!harvest" in sim.corpus.get(i).content for i in world_ids)


def test_clearing_ground_grows_the_fields(sim):
    at_day(sim, 6)                     # winter
    before = sim.world.places[FIELDS].rect
    farmer = next(c for c in sim.characters.values() if c.role == "farmer")
    farmer.pos = sim.world.places[FIELDS].tiles()[0]
    farmer.path = []
    for _ in range(CLEAR_TICKS_PER_STRIP):
        farmer.activity = Activity("clear", {"place": FIELDS, "ticks": 5}, ticks_left=5)
        sim._physics()
    after = sim.world.places[FIELDS].rect
    assert after != before
    assert len(sim.world.places[FIELDS].tiles()) > before[2] * before[3]
    for place in sim.world.places.values():     # it swallowed nothing
        if place.id != FIELDS:
            assert not set(place.tiles()) & set(sim.world.places[FIELDS].tiles())


def test_a_village_out_of_land_stops_clearing(sim):
    while sim.world.grow(FIELDS):
        pass
    farmer = next(c for c in sim.characters.values() if c.role == "farmer")
    ctx = MarkerContext(sim.world, sim.clock, farmer, sim.characters,
                        sim.rng_for("t", "t"), sim.config.near_radius)
    _, actions = build_registry().process("[!clear(place=fields)]", context=ctx)
    assert actions == []


def test_food_and_the_grown_fields_survive_a_checkpoint(sim, tmp_path):
    sim.world_agent.state.food.store = 123.0
    rect = sim.world.grow(FIELDS)
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        assert resumed.world_agent.state.food.store == 123.0
        assert resumed.world.places[FIELDS].rect == rect
    finally:
        resumed.close()


def test_a_villager_is_only_sent_to_rest_when_tired(sim):
    """A precondition is a hard gate. As a soft preference, "You are
    exhausted" was chosen 703 times in the headline run, and nobody in it was
    ever tired."""
    adult = next(c for c in sim.characters.values() if c.stage == "adult")
    adult.energy = 1.0
    tags = sim.brain.context_tags(adult, sim.characters)
    scored = sim.retriever.retrieve("You are exhausted.", Context(tags=tags), top_k=200)
    assert "adult-tired" not in [s.id for s in scored]
    adult.energy = 0.1
    tags = sim.brain.context_tags(adult, sim.characters)
    scored = sim.retriever.retrieve("You are exhausted.", Context(tags=tags), top_k=200)
    assert "adult-tired" in [s.id for s in scored]


def test_the_food_situation_is_logged_each_day(sim):
    at_day(sim, 1, hour=6)
    sim._world_turn()
    sim.log.flush()
    events = [json.loads(line) for line in open(sim.log.dir / "events.jsonl", encoding="utf-8")]
    food = [e for e in events if e["type"] == "food"]
    assert food and {"store", "crop", "need", "capacity", "tiles"} <= set(food[-1])


def _resolve(sim, who, content):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters,
                        sim.rng_for("t", "t"), sim.config.near_radius)
    return build_registry().process(content, context=ctx)[1]


def test_going_where_you_already_are_is_refused(sim):
    """A bold farmer at the forest edge chose to walk out to the forest edge
    seven times running."""
    who = next(c for c in sim.characters.values() if c.stage == "adult")
    who.pos = sim.world.places["forest_edge"].tiles()[0]
    assert _resolve(sim, who, "[!go(to=forest_edge)]") == []
    assert [a.kind for a in _resolve(sim, who, "[!go(to=forest_edge)] [!rest(ticks=4)]")] == ["rest"]
    who.pos = sim.world.places[who.home].tiles()[0]
    assert [a.kind for a in _resolve(sim, who, "[!go(to=forest_edge)]")] == ["go"]


def test_nobody_keeps_away_from_their_own_work(sim):
    farmer = next(c for c in sim.characters.values() if c.role == "farmer")
    other = next(c for c in sim.characters.values() if c.role and c.role != "farmer")
    assert _resolve(sim, farmer, "[!avoid(place=fields)]") == []
    assert [a.kind for a in _resolve(sim, other, "[!avoid(place=fields)]")] == ["avoid"]
