"""A lesson declares as it is written which news it answers, how often it
acts again and how long it lasts (config.declared_lessons,
SPECIFICATION-memory.md section 12). Skipped on a BEAR whose items do not rest
and wake."""

import asyncio
import re

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "rest"):
    pytest.skip("this BEAR predates declared instructions", allow_module_level=True)

from bear import Instruction, InstructionType, ScopeCondition  # noqa: E402

from hearthwick.__main__ import ADDABLE, PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.consolidation import consolidate  # noqa: E402
from hearthwick.memory import as_lesson  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "fading_lessons": True, "short_warnings": True,
                "afar_news": True, "lessons_satisfied": True, "declared_lessons": True,
                **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adult(sim):
    return next(c for c in sim.characters.values()
                if c.alive and not c.visitor and c.stage in ("adult", "elder"))


class Writer:
    """A stand-in lesson writer: it cites the observation holding ``cite``,
    and records the prompt it was shown."""

    def __init__(self, cite, recurs="each_time", lasts="season", content=None):
        self.cite, self.recurs, self.lasts, self.prompts = cite, recurs, lasts, []
        self.content = content or "Raiders came. Warn whoever is near. [!warn(target=nearby)]"

    async def generate(self, system, user, temperature):
        self.prompts.append(user)
        numbers = [n for n, text in re.findall(r"\[(\d+)\] (.*)", user)
                   if self.cite is not None and self.cite in text]
        about = f"[{numbers[0]}]" if numbers else "[]"
        reply = ("instructions:\n  - id: learned-x-1\n    type: directive\n"
                 f"    priority: 30\n    content: \"{self.content}\"\n"
                 f"    about: {about}\n    recurs: {self.recurs}\n    lasts: {self.lasts}\n")
        return type("Reply", (), {"content": reply})()


class Speech:
    available = True

    def __init__(self, writer):
        self.writer = writer

    def llm_for_generation(self):
        return self.writer


def written(sim, c, writer):
    sim.speech = Speech(writer)
    added = asyncio.run(consolidate(sim, c, "adult"))
    assert added, "the stand-in lesson should have been kept"
    return sim.corpus.get(added[0].id)


def lesson(sim, who, content, sources, recurs, name="1"):
    inst = Instruction(id=f"learned-{who}-{name}", type=InstructionType.DIRECTIVE, priority=55,
                       content=content,
                       scope=ScopeCondition(required_tags=[f"char_{who}", "daytime"]),
                       metadata={"layer": "learned", "character": who, "recurs": recurs})
    made = as_lesson(sim.diffuser.memory, inst, who, sources, 0)
    sim.corpus.add(made)
    sim.retriever.build_index()
    return made


WARN = "Raiders came. Warn whoever is near. [!warn(target=nearby, topic=raiders)]"


def test_off_unless_asked_for_and_only_with_lessons_satisfied(tmp_path):
    assert SimConfig().declared_lessons is False
    assert PROFILES["paper"]["declared_lessons"] is False
    assert PROFILES["illustrative"]["declared_lessons"] is True
    assert "declared_lessons" in ADDABLE
    with pytest.raises(ValueError, match="needs lessons_satisfied"):
        make_sim(tmp_path, lessons_satisfied=False)


def test_the_writer_sees_the_facts_and_the_vocabularies(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        writer = Writer(cite=raid.text)
        written(sim, c, writer)
        prompt = writer.prompts[0]
        assert re.search(r"\[\d+\] " + re.escape(raid.text), prompt)
        for name in ("each_time:", "each_day:", "always:", "season:", "life:"):
            assert name in prompt
    finally:
        sim.close()


def test_a_lesson_answers_the_news_it_cites_and_lasts_as_declared(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        made = written(sim, c, Writer(cite=raid.text, recurs="each_time", lasts="season"))
        meta = made.metadata
        assert meta["parents"] == [raid.id]
        assert meta["recurs"] == "each_time" and meta["lasts"] == "season"
        year = sim.clock.ticks_per_day * sim.clock.days_per_year
        assert meta["half_life"] == pytest.approx(year / 4)
    finally:
        sim.close()


def test_a_general_rule_answers_no_news(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)
        made = written(sim, c, Writer(cite=None, recurs="each_day", lasts="life"))
        assert made.metadata["parents"] == []
        assert made.metadata.get("half_life") is None          # for life
    finally:
        sim.close()


def test_without_the_switch_nothing_is_asked(tmp_path):
    sim = make_sim(tmp_path, declared_lessons=False)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        writer = Writer(cite=raid.text)
        made = written(sim, c, writer)
        assert "Observations" not in writer.prompts[0]
        assert "recurs" not in made.metadata and "about" not in made.metadata
    finally:
        sim.close()


def test_a_declared_habit_never_rests(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        warn = lesson(sim, c.id, WARN, [raid], recurs="always")
        assert not sim.diffuser.memory.satisfied(c.id, warn.id, 10)
        assert warn.id not in sim.diffuser.memory.resting()
    finally:
        sim.close()


def test_a_daily_lesson_wakes_with_the_day_not_with_its_event(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        raid = sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 0)[0]
        daily = lesson(sim, c.id, WARN, [raid], recurs="each_day")
        memory = sim.diffuser.memory
        assert memory.satisfied(c.id, daily.id, 10)
        sim.diffuser.witness("raid", "east_road", [c.id], {"place": "east_road"}, 50)
        assert daily.id in memory.resting()                       # not by its event
        memory.new_day(sim.clock.ticks_per_day)
        assert daily.id not in memory.resting()                   # by the day
    finally:
        sim.close()


def test_a_lesson_on_its_event_cannot_wait_for_news_it_lacks(tmp_path):
    sim = make_sim(tmp_path)
    try:
        c = adult(sim)
        alone = lesson(sim, c.id, WARN, [], recurs="each_time")
        assert sim.diffuser.memory.recurs_of(alone) == "each_day"
    finally:
        sim.close()


def test_lifetimes(tmp_path):
    sim = make_sim(tmp_path)
    try:
        memory = sim.diffuser.memory
        year = sim.clock.ticks_per_day * sim.clock.days_per_year
        assert memory.lifetime_of("season", [], "x") == pytest.approx(year / 4)
        assert memory.lifetime_of("year", [], "x") == pytest.approx(year)
        assert memory.lifetime_of("life", [], "x") is None
        assert memory.lifetime_of("news", [], "x") == pytest.approx(year / 4)
        assert memory.lifetime_of(None, [], "x") is None         # undeclared, as before
    finally:
        sim.close()
