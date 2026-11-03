import json
import random

import pytest
from bear import parse_actions

from hearthwick.config import DATA_DIR, SimConfig
from hearthwick.markers import MarkerContext, build_registry, resolve_place, resolve_target
from hearthwick.sim import Simulation
from hearthwick.world import Clock, World


@pytest.fixture
def world():
    return World.from_yaml(DATA_DIR / "world" / "village.yaml")


def make_sim(tmp_path, seed=0):
    """Hermetic: BM25, no speech model, no embedding service."""
    return Simulation(SimConfig(seed=seed, llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0))


def test_path_crosses_stream_only_at_bridge_or_ford(world):
    path = world.path((20, 5), (35, 5))
    assert path, "the forest edge must be reachable"
    crossings = [t for t in path if t[0] in (26, 27)]
    assert crossings and all(t[1] in (14, 15, 25) for t in crossings)


def test_clock_parts_and_wake():
    clock = Clock(minutes_per_tick=10, start_hour=6)
    assert clock.part_of_day == "morning"
    clock.tick = 15 * 6  # 21:00
    assert clock.part_of_day == "night"
    assert clock.ticks_until_hour(6) == 9 * 6


def test_each_vocabulary_stays_on_its_own_side(tmp_path):
    """Villagers and the world have separate marker vocabularies."""
    from hearthwick.markers import build_world_registry

    sim = make_sim(tmp_path)
    villager_markers = build_registry().known_names()
    world_markers = build_world_registry().known_names()
    assert not (villager_markers & world_markers)

    for inst in sim.corpus:
        names = {m.name for m in parse_actions(inst.content)}
        if not names:
            continue
        expected = world_markers if "world" in inst.scope.required_tags else villager_markers
        unknown = names - expected
        assert not unknown, f"{inst.id} uses {unknown}, which nothing can dispatch"
    sim.close()


def test_symbolic_places_and_targets_resolve(tmp_path):
    sim = make_sim(tmp_path)
    chars = sim.characters
    ctx = lambda cid: MarkerContext(sim.world, sim.clock, chars[cid], chars, random.Random(0), 4)
    assert resolve_place("home", ctx("pip")) == "home_rosa"
    assert resolve_place("own", ctx("pip")) is None          # children have no workplace
    assert resolve_place("mentor", ctx("lise")) == "shrine"  # Hilde is a healer
    assert resolve_place("own", ctx("garrick")) == "watchpost"
    chars["rosa"].pos = chars["pip"].pos
    assert resolve_target("parent", ctx("pip")) in ("rosa", "tobin")


def test_night_everyone_sleeps_at_home(tmp_path):
    sim = make_sim(tmp_path)
    import asyncio
    asyncio.run(sim.run(sim.clock.ticks_per_day + 20 * 6))  # through to 02:00 on day 1
    sim.close()
    assert sim.clock.part_of_day == "night"
    for c in sim.characters.values():
        assert c.resting, f"{c.id} is {c.activity_label} at night"
        assert sim.world.places[c.home].contains(*c.pos), f"{c.id} is not home"


def test_runs_are_deterministic_without_llm(tmp_path):
    import asyncio

    def frames(seed):
        sim = make_sim(tmp_path / str(seed) / str(random.random()), seed)
        asyncio.run(sim.run(sim.clock.ticks_per_day))
        sim.close()
        return (sim.log.dir / "frames.jsonl").read_text(encoding="utf-8")

    assert frames(3) == frames(3)
    assert frames(3) != frames(4)


def test_event_log_is_valid_jsonl(tmp_path):
    import asyncio
    sim = make_sim(tmp_path)
    asyncio.run(sim.run(60))
    sim.close()
    events = [json.loads(l) for l in (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[0]["type"] == "roster"
    decisions = [e for e in events if e["type"] == "decision"]
    assert decisions and all(d["chosen"] for d in decisions)
