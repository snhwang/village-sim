"""A villager born here is described as it is now (config.grown_personas,
family.persona_now). Written once at birth, a persona said only "a baby,
born to ...", and the live village's grown villagers were told they were
babies every time they spoke (2026-10-02)."""

import json

from hearthwick.__main__ import PROFILES, _saved
from hearthwick.config import SimConfig
from hearthwick.follow import roster
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw))


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def born(sim):
    adults = sorted((c for c in sim.characters.values() if c.stage == "adult"), key=lambda c: c.id)
    mother = next(c for c in adults if c.sex == "female")
    father = next(c for c in adults if c.sex == "male")
    return sim.family.birth(mother, father, 0), mother, father


def test_a_villager_born_here_is_described_as_it_is_now(tmp_path):
    sim = make_sim(tmp_path)
    try:
        child, mother, father = born(sim)
        assert child.persona == f"{child.name} is a baby, born to {mother.name} and {father.name}."
        master = next(c for c in sim.characters.values() if c.role and c.stage == "adult")
        child.stage, child.trade, child.mentor = "apprentice", master.role, master.id
        assert sim.regrow_persona(child)
        kin = f"{'son' if child.sex == 'male' else 'daughter'} of {mother.name} and {father.name}"
        assert child.persona.startswith(f"{child.name} is an apprentice {master.role}, {kin}, "
                                        f"learning the trade from {master.name}.")
        assert sim.corpus.get(f"persona-{child.id}").content == child.persona
        [e] = events(sim, "persona")
        assert e["persona"] == child.persona and e["stage"] == "apprentice"
        child.stage, child.role = "adult", master.role
        sim.regrow_persona(child)
        assert f"is {'an' if master.role[0] in 'aeiou' else 'a'} {master.role} of the village" in child.persona
        assert f"{master.name} taught {child.name} the trade." in child.persona
        assert not sim.regrow_persona(child)                    # nothing has changed
    finally:
        sim.close()


def test_founders_keep_their_personas_and_so_does_a_run_without_the_switch(tmp_path):
    sim = make_sim(tmp_path / "on")
    try:
        founder = next(iter(sim.characters.values()))
        before = founder.persona
        founder.stage = "elder"
        assert not sim.regrow_persona(founder) and founder.persona == before
    finally:
        sim.close()
    sim = make_sim(tmp_path / "off", grown_personas=False)
    try:
        child, _, _ = born(sim)
        child.stage = "child"
        assert not sim.regrow_persona(child) and "is a baby" in child.persona
    finally:
        sim.close()


def test_resume_describes_everyone_born_here_as_they_are(tmp_path):
    sim = make_sim(tmp_path)
    try:
        child, _, _ = born(sim)
        child.stage = "child"
        assert sim.refresh_personas() == 1
        assert "is a child of the village" in child.persona and "goes to school" in child.persona
    finally:
        sim.close()


def test_a_viewer_arriving_later_sees_who_a_villager_is_now(tmp_path):
    sim = make_sim(tmp_path)
    try:
        child, _, _ = born(sim)
        child.stage = "child"
        sim.regrow_persona(child)
        sim.log.flush()
        [seen] = [p for p in roster(sim.log.dir) if p["id"] == child.id]
        assert seen["persona"] == child.persona and seen["stage"] == "child"
    finally:
        sim.close()


def test_old_runs_and_the_paper_keep_the_personas_they_were_born_with(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({"config": {"seed": 3, "village": "greater"}}))
    config = SimConfig(runs_dir=tmp_path)
    assert _saved(config, "old-run")[0].grown_personas is False
    assert _saved(config, "old-run", ["grown_personas"])[0].grown_personas is True
    assert PROFILES["paper"]["grown_personas"] is False
