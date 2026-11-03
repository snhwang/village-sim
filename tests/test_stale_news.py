"""News that ended or never came (config.news_ends, config.false_alarms,
SPECIFICATION-memory.md section 9), and the illustrative profile that turns
on everything the village should now do. Skipped on a BEAR without items and
the importance floor."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from bear import Instruction, InstructionType, ScopeCondition  # noqa: E402

from hearthwick.__main__ import ADDABLE, PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.memory import DEADLINE_DAYS, as_lesson  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402
from hearthwick.world_agent import HAZARD_DAYS, SICKNESS_DAYS, WorldState  # noqa: E402


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "short_warnings": True, "afar_news": True,
                "fading_lessons": True, "news_ends": True, "false_alarms": True, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adults(sim, n):
    return [c for c in sim.characters.values()
            if c.alive and not c.visitor and c.stage in ("adult", "elder")][:n]


def strength(sim, fact_id):
    item = sim.diffuser.memory.retriever.corpus.get(fact_id)
    return item.metadata.get("salience")


def lesson_on(sim, who, sources, tick=0):
    inst = Instruction(id=f"learned-{who}-1", type=InstructionType.DIRECTIVE, priority=55,
                       content="Keep away from the well, the water is bad. [!avoid(place=well)]",
                       scope=ScopeCondition(required_tags=[f"char_{who}", "daytime"]),
                       metadata={"layer": "learned", "character": who})
    lesson = as_lesson(sim.diffuser.memory, inst, who, sources, tick)
    sim.corpus.add(lesson)
    sim.retriever.build_index()
    return lesson


def test_off_unless_asked_for_and_only_with_what_they_need(tmp_path):
    config = SimConfig()
    for name in ("news_ends", "false_alarms"):
        assert getattr(config, name) is False
        assert PROFILES["paper"][name] is False
        assert name in ADDABLE
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                             runs_dir=tmp_path / "a", embedder="bm25", news_ends=True))
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                             runs_dir=tmp_path / "b", embedder="bm25", bear_memory=True,
                             false_alarms=True))


def test_the_world_says_what_wore_off():
    state = WorldState()
    state.sick_places["well"] = 0
    state.hazards["east_road"] = 0
    assert state.roll_day(1, 144) == []
    ended = state.roll_day(max(SICKNESS_DAYS, HAZARD_DAYS), 144)
    assert ("sickness_passed", "well") in ended and ("danger_passed", "east_road") in ended


def test_an_ending_marks_down_what_was_known_and_the_lessons_on_it(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a = adults(sim, 1)[0]
        sick = sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)[0]
        raid = sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)[0]
        lesson = lesson_on(sim, a.id, [sick])
        assert sick.id in sim.diffuser.memory.salient(a.id, 10)
        sim.diffuser.witness("sickness_passed", "well", [a.id], {"place": "well"}, 600)
        assert strength(sim, sick.id) == 0.0
        assert sick.id not in sim.diffuser.memory.salient(a.id, 610)
        assert raid.id not in sim.diffuser.memory.marked_down       # another danger, another place
        assert sim.corpus.get(lesson.id).metadata["salience"] == 0.0  # the lesson follows
    finally:
        sim.close()


def test_old_news_of_an_ended_danger_is_marked_down_as_it_comes(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        sick = sim.diffuser.witness("sicken", "well", [b.id], {"place": "well"}, 0)[0]
        sim.diffuser.witness("sickness_passed", "well", [a.id], {"place": "well"}, 600)
        asyncio.run(sim.diffuser.offer(sick, b, a))
        heard = [f for f in sim.diffuser.store_for(a.id).facts if f.root == sick.root]
        assert heard and heard[0].id in sim.diffuser.memory.marked_down
    finally:
        sim.close()


def tale(sim, who, topic, tick=0):
    return sim.diffuser.witness("tale", "east_road", [who.id], {"topic": topic}, tick,
                                root=f"tale:east_road:{tick}-{topic[:8]}")[0]


def test_word_of_danger_that_never_comes_is_a_false_alarm(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        day = sim.clock.ticks_per_day
        lonely = tale(sim, a, "that there has been fighting beyond the forest")
        borne = tale(sim, b, "that there has been fighting beyond the forest", tick=1)
        sim.diffuser.witness("raid", "east_road", [b.id], {"place": "east_road"}, 3 * day)
        memory = sim.diffuser.memory
        assert memory.false_alarms(DEADLINE_DAYS * day - 1) == 0       # not yet due
        assert memory.false_alarms(DEADLINE_DAYS * day + 2) == 1
        assert lonely.id in memory.marked_down                          # nothing came
        assert borne.id not in memory.marked_down                       # raiders came
        assert memory.false_alarms(100 * day) == 0                      # judged once
    finally:
        sim.close()


def test_a_resumed_run_marks_down_again(tmp_path):
    sim = make_sim(tmp_path / "first")
    try:
        a = adults(sim, 1)[0]
        sick = sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)[0]
        sim.diffuser.witness("sickness_passed", "well", [a.id], {"place": "well"}, 600)
        sim.clock.tick = 700
        path = asyncio.run(sim.save())
    finally:
        sim.close()
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        assert sick.id in resumed.diffuser.memory.marked_down
        assert strength(resumed, sick.id) == 0.0
    finally:
        resumed.close()


def test_without_the_switches_nothing_is_marked_down(tmp_path):
    sim = make_sim(tmp_path, news_ends=False, false_alarms=False)
    try:
        a = adults(sim, 1)[0]
        sick = sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)[0]
        sim.diffuser.witness("sickness_passed", "well", [a.id], {"place": "well"}, 600)
        assert sim.diffuser.memory.false_alarms(10 ** 6) == 0
        assert not sim.diffuser.memory.marked_down and strength(sim, sick.id) != 0.0
    finally:
        sim.close()


def test_the_illustrative_profile_builds_a_village(tmp_path):
    from dataclasses import replace
    profile = PROFILES["illustrative"]
    assert profile["news_ends"] and profile["false_alarms"] and profile["decide_again"]
    config = replace(SimConfig(seed=0, village="greater", llm_base_url=None,
                               runs_dir=tmp_path, embedder="bm25"), **profile)
    sim = Simulation(config)
    try:
        assert sim.clock.days_per_year == 28
        assert sim.corpus.get("elder-help-tend") is not None        # elders in the fields
        assert "pupils_waiting" in sim.corpus.get("elder-teach").scope.required_tags
    finally:
        sim.close()


def test_routine_memories_fade_with_the_switch(tmp_path):
    from hearthwick.memory import ROUTINE_FADE_YEARS
    sim = make_sim(tmp_path, routine_fades=True)
    try:
        a = adults(sim, 1)[0]
        year = sim.clock.ticks_per_day * sim.clock.days_per_year
        memory = sim.diffuser.memory
        assert memory.half_life_of("met", a.id) == ROUTINE_FADE_YEARS["met"] * year
        assert memory.half_life_of("news", a.id) == 2 * year
        assert memory.half_life_of("hazard", a.id) < year        # dangers keep their days
    finally:
        sim.close()
    plain = make_sim(tmp_path / "off")
    try:
        assert plain.diffuser.memory.half_life_of("met", adults(plain, 1)[0].id) is None
    finally:
        plain.close()


def talk_target(sim, a, topic):
    from hearthwick.markers import MarkerContext, build_registry
    ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        talked_today=(sim.conversations.talked_today
                                      if sim.config.talk_once_a_day else None))
    actions = build_registry().process(
        f"Talk. [!talk(target=nearby, topic={topic})]", context=ctx)[1]
    return actions[0].data["target"] if actions else None


def test_the_same_talk_is_had_once_a_day(tmp_path):
    sim = make_sim(tmp_path, talk_once_a_day=True)
    try:
        a, b = adults(sim, 2)
        for other in sim.characters.values():
            if other.id != a.id:
                other.pos = (a.pos[0] + 40, a.pos[1] + 40)
        b.pos = (a.pos[0] + 1, a.pos[1])
        story = "a story from the old days"
        assert talk_target(sim, a, story) == b.id
        sim.conversations.start(a, b, story, None)
        a.conversation_id = b.conversation_id = None
        assert talk_target(sim, a, story) is None                 # had today
        assert talk_target(sim, a, "the weather") == b.id         # another topic
        sim.clock.tick += sim.clock.ticks_per_day
        assert talk_target(sim, a, story) == b.id                 # a new day
    finally:
        sim.close()
