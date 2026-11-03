"""Crafters fell timber and build a house when a couple needs one
(hearthwick/building.py)."""

import asyncio
import json

import pytest

from hearthwick import building
from hearthwick.config import SimConfig
from hearthwick.follow import world_for
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, materials=False, money=False))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
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


def waiting_couple(sim):
    """Gisla and Dunn, married and living at Dunn's house with Katrin."""
    ch = sim.characters
    gisla, dunn = ch["gisla"], ch["dunn"]
    gisla.stage, gisla.age = "adult", 8.0
    gisla.partner, dunn.partner = "dunn", "gisla"
    gisla.home = dunn.home = "home_2"
    sim.courtship.waiting.append(("dunn", "gisla"))
    return gisla, dunn


def test_only_crafters_see_a_house_is_needed_and_only_when_it_is(sim):
    edda, osric = sim.characters["edda"], sim.characters["osric"]
    assert "house_needed" not in sim.brain.context_tags(edda, sim.characters)
    waiting_couple(sim)
    tags = sim.brain.context_tags(edda, sim.characters)
    assert "house_needed" in tags and "timber_short" in tags and "timber_ready" not in tags
    assert "house_needed" not in sim.brain.context_tags(osric, sim.characters)
    sim.building.timber = building.TIMBER_PER_HOUSE
    tags = sim.brain.context_tags(edda, sim.characters)
    assert "timber_ready" in tags and "timber_short" not in tags


def test_felling_and_building_are_refused_when_they_would_do_nothing(sim):
    edda, osric = sim.characters["edda"], sim.characters["osric"]
    assert resolve(sim, edda, "[!fell]") == []                 # no house needed
    waiting_couple(sim)
    assert resolve(sim, osric, "[!fell]") == []                # not a crafter
    assert [a.data["place"] for a in resolve(sim, edda, "[!fell]")] == [building.FOREST]
    assert resolve(sim, edda, "[!build]") == []                # no timber yet
    sim.building.timber = building.TIMBER_PER_HOUSE
    assert resolve(sim, edda, "[!fell]") == []                 # timber enough
    assert [a.data["place"] for a in resolve(sim, edda, "[!build]")] == [None]


def test_a_plot_is_clear_of_every_place_and_on_dry_ground(sim):
    rect = sim.world.find_plot(building.PLOT)
    assert rect is not None
    x, y, w, h = rect
    for i in range(x - 1, x + w + 1):
        for j in range(y - 1, y + h + 1):
            assert sim.world.walkable((i, j)) and sim.world.place_at((i, j)) is None


def test_felling_at_the_forest_edge_adds_timber(sim):
    edda = sim.characters["edda"]
    waiting_couple(sim)
    for a in resolve(sim, edda, "[!fell(ticks=6)]"):
        edda.queue.append(sim._activity(a, "crafter-fell-timber"))
    sim._advance(edda)
    edda.path = []
    edda.pos = sim.world.places[building.FOREST].tiles()[0]
    mill = edda.growth.practice.get("mill", 0)
    level = edda.growth.skills.get("mill", 0)
    sim._physics()
    from hearthwick.trades import output_factor
    assert sim.building.timber == pytest.approx(building.TIMBER_PER_TICK * output_factor(level))
    assert edda.growth.practice["mill"] == mill + 1      # felling is practice at the craft


def test_crafters_stop_felling_when_there_is_timber_enough(sim):
    edda = sim.characters["edda"]
    waiting_couple(sim)
    for a in resolve(sim, edda, "[!fell(ticks=12)]"):
        edda.queue.append(sim._activity(a, "crafter-fell-timber"))
    sim._advance(edda)
    edda.path = []
    edda.pos = sim.world.places[building.FOREST].tiles()[0]
    sim.building.timber = building.TIMBER_PER_HOUSE
    sim._physics()
    assert sim.building.timber == building.TIMBER_PER_HOUSE
    sim._advance(edda)
    assert edda.activity is None


