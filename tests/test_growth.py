"""Growing up: what counts, what does not, and why someone stays put.

The rule the project committed to is no forced promotion. A villager advances
only by meeting every requirement, and one that reaches the age without the
rest stays where it is and can die there. That makes the interesting assertions
negative ones: what must *not* advance a villager.
"""

import pytest

from hearthwick.growth import GATES, TICKS_PER_LEVEL, Growth, check


def grown(roots=0, lived=None, practice=None) -> Growth:
    g = Growth()
    for i in range(roots):
        g.learned(f"event:{i}")
    for kind, times in (lived or {}).items():
        for _ in range(times):
            g.lived_through(kind)
    for site, ticks in (practice or {}).items():
        g.practised(site, ticks)
    return g


# --- knowledge counts events, not sentences -------------------------------

def test_hearing_the_same_thing_twice_is_one_thing_known():
    g = Growth()
    g.learned("sicken:well:100")
    g.learned("sicken:well:100")
    assert g.knowledge == 1

    g.learned("raid:east_road:200")
    assert g.knowledge == 2


# --- experience resists grinding ------------------------------------------

def test_doing_one_thing_harder_does_not_make_a_villager_experienced():
    """Ten of the same kind must be worth far less than ten kinds."""
    same = grown(lived={"news": 10})
    varied = grown(lived={k: 1 for k in
                          ("news", "hazard", "sickness", "met", "did")})
    assert varied.experience > same.experience


def test_the_first_of_a_kind_counts_fully():
    assert grown(lived={"hazard": 1}).experience == 1
    assert grown(lived={"hazard": 1, "news": 1}).experience == 2


# --- skill is practised, not granted --------------------------------------

def test_skill_rises_with_practice_and_stops_at_the_cap():
    assert grown(practice={"fields": TICKS_PER_LEVEL - 1}).best_skill == 0
    assert grown(practice={"fields": TICKS_PER_LEVEL}).best_skill == 1
    assert grown(practice={"fields": TICKS_PER_LEVEL * 3}).best_skill == 3
    assert grown(practice={"fields": TICKS_PER_LEVEL * 99}).best_skill == 5


def test_practice_is_per_place():
    g = grown(practice={"fields": TICKS_PER_LEVEL, "mill": TICKS_PER_LEVEL * 2})
    assert g.skills == {"fields": 1, "mill": 2}
    assert g.best_skill == 2


# --- the gates ------------------------------------------------------------

def schooled(**kw) -> Growth:
    """A child with the schooling to graduate."""
    g = grown(**kw)
    g.practised("schoolyard", TICKS_PER_LEVEL * GATES["child"].school)
    return g


def test_a_villager_that_meets_everything_advances():
    gate = GATES["child"]
    ready = schooled(roots=gate.knowledge,
                     lived={f"k{i}": 1 for i in range(gate.experience)})
    nxt, missing = check("child", ready, age=gate.min_age)
    assert nxt == "apprentice" and missing == []


def test_age_alone_does_not_promote_anyone():
    """The rule in one assertion: old enough is not the same as ready."""
    nxt, missing = check("child", Growth(), age=99.0)
    assert nxt is None
    assert any("knowledge" in m for m in missing)
    assert not any(m.startswith("age") for m in missing)


def test_everything_but_age_does_not_promote_anyone_either():
    gate = GATES["child"]
    ready = schooled(roots=gate.knowledge,
                     lived={f"k{i}": 1 for i in range(gate.experience)})
    nxt, missing = check("child", ready, age=gate.min_age - 0.1)
    assert nxt is None and missing == [f"age {gate.min_age - 0.1:.1f} of {gate.min_age}"]


