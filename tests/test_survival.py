"""What keeps a village going (SPECIFICATION.md section 2.9j): a wider
fertile window, fields broken on new ground, blight only in summer, and
villagers cutting a blight out together."""

import json

import pytest
from bear import Corpus

from hearthwick import checkpoint, family
from hearthwick.__main__ import PROFILES, _saved
from hearthwick.character import Activity
from hearthwick.config import DATA_DIR, SimConfig
from hearthwick.food import FIELDS, field_places, field_tiles
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import BLIGHT_FIGHT_TICKS, Simulation
from hearthwick.world import Place


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw))


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


def adult(sim, n=0):
    return [c for c in sim.characters.values() if c.stage == "adult" and c.alive][n]


# -- the fertile window -----------------------------------------------------------

def test_the_wide_window_takes_in_elders_to_forty(sim):
    c = adult(sim)
    c.stage, c.age = "elder", 30.0
    assert family.fertile(c, wide=True) and not family.fertile(c)
    c.age = 41.0
    assert not family.fertile(c, wide=True)
    c.stage, c.age = "adult", 15.0
    assert family.fertile(c) and family.fertile(c, wide=True)
    c.stage, c.age = "elder", 30.0
    assert "fertile" in sim.brain.context_tags(c, sim.characters)          # the switch is on


def test_an_older_couple_is_not_refused_for_age_with_the_wide_window(sim):
    a, b = sim.characters["dunn"], sim.characters["gisla"]
    a.partner, b.partner = b.id, a.id
    a.home = b.home
    for c in (a, b):
        c.stage, c.age, c.pos = "elder", 32.0, sim.world.places[b.home].tiles()[0]
    assert family.refusal(a, sim.characters, sim.world, False) == "not of age"
    assert family.refusal(a, sim.characters, sim.world, False, wide=True) != "not of age"


def test_elders_court_and_have_children_with_the_wide_window(sim, tmp_path):
    from hearthwick.courtship import eligible
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    # Gated on fertile, which carries the stage, and not on being an adult.
    assert "stage_adult" not in corpus.get("family-have-child").scope.required_tags
    a, b = sim.characters["dunn"], sim.characters["gisla"]
    for c in (a, b):
        c.stage, c.age, c.partner = "elder", 30.0, None
    assert eligible(a, b, sim.characters, elders=True) and not eligible(a, b, sim.characters)
    assert "marriageable" in sim.courtship.tags(a)
    narrow = make_sim(tmp_path / "narrow", fertility=False)
    try:
        n = narrow.characters["dunn"]
        n.stage, n.partner = "elder", None
        assert "marriageable" not in narrow.courtship.tags(n)
    finally:
        narrow.close()


# -- fields on new ground --------------------------------------------------------

def fill(sim):
    """The map as founded taken up, so no field can grow into it."""
    world = sim.world
    world.add_place(Place("filled", "the village, full", "filled", (0, 0, world.width, world.height)))


def test_when_no_field_can_grow_new_ground_is_broken(sim):
    fill(sim)
    before = field_tiles(sim.world)
    farmer = next(c for c in sim.characters.values() if c.role == "farmer" and c.alive)
    sim._clear_fields(farmer, FIELDS)
    fields = field_places(sim.world)
    assert [p.id for p in fields] == ["fields", "fields_2"]
    assert fields[1].name == "the new fields" and fields[1].rect[2] == 4
    assert field_tiles(sim.world) == before + 16
    [added] = [e for e in events(sim, "place_added") if e["place"]["kind"] == "fields"]
    assert added["by"] == farmer.id


def test_without_land_growth_no_new_field_is_broken(tmp_path):
    s = make_sim(tmp_path, land=False)
    try:
        fill(s)
        farmer = next(c for c in s.characters.values() if c.role == "farmer" and c.alive)
        s._clear_fields(farmer, FIELDS)
        assert [p.id for p in field_places(s.world)] == ["fields"]
        assert resolve(s, farmer, "[!clear(place=fields)]") == []
    finally:
        s.close()


def test_work_in_the_fields_goes_where_there_are_fewest_hands(sim):
    fill(sim)
    farmer = next(c for c in sim.characters.values() if c.role == "farmer" and c.alive)
    sim._clear_fields(farmer, FIELDS)
    others = [c for c in sim.characters.values() if c.alive and c.id != farmer.id][:3]
    for o in others:
        o.pos = sim.world.places[FIELDS].tiles()[0]
    [action] = resolve(sim, farmer, "[!work(site=fields)]")
    assert action.data["place"] == "fields_2"


def test_a_new_field_survives_a_checkpoint(tmp_path):
    s = make_sim(tmp_path)
    fill(s)
    s._clear_fields(next(c for c in s.characters.values() if c.role == "farmer"), FIELDS)
    path = checkpoint.save(s)
    s.close()
    resumed = make_sim(tmp_path)
    try:
        resumed.resume_from(path)
        assert "fields_2" in resumed.world.places and resumed.world.places["fields_2"].kind == "fields"
    finally:
        resumed.close()


# -- the blight --------------------------------------------------------------------

def test_blight_comes_only_in_summer():
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    blight = corpus.get("world-blight-in-the-fields")
    assert "season_summer" in blight.scope.required_tags


def blighted(sim):
    sim.world_agent.state.sick_places[FIELDS] = sim.clock.day


def test_only_those_old_enough_fight_a_blight_and_only_while_there_is_one(sim):
    c = adult(sim)
    assert resolve(sim, c, "[!fight_blight]") == []                     # no blight
    blighted(sim)
    [action] = resolve(sim, c, "[!fight_blight]")
    assert action.kind == "fight_blight" and action.data["place"] == FIELDS
    child = next(o for o in sim.characters.values() if o.stage == "child")
    assert resolve(sim, child, "[!fight_blight]") == []


