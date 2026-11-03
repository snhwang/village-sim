"""A warning is about the fresh news that unlocked it, passes on only that,
and goes only to someone the warner has not told it (config.fresh_warnings,
SPECIFICATION-warnings.md section 13). Skipped on a BEAR without items and
the importance floor."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from bear import ScopeCondition  # noqa: E402

from hearthwick.__main__ import PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.markers import MarkerContext, build_registry  # noqa: E402
from hearthwick.memory import FADE_DAYS  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402

SWITCHES = {"bear_memory": True, "short_warnings": True, "afar_news": True,
            "told_memory": True, "quick_warnings": True}


def make_sim(tmp_path, fresh=True):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                fresh_warnings=fresh, **SWITCHES))


def adults(sim, n):
    return [c for c in sim.characters.values()
            if c.alive and not c.visitor and c.stage in ("adult", "elder")][:n]


def alone_with(sim, a, *others):
    """Everyone but ``others`` out of reach of ``a``, and those one step away."""
    for other in sim.characters.values():
        if other.id != a.id:
            other.pos = (a.pos[0] + 40, a.pos[1] + 40)
    for i, other in enumerate(others):
        other.pos = (a.pos[0] + 1 + i, a.pos[1])


def warn(sim, a, instruction_id="knows-warn-about-road"):
    """What ``a`` would do with the warning ``instruction_id``, resolved as a
    decision resolves it."""
    inst = sim.corpus.get(instruction_id)
    brain = sim.brain
    ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=brain._news_roots,
                        known_to=brain.known_to, quick_warnings=True,
                        warn_news=brain._warn_news if sim.config.fresh_warnings else None,
                        instruction=inst)
    actions = build_registry().process(inst.content, context=ctx)[1]
    return actions[0] if actions else None


def raid(sim, who, tick):
    return sim.diffuser.witness("raid", "east_road", [w.id for w in who], {"place": "east_road"},
                                tick, root=f"raid:east_road:{tick}")[0]


def test_off_unless_asked_for_and_only_with_its_needs(tmp_path):
    assert SimConfig().fresh_warnings is False
    assert PROFILES["paper"]["fresh_warnings"] is False
    assert PROFILES["illustrative"]["fresh_warnings"] is True
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", fresh_warnings=True, bear_memory=True,
                             quick_warnings=True))


def test_a_warning_carries_only_the_fresh_news_it_answers(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        day = sim.clock.ticks_per_day
        old = raid(sim, [a], 0)
        sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 1)
        sim.clock.tick = 3 * FADE_DAYS["hazard"] * day
        new = raid(sim, [a], sim.clock.tick)
        action = warn(sim, a)
        assert action is not None and action.data["target"] == b.id
        # Not the raid that has faded, and not the sickness at the well.
        assert action.data["news"] == [new.root]
        assert old.root not in action.data["news"]
    finally:
        sim.close()


def test_without_fresh_news_there_is_nothing_to_warn_of(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        raid(sim, [a], 0)
        sim.clock.tick = 3 * FADE_DAYS["hazard"] * sim.clock.ticks_per_day
        assert warn(sim, a) is None
    finally:
        sim.close()


def test_a_listener_once_told_is_not_warned_again(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)
        news = raid(sim, [a], 1)
        sim.clock.tick = 2
        action = warn(sim, a)
        assert action is not None

        heard = asyncio.run(sim.diffuser.tell(a, b, action.data["topic"],
                                              "knows-warn-about-road", action.data["news"]))
        # Only the raid went, not the sickness the warner also holds.
        assert len(heard) == 1
        assert {f.root for f in sim.diffuser.store_for(b.id).facts} == {news.root}
        assert warn(sim, a) is None
    finally:
        sim.close()


def test_a_listener_is_told_as_the_warning_is_given(tmp_path):
    """A decision later in the same tick (config.decide_again) sees the
    listener told, though the offers have not run yet."""
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        news = raid(sim, [a], 0)
        sim.clock.tick = 1
        action = warn(sim, a)

        async def go():
            a.queue.append(sim._activity(action, "knows-warn-about-road"))
            sim._advance(a)
            again = warn(sim, a)          # before any offer has run
            await sim.conversations.wait_generating()
            return again

        assert asyncio.run(go()) is None
        assert news.root in {f.root for f in sim.diffuser.store_for(b.id).facts}
    finally:
        sim.close()


def test_without_the_switch_old_news_still_qualifies(tmp_path):
    sim = make_sim(tmp_path, fresh=False)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        raid(sim, [a], 0)
        sim.clock.tick = 3 * FADE_DAYS["hazard"] * sim.clock.ticks_per_day
        action = warn(sim, a)
        assert action is not None and "news" not in action.data
    finally:
        sim.close()


def test_a_lesson_warns_of_the_news_it_was_written_from(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a = adults(sim, 1)[0]
        news = raid(sim, [a], 0)
        sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 1)

        class Lesson:
            scope = ScopeCondition(required_tags=["daytime"])
            metadata = {"kind": "lesson", "parents": [news.id]}

        assert sim.brain._warn_news(a.id, Lesson, "something you should know") == {news.root}
        Lesson.metadata = {"kind": "lesson"}
        # Resting on no news, the news its topic names.
        assert sim.brain._warn_news(a.id, Lesson, "the trouble on the east road") == {news.root}
    finally:
        sim.close()