def test_a_missing_skill_holds_an_apprentice_back():
    """The skill has to be in the apprentice's own trade."""
    gate = GATES["apprentice"]
    almost = grown(roots=gate.knowledge,
                   lived={f"k{i}": 1 for i in range(gate.experience)})
    nxt, missing = check("apprentice", almost, age=gate.min_age, site="fields")
    assert nxt is None and any("skill" in m for m in missing)

    almost.practised("mill", TICKS_PER_LEVEL * gate.trade_skill)
    nxt, missing = check("apprentice", almost, age=gate.min_age, site="fields")
    assert nxt is None, "skill at another trade's place qualified it"

    almost.practised("fields", TICKS_PER_LEVEL * gate.trade_skill)
    nxt, missing = check("apprentice", almost, age=gate.min_age, site="fields")
    assert nxt == "adult" and missing == []


def test_a_child_does_not_graduate_without_school():
    gate = GATES["child"]
    ready = grown(roots=gate.knowledge, lived={f"k{i}": 1 for i in range(gate.experience)})
    nxt, missing = check("child", ready, age=gate.min_age)
    assert nxt is None and missing == [f"school 0 of {gate.school}"]


def test_an_elder_has_nowhere_further_to_go():
    """No gate, and so no reason recorded -- an elder is not held back."""
    nxt, missing = check("elder", grown(roots=99), age=80.0)
    assert nxt is None and missing == []


def test_the_reason_names_every_track_that_falls_short():
    """A villager who never grows up must be answerable for why."""
    nxt, missing = check("apprentice", Growth(), age=0.0)
    assert nxt is None
    assert len(missing) == 4
    assert {m.split()[0].rstrip(":") for m in missing} == {"age", "knowledge", "experience",
                                                          "skill"}


@pytest.mark.parametrize("stage", ("child", "apprentice", "adult"))
def test_every_stage_but_the_last_has_a_way_forward(stage):
    assert stage in GATES and GATES[stage].to in ("apprentice", "adult", "elder")


# --- the wiring, not just the arithmetic ----------------------------------

def test_a_villager_with_enough_actually_advances_in_a_run(tmp_path):
    """The gate logic is tested above; this tests that the simulation uses it.

    A short run cannot reach the thresholds honestly -- twelve days produce
    about ten world events and a villager learns one or two -- so the growth is
    granted directly and the run is asked only whether it notices.
    """
    import asyncio
    import json

    from hearthwick.config import SimConfig
    from hearthwick.sim import Simulation

    sim = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0,
                               growth=True))
    try:
        child = next(c for c in sim.characters.values() if c.stage == "child")
        gate = GATES["child"]
        child.age = gate.min_age + 1
        for i in range(gate.knowledge):
            child.growth.learned(f"event:{i}")
        for i in range(gate.experience):
            child.growth.lived_through(f"kind{i}")
        child.growth.practised("schoolyard", TICKS_PER_LEVEL * gate.school)

        stuck = next(c for c in sim.characters.values()
                     if c.stage == "child" and c.id != child.id)
        stuck.age = gate.min_age + 1          # old enough, and nothing else

        asyncio.run(sim.run(sim.clock.ticks_per_day + 1))
        sim.close()

        assert child.stage == "apprentice", "a villager that met every gate stayed put"
        assert stuck.stage == "child", "age alone promoted somebody"

        events = [json.loads(line) for line
                  in (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        changes = [e for e in events if e["type"] == "stage_change"]
        assert any(e["character"] == child.id and e["now"] == "apprentice"
                   for e in changes)

        held = [e for e in events if e["type"] == "growth_held_back"
                and e["character"] == stuck.id]
        assert held, "a villager held back left no record of why"
        assert any("knowledge" in m for m in held[0]["missing"])
    finally:
        if sim.log.dir.exists():
            sim.close()


def test_advancement_changes_which_instructions_are_reachable(tmp_path):
    """Advancing is a tag swap, and the tag swap is the whole mechanism."""
    from hearthwick.config import SimConfig
    from hearthwick.sim import Simulation

    sim = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0))
    try:
        child = next(c for c in sim.characters.values() if c.stage == "child")
        before = set(sim.brain.context_tags(child, sim.characters))
        child.stage = "apprentice"
        after = set(sim.brain.context_tags(child, sim.characters))
        assert "stage_child" in before and "stage_child" not in after
        assert "stage_apprentice" in after
    finally:
        sim.close()
