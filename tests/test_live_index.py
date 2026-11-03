"""What leaves the live memory index (config.forget_the_dead,
config.forget_faded, SPECIFICATION-memory.md section 7), and telling only
what the listener has not had (config.novel_telling, section 8). Skipped on a
BEAR without items and the importance floor."""

import asyncio

import numpy as np
import pytest

items = pytest.importorskip("bear.items")
if not hasattr(items, "set_importance"):
    pytest.skip("this BEAR predates the importance floor", allow_module_level=True)

from hearthwick import embedder as embedder_module  # noqa: E402
from hearthwick.__main__ import ADDABLE, PROFILES  # noqa: E402
from hearthwick.config import SimConfig  # noqa: E402
from hearthwick.markers import MarkerContext, build_registry  # noqa: E402
from hearthwick.memory import FADE_DAYS, FORGET_BELOW  # noqa: E402
from hearthwick.sim import Simulation  # noqa: E402

SWITCHES = ("forget_the_dead", "forget_faded", "novel_telling")


def make_sim(tmp_path, **switches):
    switches = {"bear_memory": True, "short_warnings": True, "afar_news": True, **switches}
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def adults(sim, n):
    return [c for c in sim.characters.values()
            if c.alive and not c.visitor and c.stage in ("adult", "elder")][:n]


def live(sim):
    return {i.id for i in sim.diffuser.memory.retriever.corpus}


def test_off_unless_asked_for_and_only_with_what_they_need(tmp_path):
    config = SimConfig()
    for name in SWITCHES:
        assert getattr(config, name) is False
        assert PROFILES["paper"][name] is False
        assert name in ADDABLE
    for name in ("forget_the_dead", "forget_faded"):
        with pytest.raises(ValueError):
            Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                                 runs_dir=tmp_path / name, embedder="bm25", **{name: True}))
    with pytest.raises(ValueError):
        Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                             runs_dir=tmp_path / "novel", embedder="bm25", novel_telling=True))


def test_a_faded_memory_leaves_the_index_and_comes_back_when_lived_again(tmp_path):
    sim = make_sim(tmp_path, forget_faded=True)
    try:
        a = adults(sim, 1)[0]
        raid = sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)[0]
        day = sim.clock.ticks_per_day
        span = FADE_DAYS["hazard"] * day
        memory = sim.diffuser.memory
        assert raid.id in live(sim)
        # Just above a twentieth of its strength it stays, just below it goes.
        edge = int(span * np.log2(1 / FORGET_BELOW))
        assert memory.prune(edge - 1) == 0 and raid.id in live(sim)
        assert memory.prune(edge + 1) == 1 and raid.id not in live(sim)
        store = sim.diffuser.store_for(a.id)
        assert any(f.id == raid.id for f in store.facts)       # its own record stays
        assert raid.id not in memory.recall(a.id, "raiders on the east road", 5)
        store.reinforce(raid, refreshed=edge + 2)              # lived again
        assert raid.id in live(sim) and raid.id not in memory.dropped
        assert memory.prune(edge + 3) == 0                     # its clock started again
    finally:
        sim.close()


def test_what_never_fades_never_leaves(tmp_path):
    sim = make_sim(tmp_path, forget_faded=True)
    try:
        a, b = adults(sim, 2)
        met = [f for f in sim.diffuser.store_for(a.id).facts if f.kind == "met"]
        festival = sim.diffuser.witness("festival", "inn", [a.id], {"place": "inn"}, 0)
        assert sim.diffuser.memory.prune(10 ** 7) >= 0
        kept = live(sim)
        assert all(f.id in kept for f in met)
        assert all(f.id in kept for f in festival
                   if sim.diffuser.memory.half_life_of(f.kind, a.id, f.tags) is None)
    finally:
        sim.close()


def test_the_dead_leave_the_index_and_others_memories_of_them_stay(tmp_path):
    sim = make_sim(tmp_path, forget_the_dead=True)
    try:
        a, b = adults(sim, 2)
        mine = sim.diffuser.witness("raid", "east_road", [a.id, b.id], {"place": "east_road"}, 0)
        theirs = [f for f in mine if f.holder == b.id]
        ours = [f for f in mine if f.holder == a.id]
        b.alive = False
        sim.diffuser.memory.prune(1)
        kept = live(sim)
        assert theirs and all(f.id not in kept for f in theirs)
        assert ours and all(f.id in kept for f in ours)
    finally:
        sim.close()


