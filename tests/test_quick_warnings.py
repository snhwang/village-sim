"""A warning is a word to someone within reach, passed on in one tick, with no
walk and no conversation (config.quick_warnings, SPECIFICATION-warnings.md
section 8)."""

import asyncio
import json

from bear import MarkerAction

from hearthwick.__main__ import PROFILES
from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path, quick=True):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0,
                                quick_warnings=quick))


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


def warn_target(sim, a, target="nearby"):
    ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        quick_warnings=sim.config.quick_warnings)
    actions = build_registry().process(
        f"Warn them. [!warn(target={target}, topic=the raiders on the east road)]", context=ctx)[1]
    return actions[0].data["target"] if actions else None


def test_off_unless_asked_for():
    assert SimConfig().quick_warnings is False
    assert PROFILES["paper"]["quick_warnings"] is False


def test_only_someone_within_reach_is_warned(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, near, far = adults(sim, 3)
        alone_with(sim, a, near)
        far.pos = (a.pos[0] + sim.config.near_radius + 5, a.pos[1])
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)
        assert warn_target(sim, a, far.id) is None          # by name, but out of reach
        assert warn_target(sim, a, near.id) == near.id
        assert warn_target(sim, a) == near.id
    finally:
        sim.close()


def test_without_the_switch_a_named_villager_far_away_can_still_be_warned(tmp_path):
    sim = make_sim(tmp_path, quick=False)
    try:
        a, near, far = adults(sim, 3)
        alone_with(sim, a, near)
        far.pos = (a.pos[0] + sim.config.near_radius + 5, a.pos[1])
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)
        assert warn_target(sim, a, far.id) == far.id
    finally:
        sim.close()


def test_the_news_passes_in_one_tick_and_nobody_stops(tmp_path):
    sim = make_sim(tmp_path)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        raid = sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)[0]
        action = MarkerAction("warn", {"target": b.id, "topic": "the raiders"}, None)

        async def go():
            a.queue.append(sim._activity(action, "knows-warn-about-road"))
            sim._advance(a)
            await sim.conversations.wait_generating()

        asyncio.run(go())
        assert a.activity is None and a.conversation_id is None
        assert b.conversation_id is None
        assert raid.root in {f.root for f in sim.diffuser.store_for(b.id).facts}
        sim.log.flush()
        kinds = [json.loads(line)["type"] for line in open(sim.log.dir / "events.jsonl",
                                                            encoding="utf-8")]
        assert "warned" in kinds and "conversation_start" not in kinds
    finally:
        sim.close()
