"""Lessons as BEAR items that fade with the news they came from
(config.fading_lessons, hearthwick/memory.py, SPECIFICATION-warnings.md
section 2). Skipped on a BEAR without items and the importance floor."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from bear import Context, Corpus, Instruction, InstructionType, ScopeCondition  # noqa: E402
from bear.config import Config  # noqa: E402
from bear.retriever import Embedder, Retriever  # noqa: E402

from hearthwick.__main__ import PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.memory import LESSON_FLOOR, as_lesson  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, **switches):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                bear_memory=True, fading_lessons=True, **switches))


def owned_lesson(who, content="Warn the others: sickness is in the valley. "
                              "[!warn(target=nearby, topic=sickness)]"):
    return Instruction(id=f"learned-{who}-1", type=InstructionType.DIRECTIVE, priority=55,
                       content=content,
                       scope=ScopeCondition(required_tags=[f"char_{who}", "daytime"],
                                            tags=["near_someone"]),
                       metadata={"layer": "learned", "character": who})


def test_off_unless_asked_for_and_only_with_bear_memory(tmp_path):
    assert SimConfig().fading_lessons is False
    assert PROFILES["paper"]["fading_lessons"] is False
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", fading_lessons=True))


def test_a_lesson_fades_as_its_shortest_fading_source_does(tmp_path):
    sim = make_sim(tmp_path)
    try:
        who = next(iter(sim.characters))
        sick = sim.diffuser.witness("sicken", "well", [who], {"place": "well"}, 0)[0]
        raid = sim.diffuser.witness("raid", "east_road", [who], {"place": "east_road"}, 0)[0]
        lesson = as_lesson(sim.diffuser.memory, owned_lesson(who), who, [raid, sick], 10)
        year = sim.clock.ticks_per_day * sim.clock.days_per_year
        assert lesson.metadata["half_life"] == year            # sickness, one year
        assert lesson.metadata["parents"] == [raid.id, sick.id]
        assert lesson.metadata["created"] == 10.0
        assert lesson.metadata["layer"] == "learned"           # still a learned lesson
        required = set(lesson.scope.required_tags)
        assert {"item", f"char_{who}", "daytime"} <= required  # its gates stay hard
        assert lesson.scope.tags == ["near_someone"]
        plain = as_lesson(sim.diffuser.memory, owned_lesson(who, "Rest. [!rest]"), who, [], 10)
        assert plain.metadata.get("half_life") is None         # rests on nothing: never fades
    finally:
        sim.close()


def test_a_faded_lesson_drops_out_of_decisions():
    who = "ada"
    corpus = Corpus()
    lesson = items.item("Warn the others. [!warn(target=nearby)]", who, id="learned-ada-1",
                        kind="lesson", created=0.0, half_life=100.0, priority=55)
    lesson = lesson.model_copy(update={"scope": ScopeCondition(
        required_tags=sorted(set(lesson.scope.required_tags) | {"daytime"}))})
    corpus.add(lesson)
    corpus.add(Instruction(id="adult-work", type=InstructionType.DIRECTIVE, priority=60,
                           content="Go to work. [!work(site=own)]",
                           scope=ScopeCondition(required_tags=["daytime"])))
    retriever = Retriever(corpus, config=Config(default_threshold=-1.0, mandatory_tags=[]),
                          embedder=Embedder(model_name="hash"))
    retriever.build_index()

    def ids(now):
        ctx = Context(tags=["daytime", f"char_{who}"], gate_tags=["item"], now=float(now),
                      min_salience=LESSON_FLOOR)
        return {s.instruction.id for s in retriever.retrieve("what now", ctx, top_k=10)}

    assert ids(100) == {"learned-ada-1", "adult-work"}         # exactly one half-life old
    assert ids(101) == {"adult-work"}                          # past it: gone
    retriever.reinforce(["learned-ada-1"], 101.0)              # its news witnessed again
    assert "learned-ada-1" in ids(150)


def test_witnessing_the_news_again_renews_the_lesson(tmp_path):
    sim = make_sim(tmp_path)
    try:
        who = next(iter(sim.characters))
        sick = sim.diffuser.witness("sicken", "well", [who], {"place": "well"}, 0)[0]
        lesson = as_lesson(sim.diffuser.memory, owned_lesson(who), who, [sick], 0)
        sim.corpus.add(lesson)
        sim.retriever.build_index()
        # Lived again. Without the embedding service a second witnessing is a
        # second fact rather than a duplicate, so the store is told directly.
        sim.diffuser.store_for(who).reinforce(sick, refreshed=500)
        sim.diffuser.store_for(who).tags()                     # the next question flushes
        assert sim.corpus.get(lesson.id).metadata["reinforced"] == 500.0
    finally:
        sim.close()


def test_a_lesson_survives_a_checkpoint_with_its_clock(tmp_path):
    sim = make_sim(tmp_path)
    try:
        who = next(iter(sim.characters))
        sick = sim.diffuser.witness("sicken", "well", [who], {"place": "well"}, 0)[0]
        lesson = as_lesson(sim.diffuser.memory, owned_lesson(who), who, [sick], 7)
        sim.corpus.add(lesson)
        sim.retriever.build_index()
        path = asyncio.run(sim.save())
        resumed = make_sim(tmp_path / "again")
        try:
            resumed.resume_from(path)
            back = resumed.corpus.get(lesson.id)
            assert back.type == InstructionType.ITEM
            for key in ("created", "half_life", "parents", "layer"):
                assert back.metadata[key] == lesson.metadata[key]
            assert set(back.scope.required_tags) == set(lesson.scope.required_tags)
        finally:
            resumed.close()
    finally:
        sim.close()