def test_building_lays_out_a_site_and_a_house_goes_up(sim):
    gisla, dunn = waiting_couple(sim)
    baby = sim.family.birth(gisla, dunn, sim.clock.tick)
    assert baby.home == "home_2"
    edda = sim.characters["edda"]
    sim.building.timber = building.TIMBER_PER_HOUSE
    for a in resolve(sim, edda, "[!build]"):
        edda.queue.append(sim._activity(a, "crafter-start-house"))
    sim._advance(edda)
    site = sim.building.site
    assert site is not None and site.id in sim.world.places
    assert edda.activity.data["place"] == site.id
    edda.pos = site.tiles()[0]
    for _ in range(int(building.WORK_PER_HOUSE)):
        sim.building.work(edda, 1.0, sim.clock.tick)
        if sim.building.site is None:
            break
    assert sim.building.site is None and building.SITE not in sim.world.places
    home = sim.world.places["home_14"]
    assert home.kind == "home" and home.rect == site.rect
    assert gisla.home == dunn.home == baby.home == "home_14"
    assert sim.characters["katrin"].home == "home_2"
    assert sim.courtship.waiting == []
    assert sim.building.timber == pytest.approx(0.0, abs=1e-9)
    assert events(sim, "house_built")[0]["couple"] == ["dunn", "gisla"]
    assert "house_needed" not in sim.brain.context_tags(edda, sim.characters)
    # The map a viewer is sent has the new house in it, and no site.
    grown = world_for(sim.log.dir, sim.config.data_dir)
    assert "home_14" in grown.places and building.SITE not in grown.places
    assert "home_14" not in world_for(sim.log.dir, sim.config.data_dir, grown=False).places


def test_building_stops_when_the_timber_runs_out(sim):
    waiting_couple(sim)
    edda = sim.characters["edda"]
    sim.building.timber = 3.0
    sim.building.start(edda, sim.clock.tick)
    edda.pos = sim.building.site.tiles()[0]
    for _ in range(int(building.WORK_PER_HOUSE)):
        sim.building.work(edda, 1.0, sim.clock.tick)
    per_work = building.TIMBER_PER_HOUSE / building.WORK_PER_HOUSE
    assert sim.building.progress == pytest.approx(3.0 / per_work)
    assert sim.building.site is not None
    assert resolve(sim, edda, "[!build]") == []


def test_a_house_going_up_survives_a_checkpoint(sim, tmp_path):
    waiting_couple(sim)
    edda = sim.characters["edda"]
    sim.building.timber = 12.0
    sim.building.start(edda, sim.clock.tick)
    edda.pos = sim.building.site.tiles()[0]
    for _ in range(20):
        sim.building.work(edda, 1.0, sim.clock.tick)
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        b = resumed.building
        assert b.site is not None and b.site.rect == sim.building.site.rect
        assert building.SITE in resumed.world.places
        assert b.timber == pytest.approx(sim.building.timber)
        assert b.progress == pytest.approx(sim.building.progress)
    finally:
        resumed.close()


def test_each_frame_reports_the_house_going_up_only_while_one_is_needed(sim):
    assert sim.building.status() is None
    frame = sim.log.frame(0, sim.clock.to_dict(), [], sim.building.status())
    assert "b" not in frame
    waiting_couple(sim)
    sim.building.timber = 6.0
    status = sim.building.status()
    assert status == {"site": None, "timber": 6.0, "timber_needed": building.TIMBER_PER_HOUSE,
                      "work": 0.0, "work_needed": building.WORK_PER_HOUSE,
                      "goods": {"timber": [6.0, 30.0]}, "project": None, "queued": 0,
                      "unpaid": 0, "plan": None, "waiting": [["dunn", "gisla"]]}
    frame = sim.log.frame(0, sim.clock.to_dict(), [], status)
    assert frame["b"]["waiting"] == [["dunn", "gisla"]]