def test_a_resumed_run_leaves_out_what_had_left(tmp_path):
    sim = make_sim(tmp_path / "first", forget_faded=True)
    try:
        a = adults(sim, 1)[0]
        raid = sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)[0]
        sim.clock.tick = 40 * sim.clock.ticks_per_day
        sim.diffuser.memory.prune(sim.clock.tick)
        assert raid.id not in live(sim)
        path = asyncio.run(sim.save())
    finally:
        sim.close()
    resumed = make_sim(tmp_path / "again", forget_faded=True)
    try:
        resumed.resume_from(path)
        assert raid.id not in live(resumed)
        assert any(f.id == raid.id for f in resumed.diffuser.store_for(a.id).facts)
    finally:
        resumed.close()


def test_the_embedder_keeps_documents_for_good(monkeypatch):
    calls = []

    def post(self, texts, is_query):
        calls.append(list(texts))
        return np.ones((len(texts), 4), dtype=np.float32)

    monkeypatch.setattr(embedder_module, "CACHE_SIZE", 2)
    monkeypatch.setattr(embedder_module.ServiceEmbedder, "_post", post)
    e = embedder_module.ServiceEmbedder("http://nowhere")
    e.dim = 4
    e.keep_documents = True
    e.embed(["a", "b", "c", "d"])
    e.embed(["a", "b", "c", "d"])
    assert len(calls) == 1                       # all four read back, none sent again
    e.embed(["q1", "q2", "q3"], is_query=True)
    e.embed(["q1"], is_query=True)
    assert calls[-1] == ["q1"]                   # queries keep to the small cache


def talk_target(sim, a, topic):
    ctx = MarkerContext(sim.world, sim.clock, a, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        known_to=sim.diffuser.known_to,
                        novel_telling=sim.config.novel_telling)
    actions = build_registry().process(
        f"Tell them. [!talk(target=nearby, topic={topic})]", context=ctx)[1]
    return actions[0].data["target"] if actions else None


def alone_with(sim, a, b):
    for other in sim.characters.values():
        if other.id != a.id:
            other.pos = (a.pos[0] + 40, a.pos[1] + 40)
    b.pos = (a.pos[0] + 1, a.pos[1])


def test_telling_news_goes_only_to_who_has_not_had_it(tmp_path):
    sim = make_sim(tmp_path, told_memory=True, novel_telling=True)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        sick = sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)[0]
        assert talk_target(sim, a, "the sickness at the well") == b.id
        sim.diffuser._note_told(a.id, b.id, sick.root)
        assert talk_target(sim, a, "the sickness at the well") is None    # b has had it
        assert talk_target(sim, a, "the weather") == b.id                  # talk, not telling
    finally:
        sim.close()


def test_without_the_switch_telling_is_as_before(tmp_path):
    sim = make_sim(tmp_path, told_memory=True)
    try:
        a, b = adults(sim, 2)
        alone_with(sim, a, b)
        sick = sim.diffuser.witness("sicken", "well", [a.id], {"place": "well"}, 0)[0]
        sim.diffuser._note_told(a.id, b.id, sick.root)
        assert talk_target(sim, a, "the sickness at the well") == b.id
    finally:
        sim.close()


def test_a_new_day_lets_go_of_bears_change_records(tmp_path):
    """BEAR keeps every change to its items for its audit, which only the
    audit takes, and nothing here audits: a day's start lets them go."""
    sim = make_sim(tmp_path, fading_lessons=True)
    try:
        a = adults(sim, 1)[0]
        sim.diffuser.witness("raid", "east_road", [a.id], {"place": "east_road"}, 0)
        memory = sim.diffuser.memory.retriever
        assert memory._item_deltas
        sim.clock.tick = sim.clock.ticks_per_day
        sim._physics()
        assert memory._item_deltas == [] and sim.retriever._item_deltas == []
    finally:
        sim.close()
