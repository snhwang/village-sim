"""The world is an entity on the same terms as a villager (DESIGN.md §2.1)."""

import asyncio
import json

import pytest
from bear import Context, MarkerAction

from hearthwick.config import SimConfig
from hearthwick.sim import Simulation
from hearthwick.world_agent import season_of


def make_sim(tmp_path, seed=0):
    return Simulation(SimConfig(seed=seed, llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()          # idempotent: a test may have closed it already


def test_seasons_divide_the_year(sim):
    clock = sim.clock
    seen = []
    for day in range(clock.days_per_year):
        clock.tick = day * clock.ticks_per_day
        seen.append(season_of(clock))
    assert set(seen) == {"spring", "summer", "autumn", "winter"}


def test_villagers_and_the_world_cannot_reach_each_other(sim):
    """Neither can retrieve the other's instructions: no shared tag."""
    world_tags = sim.world_agent.context_tags()
    assert "world" in world_tags

    villager = sim.characters["rosa"]
    villager_tags = sim.brain.context_tags(villager, sim.characters)
    assert "world" not in villager_tags

    for scored in sim.retriever.retrieve(sim.world_agent.situation(),
                                         Context(tags=world_tags), top_k=20):
        assert "world" in scored.instruction.scope.required_tags, scored.id

    for scored in sim.retriever.retrieve(sim.brain.situation(villager, sim.characters),
                                         Context(tags=villager_tags), top_k=20):
        assert "world" not in scored.instruction.scope.required_tags, scored.id


def test_the_world_decides_the_sky_and_then_the_day(sim):
    asyncio.run(sim.run(sim.clock.ticks_per_day * 2 + 10))
    sim.close()
    events = [json.loads(l) for l in (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    world_decisions = [e for e in events if e["type"] == "decision" and e["character"] == "world"]
    assert len(world_decisions) == 4
    foci = [("sky" in d["tags"], "happening" in d["tags"]) for d in world_decisions]
    assert foci == [(True, False), (False, True)] * 2
    for decision in world_decisions:
        chosen = decision["chosen"]
        if chosen and "sky" in decision["tags"]:
            assert any(a["kind"] == "weather" for a in decision["actions"]), chosen
        if chosen and "happening" in decision["tags"]:
            assert all(a["kind"] != "weather" for a in decision["actions"]), chosen
    # A day where every candidate is refused is a real outcome, not a failure:
    # if the weather is already what it would be and the last traveler's news
    # is still going round, there is nothing to decide. What must always hold
    # is that the log says which candidates were refused, so a quiet day can
    # be told apart from a broken one.
    for decision in world_decisions:
        if decision["chosen"] is None:
            actionable = [r for r in decision["retrieved"] if r["actionable"]]
            assert actionable, "nothing chosen and nothing was even available"
            assert all(r["refused"] for r in actionable),                 "nothing chosen but some candidate was not refused"


def test_an_event_already_in_effect_is_not_decided_again(sim):
    from hearthwick.markers import SickenHandler, WorldMarkerContext
    from bear import parse_actions

    marker = parse_actions("[!sicken(well)]")[0]
    context = WorldMarkerContext(sim.world, sim.clock, sim.world_agent.state)
    assert SickenHandler().to_action(marker, context) is not None

    sim.world_agent.state.sick_places["well"] = sim.clock.day
    assert SickenHandler().to_action(marker, context) is None


def test_weather_reaches_the_villagers_as_context(sim):
    rosa = sim.characters["rosa"]
    assert not any(t.startswith("weather_") for t in sim.brain.context_tags(rosa, sim.characters))

    sim.world_agent.state.weather = "storm"
    tags = sim.brain.context_tags(rosa, sim.characters)
    assert "weather_storm" in tags
    assert "storm" in sim.brain.situation(rosa, sim.characters).lower()


def test_witnesses_are_whoever_was_close_and_awake(sim):
    rosa = sim.characters["rosa"]
    rx, ry, rw, rh = sim.world.places["well"].rect
    rosa.pos = (rx + rw // 2, ry + rh // 2)
    assert "rosa" in sim._witnesses("well")

    far = sim.characters["garrick"]
    far.pos = (0, 29)
    assert "garrick" not in sim._witnesses("well")


def test_world_events_are_logged_with_ground_truth(sim):
    asyncio.run(sim.run(sim.clock.ticks_per_day * 3))
    sim.close()
    events = [json.loads(l) for l in (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    world_events = [e for e in events if e["type"] == "world_event"]
    assert world_events, "three days should produce at least one world event"
    for e in world_events:
        assert {"event", "place", "witnesses", "weather", "season"} <= set(e)


# --- the world has to be able to do more than one thing --------------------

def test_a_traveler_is_refused_while_the_last_one_is_still_news(sim):
    """The handler that never said no.

    Every other world marker is refused while its effect is in force. The
    traveler was not, so once the well was sick and the weather was what it
    would be, a traveler was the only thing left and the world sent one every
    day: six of nine events in a ten-day run.
    """
    from bear import parse_actions

    from hearthwick.markers import TravelerHandler, WorldMarkerContext
    from hearthwick.world_agent import NEWS_FRESH_DAYS

    marker = parse_actions("[!traveler(news)]")[0]
    context = WorldMarkerContext(sim.world, sim.clock, sim.world_agent.state)
    handler = TravelerHandler()
    assert handler.to_action(marker, context) is not None

    sim.world_agent.state.last_traveler_day = sim.clock.day
    assert handler.to_action(marker, context) is None

    sim.world_agent.state.last_traveler_day = sim.clock.day - NEWS_FRESH_DAYS - 1
    assert handler.to_action(marker, context) is not None, "news should go stale"


def test_the_world_recovers_so_it_can_repeat_itself(sim):
    """Without this every event is a one-way door and the world runs dry."""
    from hearthwick.world_agent import HAZARD_DAYS, SICKNESS_DAYS

    state = sim.world_agent.state
    state.sick_places["well"] = 0
    state.hazards["east_road"] = 0

    state.recover(SICKNESS_DAYS - 1, sim.clock.ticks_per_day)
    assert "well" in state.sick_places, "sickness should not pass on the first day"

    state.recover(SICKNESS_DAYS, sim.clock.ticks_per_day)
    assert "well" not in state.sick_places, "bad water has to clear eventually"

    state.recover(HAZARD_DAYS, sim.clock.ticks_per_day)
    assert "east_road" not in state.hazards, "a raided road stops being news"


def test_a_trader_is_not_a_hazard(sim):
    """A passing merchant used to set a hazard, which blocked raiders for ever."""
    state = sim.world_agent.state
    before = dict(state.hazards)
    sim._apply_world_action(MarkerAction("traveler", {"topic": "news", "place": "east_road"}, None))
    assert state.hazards == before, "a traveler must not leave a hazard behind"
    assert state.last_traveler_day == sim.clock.day


def test_every_world_instruction_belongs_to_one_decision(sim):
    """Weather took a third of the world's days when it shared one decision
    with everything else, and a day spent on the weather is a day with no news.
    Each world instruction now requires exactly one focus, and weather is the
    sky's alone."""
    from bear import parse_actions

    for instruction in sim.corpus.instructions:
        required = set(instruction.scope.required_tags or [])
        if "world" not in required:
            continue
        foci = required & {"sky", "happening"}
        assert len(foci) == 1, instruction.id
        weather = any(m.name == "weather" for m in parse_actions(instruction.content))
        assert weather == ("sky" in foci), instruction.id


def test_the_sky_and_the_day_see_the_same_dawn(sim):
    """Applying the sky first let the rain that ends a dry spell erase it
    before the day's event was decided, so the well could never sicken."""
    state = sim.world_agent.state
    state.days_since_rain = 5        # a dry spell, which the sky will end
    asyncio.run(sim.run(sim.clock.ticks_per_day + 2))
    sim.close()
    events = [json.loads(l) for l in (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    sky, day = [e for e in events if e["type"] == "decision" and e["character"] == "world"][:2]
    assert set(sky["tags"]) - {"sky"} == set(day["tags"]) - {"happening"}


def test_rain_does_not_undo_the_work_in_the_fields(sim):
    """A good harvest needs the fields well watered and well worked. Judged on
    yesterday alone the two never met, because on the rainy day that waters
    the fields everybody shelters."""
    state = sim.world_agent.state
    workers = {f"farmer{i}" for i in range(10)}
    state.field_workers = set(workers)       # a dry day of work
    state.roll_day(1, sim.clock.ticks_per_day)
    state.field_workers = set()              # a day of rain
    state.roll_day(2, sim.clock.ticks_per_day)
    state.days_since_rain = 0
    tags = sim.world_agent.context_tags()
    assert "well_watered" in tags and "well_worked" in tags

    for day in (3, 4, 5):                    # the work wears off
        state.roll_day(day, sim.clock.ticks_per_day)
    assert "fields_neglected" in sim.world_agent.context_tags()
