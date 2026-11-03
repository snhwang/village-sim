"""A one-shot lesson's urge ends once its goal is met, until something
rekindles it (config.lessons_satisfied, SPECIFICATION-memory.md section 11).
Skipped on a BEAR whose items do not rest and wake."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "rest"):
    pytest.skip("this BEAR predates resting items", allow_module_level=True)

from bear import Instruction, InstructionType, ScopeCondition  # noqa: E402

from hearthwick.__main__ import ADDABLE, PROFILES  # noqa: E402
from hearthwick.character import Activity  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.memory import as_lesson  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "fading_lessons": True, "short_warnings": True,
                "afar_news": True, "lessons_satisfied": True, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adult(sim):
    return next(c for c in sim.characters.values()
                if c.alive and not c.visitor and c.stage in ("adult", "elder"))


def lesson(sim, who, content, sources, name="1"):
    inst = Instruction(id=f"learned-{who}-{name}", type=InstructionType.DIRECTIVE, priority=55,
                       content=content,
                       scope=ScopeCondition(required_tags=[f"char_{who}", "daytime"]),
                       metadata={"layer": "learned", "character": who})
    made = as_lesson(sim.diffuser.memory, inst, who, sources, 0)
    sim.corpus.add(made)
    sim.retriever.build_index()
    return made


def strength(sim, lesson_id):
    return sim.corpus.get(lesson_id).metadata.get("salience")


WARN = "Raiders were on the east road. Warn whoever is near. [!warn(target=nearby, topic=raiders)]"


def test_off_unless_asked_for_and_only_with_fading_lessons(tmp_path):
    assert SimConfig().lessons_satisfied is False
    assert PROFILES["paper"]["lessons_satisfied"] is False
    assert PROFILES["illustrative"]["lessons_satisfied"] is True
    assert "lessons_satisfied" in ADDABLE
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", bear_memory=True, lessons_satisfied=True))


def test_a_one_shot_lesson_rests_once_carried_out(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        warn = lesson(sim, c.id, WARN, [raid])
        c.activity = Activity(kind="warn", data={"target": "x"}, instruction_id=warn.id)
        c.queue.clear()
        sim._finish(c)
        assert strength(sim, warn.id) == 0.0 and warn.id in sim.diffuser.memory.resting()
    finally:
        sim.close()


def test_not_until_the_last_of_it_is_done(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        go = lesson(sim, c.id, "Go and look. [!go(to=east_road)] [!warn(target=nearby)]", [raid])
        c.activity = Activity(kind="go", data={"to": "east_road"}, instruction_id=go.id)
        c.queue.clear()
        c.queue.append(Activity(kind="warn", data={}, instruction_id=go.id))
        sim._finish(c)
        assert go.id not in sim.diffuser.memory.resting()           # the warning is still to come
    finally:
        sim.close()


def test_a_habit_never_rests(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        tend = lesson(sim, c.id, "The crop needs hands. [!work(site=fields, ticks=6)]", [])
        assert not sim.diffuser.memory.satisfied(c.id, tend.id, 10)
        assert strength(sim, tend.id) != 0.0
    finally:
        sim.close()


def test_the_same_kind_of_event_there_rekindles_it(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        warn = lesson(sim, c.id, WARN, [raid])
        memory = sim.diffuser.memory
        memory.satisfied(c.id, warn.id, 10)
        sim.diffuser.witness("raid", "well", [c.id], {"place": "well"}, 500)
        assert warn.id in memory.resting()                          # another place
        sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 900)
        assert warn.id not in memory.resting() and strength(sim, warn.id) == 1.0
    finally:
        sim.close()


def test_a_lesson_on_no_news_wakes_the_next_day(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        shrine = lesson(sim, c.id, "Walk to the shrine. [!go(to=shrine)]", [], name="2")
        memory = sim.diffuser.memory
        assert memory.satisfied(c.id, shrine.id, 10)
        memory.new_day(sim.clock.ticks_per_day)
        assert shrine.id not in memory.resting() and strength(sim, shrine.id) == 1.0
    finally:
        sim.close()


def test_a_resumed_run_keeps_its_resting_lessons(tmp_path):
    sim = make_sim(tmp_path / "first")
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        warn = lesson(sim, c.id, WARN, [raid])
        sim.diffuser.memory.satisfied(c.id, warn.id, 10)
        path = asyncio.run(sim.save())
    finally:
        sim.close()
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        assert warn.id in resumed.diffuser.memory.resting()
    finally:
        resumed.close()


def test_without_the_switch_a_lesson_never_rests(tmp_path):
    sim = make_sim(tmp_path, lessons_satisfied=False)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        warn = lesson(sim, c.id, WARN, [raid])
        c.activity = Activity(kind="warn", data={}, instruction_id=warn.id)
        sim._finish(c)
        assert strength(sim, warn.id) != 0.0
    finally:
        sim.close()