def test_without_the_switch_nobody_fights_it(tmp_path):
    s = make_sim(tmp_path, blight_fighting=False)
    try:
        blighted(s)
        assert resolve(s, adult(s), "[!fight_blight]") == []
    finally:
        s.close()


def test_enough_hands_cut_a_blight_out(sim):
    blighted(sim)
    hands = [adult(sim, n) for n in range(3)]
    field = sim.world.places[FIELDS]
    for c in hands:
        c.activity = Activity("fight_blight", {"place": FIELDS, "ticks": 24})
        c.pos = field.tiles()[0]
    for tick in range(BLIGHT_FIGHT_TICKS):
        sim._fight_blight(hands[tick % 3], field)
    state = sim.world_agent.state
    assert FIELDS not in state.sick_places and FIELDS not in state.fought
    [ended] = events(sim, "blight_ended")
    assert ended["by"] == sorted(c.id for c in hands)
    told = [f.text for store in sim.diffuser.stores.values() for f in store.facts]
    assert "The blight has been cut out of the fields." in told
    assert any("cut the blight out" in f.text for f in sim.diffuser.store_for(hands[0].id).facts)


def test_fighting_a_blight_begins_and_runs_as_any_stint_does(sim):
    """Begun and advanced the way the step does it. Left out of the list of
    activities at a place, it began with no ticks, and the next advance
    failed and paused the live village (2026-09-30)."""
    blighted(sim)
    c = adult(sim)
    [action] = resolve(sim, c, "[!fight_blight(ticks=3)]")
    c.activity = Activity(action.kind, dict(action.data))
    sim._begin(c)
    assert c.activity.ticks_left == 3 and (c.path or sim.world.places[FIELDS].contains(*c.pos))
    c.path = []
    c.pos = sim.world.places[FIELDS].tiles()[0]
    for _ in range(3):
        sim._advance(c)
    assert c.activity is None


def test_a_stint_saved_without_its_ticks_still_runs(sim):
    """The live village's checkpoint carried a blight fight begun without its
    ticks, and every resume failed on it."""
    c = adult(sim)
    c.activity = Activity("fight_blight", {"place": FIELDS, "ticks": 2})
    c.path = []
    assert c.activity.ticks_left is None
    sim._advance(c)
    sim._advance(c)
    assert c.activity is None


def test_every_stint_begins_with_its_ticks(sim):
    """Each kind of stint at a place gets its ticks when it begins. Building
    is left out: its place is the site, laid out only when a house is needed."""
    from hearthwick.sim import CRAFT_WORK
    c = adult(sim)
    for kind in (k for k in CRAFT_WORK if k != "build"):
        c.activity = Activity(kind, {"place": FIELDS, "ticks": 5, "what": "clay", "for": "self"})
        c.path = []
        sim._begin(c)
        assert c.activity.ticks_left == 5, kind


def test_a_blight_half_fought_keeps_the_work_done_until_it_passes(sim):
    blighted(sim)
    c = adult(sim)
    c.activity = Activity("fight_blight", {"place": FIELDS, "ticks": 12})
    for _ in range(10):
        sim._fight_blight(c, sim.world.places[FIELDS])
    state = sim.world_agent.state
    assert state.fought[FIELDS] == 10 and FIELDS in state.sick_places
    path = checkpoint.save(sim)
    resumed = make_sim(sim.config.runs_dir / "again")
    try:
        resumed.resume_from(path)
        assert resumed.world_agent.state.fought[FIELDS] == 10
    finally:
        resumed.close()
    state.recover(sim.clock.day + 10, sim.clock.ticks_per_day)
    assert state.fought == {}


# -- richer fields ------------------------------------------------------------------

def test_richer_fields_yield_half_as_much_again(sim, tmp_path):
    from hearthwick.food import CROP_PER_TILE, GATHER_PER_TICK, TEND_TICKS_PER_TILE
    food = sim.world_agent.state.food
    assert food.rich == 1.5 and food.capacity(10) == 10 * CROP_PER_TILE * 1.5
    food.crop = 0.0
    food.work("spring", 100)
    assert food.crop == pytest.approx(1.5 * CROP_PER_TILE / TEND_TICKS_PER_TILE)
    food.crop, food.store = 10.0, 0.0
    food.work("autumn", 100)
    assert food.store == pytest.approx(1.5 * GATHER_PER_TICK)
    plain = make_sim(tmp_path / "plain", richer_fields=False)
    try:
        assert plain.world_agent.state.food.rich == 1.0
    finally:
        plain.close()


def test_how_rich_the_fields_are_is_the_runs_setting_on_resume(tmp_path):
    s = make_sim(tmp_path, richer_fields=False)
    path = checkpoint.save(s)
    s.close()
    resumed = make_sim(tmp_path)
    try:
        resumed.resume_from(path)
        assert resumed.world_agent.state.food.rich == 1.5
    finally:
        resumed.close()


# -- switches ------------------------------------------------------------------------

def test_old_runs_and_the_paper_keep_the_old_rules(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({"config": {"seed": 3, "village": "greater"}}))
    config = SimConfig(runs_dir=tmp_path)
    saved = _saved(config, "old-run")[0]
    assert saved.fertility is False and saved.blight_fighting is False
    assert saved.richer_fields is False
    assert _saved(config, "old-run", ["fertility", "blight_fighting"])[0].fertility is True
    assert PROFILES["paper"]["fertility"] is False and PROFILES["paper"]["blight_fighting"] is False
    assert PROFILES["paper"]["richer_fields"] is False
