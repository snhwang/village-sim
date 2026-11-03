"""What news makes a villager do fades in days, and far-off news warns only of
a danger that can come here (config.short_warnings, SPECIFICATION-warnings.md
section 10). Both are properties of the news as fading BEAR items. Skipped on
a BEAR without items and the importance floor."""

import asyncio

import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from hearthwick.__main__ import PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.knowledge import CAN_COME, can_come  # noqa: E402
from hearthwick.memory import FADE_DAYS  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "short_warnings": True, "afar_news": True, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adults(sim, n):
    return [c for c in sim.characters.values()
            if c.alive and not c.visitor and c.stage in ("adult", "elder")][:n]


def tale(sim, who, topic, tick=0):
    return sim.diffuser.witness("tale", "east_road", [who.id], {"topic": topic}, tick,
                                root=f"tale:east_road:{tick}-{topic[:8]}")[0]


def test_off_unless_asked_for_and_only_with_bear_memory(tmp_path):
    assert SimConfig().short_warnings is False
    assert PROFILES["paper"]["short_warnings"] is False
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", short_warnings=True))


def test_which_far_off_news_can_come_here():
    assert can_come("that there has been fighting beyond the forest")
    assert can_come("that a sickness is going round two valleys over")
    assert can_come("that wolves have been seen at the edge of the high pastures")
    assert not can_come("that there is to be a fair beyond the forest")
    assert not can_come("that the low road is washed out at the ford")
    assert not can_come("that grain is dear in the market towns this year")


def test_far_off_danger_that_can_come_warns_and_the_rest_does_not(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a = adults(sim, 1)[0]
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        fair = tale(sim, a, "that there is to be a fair beyond the forest", tick=1)
        assert CAN_COME in raiders.tags and CAN_COME not in fair.tags
        tags = sim.diffuser.store_for(a.id).tags(now=2, fade={"hazard": 1})
        assert "knows_danger_coming" in tags
        assert "knows_hazard_east_road" not in tags and "knows_news_east_road" not in tags
        assert sim.corpus.get("coming-pass-the-word") is not None
    finally:
        sim.close()


def test_the_danger_passes_on_as_one_that_can_come(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        asyncio.run(sim.diffuser.offer(raiders, a, b))
        heard = [f for f in sim.diffuser.store_for(b.id).facts if f.root == raiders.root]
        assert heard and CAN_COME in heard[0].tags
    finally:
        sim.close()


def test_a_warning_lasts_days_not_years(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a = adults(sim, 1)[0]
        day = sim.clock.ticks_per_day
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        item = sim.diffuser.memory.retriever.corpus.get(raiders.id)
        assert item.metadata["half_life"] == FADE_DAYS["hazard"] * day   # a danger's span
        store = sim.diffuser.store_for(a.id)
        assert "knows_danger_coming" in store.tags(now=FADE_DAYS["hazard"] * day, fade={})
        assert "knows_danger_coming" in store.tags(now=FADE_DAYS["hazard"] * day,
                                                   fade={"hazard": 1})
        assert "knows_danger_coming" not in store.tags(now=FADE_DAYS["hazard"] * day + 1,
                                                       fade={"hazard": 1})
    finally:
        sim.close()


def test_without_the_switch_nothing_is_tagged(tmp_path):
    sim = Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0, afar_news=True))
    try:
        a = adults(sim, 1)[0]
        raiders = tale(sim, a, "that there has been fighting beyond the forest")
        assert CAN_COME not in raiders.tags
        assert sim.corpus.get("coming-pass-the-word") is None
    finally:
        sim.close()
