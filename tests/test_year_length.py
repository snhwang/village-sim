"""A year longer than eight days (--days-per-year) scales the rates that were
set per day for the eight-day year, and leaves them exactly as they were at
eight."""

import pytest

from hearthwick import family
from hearthwick.config import SimConfig
from hearthwick.food import (CROP_PER_TILE, START_DAYS_OF_FOOD, Food, field_tiles, need_per_day,
                             year_scale)
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw), None)


def test_the_eight_day_year_is_unchanged(tmp_path):
    sim = make_sim(tmp_path)
    try:
        food = sim.world_agent.state.food
        assert food.store == round(START_DAYS_OF_FOOD * need_per_day(sim.characters.values()), 2)
        assert food.scale == 1.0 and year_scale(8) == 1.0
        assert family.conception_chance(8) == family.CONCEPTION_CHANCE
    finally:
        sim.close()


def test_a_four_week_year_opens_with_food_to_its_first_harvest(tmp_path):
    sim = make_sim(tmp_path, days_per_year=28)
    try:
        food = sim.world_agent.state.food
        need = need_per_day(sim.characters.values())
        assert food.store == round(22 * need, 2)
        assert food.scale == 3.5
        tiles = field_tiles(sim.world)
        assert food.capacity(tiles) == pytest.approx(tiles * CROP_PER_TILE * food.rich * 3.5)
    finally:
        sim.close()


def test_the_land_a_person_needs_does_not_change_with_the_year():
    short, long = Food(scale=year_scale(8)), Food(scale=year_scale(28))
    for tiles, need in ((99, 30.0), (99, 60.0), (300, 60.0)):
        assert ("fields_small" in short.tags("spring", 0, 8, need, tiles, 0.0)) == \
               ("fields_small" in long.tags("spring", 0, 28, need, tiles, 0.0))


def test_a_year_of_trying_gives_the_same_odds():
    for days in (8, 16, 28, 56):
        p = family.conception_chance(days)
        assert 1 - (1 - p) ** days == pytest.approx(1 - (1 - family.CONCEPTION_CHANCE) ** 8)
