"""Word of danger abroad fades from when it reached the village, not from when
each villager heard it, and is a false alarm unless the danger came within the
week (config.far_danger_dated, SPECIFICATION-warnings.md section 14). Skipped
on a BEAR without items and the importance floor."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from hearthwick.__main__ import PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.memory import FADE_DAYS  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402

COMING = "knows_danger_coming"


def make_sim(tmp_path, dated=True, **switches):
    switches = {"bear_memory": True, "short_warnings": True, "afar_news": True,
                "far_danger_dated": dated, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adults(sim, n):
    return [c for c in sim.characters.values()
            if c.alive and not c.visitor and c.stage in ("adult", "elder")][:n]


def tale(sim, who, topic, tick=0):
    return sim.diffuser.witness("tale", "east_road", [who.id], {"topic": topic}, tick,
                                root=f"tale:east_road:{tick}-{topic[:8]}")[0]


def heard_later(sim, teller, listener, fact, tick):
    """``listener`` hears ``fact`` from ``teller`` at ``tick``."""
    sim.clock.tick = tick
    asyncio.run(sim.diffuser.offer(fact, teller, listener))


def tags(sim, who, now):
    return sim.diffuser.store_for(who.id).tags(now=now, fade={"hazard": 1})


def test_off_unless_asked_for_and_only_with_short_warnings(tmp_path):
    assert SimConfig().far_danger_dated is False
    assert PROFILES["paper"]["far_danger_dated"] is False
    assert PROFILES["illustrative"]["far_danger_dated"] is True
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", far_danger_dated=True, bear_memory=True))


def test_an_old_tale_heard_late_does_not_warn(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        day = sim.clock.ticks_per_day
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        late = 4 * FADE_DAYS["hazard"] * day
        heard_later(sim, a, b, raiders, late)
        assert any(f.root == raiders.root for f in sim.diffuser.store_for(b.id).facts)
        assert COMING not in tags(sim, b, late)
    finally:
        sim.close()


def test_without_the_switch_the_same_tale_warns_again(tmp_path):
    sim = make_sim(tmp_path, dated=False)
    try:
        a, b = adults(sim, 2)
        day = sim.clock.ticks_per_day
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        late = 4 * FADE_DAYS["hazard"] * day
        heard_later(sim, a, b, raiders, late)
        assert COMING in tags(sim, b, late)
    finally:
        sim.close()


def test_a_tale_heard_within_its_week_still_warns(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        day = sim.clock.ticks_per_day
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        heard_later(sim, a, b, raiders, 2 * day)
        assert COMING in tags(sim, b, 2 * day)
        assert COMING not in tags(sim, b, (FADE_DAYS["hazard"] + 1) * day)
    finally:
        sim.close()


def test_the_tale_told_again_is_fresh_again(tmp_path):
    """A storyteller who brings the same word again lives it again, so its
    clock restarts from the new telling."""
    sim = make_sim(tmp_path)
    try:
        a = adults(sim, 1)[0]
        day = sim.clock.ticks_per_day
        tale(sim, a, "that there has been fighting beyond the forest")
        later = 4 * FADE_DAYS["hazard"] * day
        assert COMING not in tags(sim, a, later)
        tale(sim, a, "that there has been fighting beyond the forest", tick=later)
        assert COMING in tags(sim, a, later + 1)
    finally:
        sim.close()


def test_word_renewed_by_the_storyteller_is_fresh_for_its_hearers(tmp_path):
    """The storyteller living the word again renews it, and so does every
    copy told on from it, while one told before the renewal stays old."""
    sim = make_sim(tmp_path)
    try:
        a, b, c = adults(sim, 3)
        day = sim.clock.ticks_per_day
        word = tale(sim, a, "that there has been fighting beyond the forest")
        heard_later(sim, a, b, word, 1 * day)
        later = 4 * FADE_DAYS["hazard"] * day
        sim.diffuser.store_for(a.id).reinforce(word, refreshed=later)   # told again
        heard_later(sim, a, c, word, later + 1)
        assert COMING in tags(sim, c, later + 1)
        assert COMING not in tags(sim, b, later + 1)
    finally:
        sim.close()


def test_a_raid_long_after_does_not_bear_out_an_old_tale(tmp_path):
    sim = make_sim(tmp_path, false_alarms=True)
    try:
        a = adults(sim, 1)[0]
        day = sim.clock.ticks_per_day
        old = tale(sim, a, "that there has been fighting beyond the forest")
        # A raid a month on, long after the word's week.
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 30 * day)
        sim.diffuser.memory.false_alarms(31 * day)
        assert old.id in sim.diffuser.memory.marked_down
    finally:
        sim.close()


def test_a_raid_within_the_week_bears_the_tale_out(tmp_path):
    sim = make_sim(tmp_path, false_alarms=True)
    try:
        a = adults(sim, 1)[0]
        day = sim.clock.ticks_per_day
        word = tale(sim, a, "that there has been fighting beyond the forest")
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 3 * day)
        sim.diffuser.memory.false_alarms(10 * day)
        assert word.id not in sim.diffuser.memory.marked_down
    finally:
        sim.close()


def test_without_the_switch_any_later_raid_bears_it_out(tmp_path):
    sim = make_sim(tmp_path, dated=False, false_alarms=True)
    try:
        a = adults(sim, 1)[0]
        day = sim.clock.ticks_per_day
        old = tale(sim, a, "that there has been fighting beyond the forest")
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 30 * day)
        sim.diffuser.memory.false_alarms(31 * day)
        assert old.id not in sim.diffuser.memory.marked_down
    finally:
        sim.close()
