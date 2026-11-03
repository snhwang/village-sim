"""Lessons that outlast their news (config.lasting_lessons,
SPECIFICATION-memory.md). With short warnings the news fades in days, and a
lesson resting on it used to fade with it. With this switch a lesson fades
over the years its news once took. Skipped on a BEAR without items and the
importance floor."""

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from bear import Instruction, InstructionType, ScopeCondition  # noqa: E402

from hearthwick.__main__ import ADDABLE, PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.memory import FADE_DAYS, as_lesson  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "fading_lessons": True, "short_warnings": True,
                "afar_news": True, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def lesson(who):
    return Instruction(id=f"learned-{who}-1", type=InstructionType.DIRECTIVE, priority=55,
                       content="Raiders were on the road. Warn whoever is near. "
                               "[!warn(target=nearby, topic=raiders)]",
                       scope=ScopeCondition(required_tags=[f"char_{who}", "daytime"]),
                       metadata={"layer": "learned", "character": who})


def test_off_unless_asked_for_and_only_with_fading_lessons(tmp_path):
    assert SimConfig().lasting_lessons is False
    assert PROFILES["paper"]["lasting_lessons"] is False
    assert "lasting_lessons" in ADDABLE
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", bear_memory=True, lasting_lessons=True))


def test_a_lesson_lasts_years_while_its_news_lasts_days(tmp_path):
    sim = make_sim(tmp_path, lasting_lessons=True)
    try:
        who = next(iter(sim.characters))
        raid = sim.diffuser.witness("raid", "east_road", [who], {"place": "east_road"}, 0)[0]
        sick = sim.diffuser.witness("sicken", "well", [who], {"place": "well"}, 0)[0]
        day = sim.clock.ticks_per_day
        year = day * sim.clock.days_per_year
        memory = sim.diffuser.memory
        assert memory.half_life_of(raid.kind, who, raid.tags) == FADE_DAYS["hazard"] * day
        assert memory.lesson_half_life_of(raid, who) == 2 * year      # a danger, two years
        assert memory.lesson_half_life_of(sick, who) == year          # a sickness, one
        made = as_lesson(memory, lesson(who), who, [raid, sick], 10)
        assert made.metadata["half_life"] == year                     # the shorter of the two
        assert made.metadata["parents"] == [raid.id, sick.id]          # and still rests on both
    finally:
        sim.close()


def test_without_it_a_lesson_fades_with_its_news(tmp_path):
    sim = make_sim(tmp_path)
    try:
        who = next(iter(sim.characters))
        raid = sim.diffuser.witness("raid", "east_road", [who], {"place": "east_road"}, 0)[0]
        made = as_lesson(sim.diffuser.memory, lesson(who), who, [raid], 10)
        assert made.metadata["half_life"] == FADE_DAYS["hazard"] * sim.clock.ticks_per_day
    finally:
        sim.close()


def test_danger_that_can_come_lasts_as_a_danger(tmp_path):
    sim = make_sim(tmp_path, lasting_lessons=True)
    try:
        who = next(iter(sim.characters))
        tale = sim.diffuser.witness("tale", "east_road", [who],
                                    {"topic": "that there has been fighting beyond the forest"},
                                    0, root="tale:east_road:0")[0]
        year = sim.clock.ticks_per_day * sim.clock.days_per_year
        assert sim.diffuser.memory.lesson_half_life_of(tale, who) == 2 * year
    finally:
        sim.close()
