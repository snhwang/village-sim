"""The land grows when the village is full (hearthwick/land.py)."""

import json

import pytest

from hearthwick import building, checkpoint
from hearthwick.__main__ import PROFILES, _saved
from hearthwick.config import SimConfig
from hearthwick.follow import world_for
from hearthwick.land import GROW_BY
from hearthwick.sim import Simulation
from hearthwick.world import Place


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                **{"materials": False, "money": False, **kw}))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def full(sim, monkeypatch=None):
    """The map as founded taken up from edge to edge, so only land added has
    room."""
    world = sim.world
    world.add_place(Place("filled", "the village, full", "filled", (0, 0, world.width, world.height)))


def crafter(sim):
    return next(c for c in sim.characters.values()
                if building.is_builder(c) and c.stage in ("adult", "elder"))


def test_new_land_is_open_and_the_road_runs_on_to_it(sim):
    world = sim.world
    road, forest = world.places["east_road"].rect, world.places["forest_edge"].rect
    roads = world.extend_east(GROW_BY)
    assert world.width == 40 + GROW_BY
    assert roads == {"east_road": (road[0], road[1], road[2] + GROW_BY, road[3])}
    assert world.places["east_road"].rect == roads["east_road"]
    assert world.places["forest_edge"].rect == forest                 # the forest stays
    assert all(world.walkable((x, y)) for x in range(40, world.width) for y in range(world.height))
    assert world.path((30, 20), (world.width - 1, 5))                   # and it can be reached


def test_a_house_with_no_plot_left_is_built_on_new_land(sim, monkeypatch):
    full(sim, monkeypatch)
    sim.courtship.waiting.append(("dunn", "gisla"))
    sim.building.timber = building.TIMBER_PER_HOUSE
    c = crafter(sim)
    assert sim.building.can_build(c)
    site = sim.building.start(c, sim.clock.tick)
    assert site is not None and sim.world.places[site].rect[0] >= 40
    [grown] = events(sim, "land_grown")
    assert grown["width"] == 40 + GROW_BY and grown["roads"]["east_road"][2] == 12 + GROW_BY
    assert sim.land.grown == 1


def test_without_the_switch_the_map_keeps_its_size(tmp_path, monkeypatch):
    s = make_sim(tmp_path, land=False)
    try:
        full(s, monkeypatch)
        s.courtship.waiting.append(("dunn", "gisla"))
        s.building.timber = building.TIMBER_PER_HOUSE
        assert not s.building.can_build(crafter(s))
        assert s.building.start(crafter(s), s.clock.tick) is None
        assert s.world.width == 40 and events(s, "land_grown") == []
        assert not s.land.room(3)
    finally:
        s.close()


def test_asking_for_room_does_not_grow_the_land(sim, monkeypatch):
    full(sim, monkeypatch)
    assert sim.land.room(5)
    assert sim.world.width == 40                                        # only asked, not grown


def test_the_grown_land_survives_a_checkpoint(tmp_path, monkeypatch):
    s = make_sim(tmp_path)
    full(s, monkeypatch)
    s.courtship.waiting.append(("dunn", "gisla"))
    s.building.timber = building.TIMBER_PER_HOUSE
    site = s.building.start(crafter(s), s.clock.tick)
    rect = s.world.places[site].rect
    path = checkpoint.save(s)
    s.close()
    resumed = make_sim(tmp_path)
    try:
        resumed.resume_from(path)
        assert resumed.world.width == 40 + GROW_BY and resumed.land.grown == 1
        assert resumed.world.places["east_road"].rect[2] == 12 + GROW_BY
        assert resumed.building.site.rect == rect
    finally:
        resumed.close()


def test_a_replay_is_drawn_on_the_land_as_it_grew(sim, monkeypatch):
    full(sim, monkeypatch)
    sim.courtship.waiting.append(("dunn", "gisla"))
    sim.building.timber = building.TIMBER_PER_HOUSE
    sim.building.start(crafter(sim), sim.clock.tick)
    sim.log.flush()
    world = world_for(sim.log.dir, sim.config.data_dir)
    assert world.width == 40 + GROW_BY
    assert world.places["east_road"].rect[2] == 12 + GROW_BY
    assert world_for(sim.log.dir, sim.config.data_dir, grown=False).width == 40


def test_a_conversation_can_outlast_the_site_it_was_held_on(sim):
    """A building site is removed when what stands on it is finished. A
    conversation held there once ended by looking the site up, and the step
    failed, which paused the live village (2026-09-29)."""
    sim.courtship.waiting.append(("dunn", "gisla"))
    sim.building.timber = building.TIMBER_PER_HOUSE
    a = crafter(sim)
    site = sim.world.places[sim.building.start(a, sim.clock.tick)]
    b = next(c for c in sim.characters.values() if c.alive and c.id != a.id and c.stage == "adult")
    a.pos = b.pos = site.tiles()[0]
    conv = sim.conversations.start(a, b, "the house", None)
    sim.world.remove_place(site.id)
    sim.conversations.end(conv)
    held = [f.text for f in sim.diffuser.store_for(a.id).facts if f.kind == "met"]
    assert any("at the village" in t for t in held)
    # And a walk begun toward a site that is gone ends where it began.
    from hearthwick.character import Activity
    a.activity = Activity("go", {"place": site.id})
    sim._begin(a)
    assert a.activity.ticks_left == 0 and a.path == []


def test_old_runs_and_the_paper_keep_the_map_as_it_was(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({"config": {"seed": 3, "village": "greater"}}))
    config = SimConfig(runs_dir=tmp_path)
    assert _saved(config, "old-run")[0].land is False
    assert _saved(config, "old-run", ["land"])[0].land is True
    assert PROFILES["paper"]["land"] is False
