"""Couples have a child when they can support one (hearthwick/family.py)."""

import asyncio
import json

import pytest
from bear import Context

from hearthwick import family
from hearthwick.character import Activity
from hearthwick.config import SimConfig
from hearthwick.growth import GATES
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path, **kw):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **kw))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def couple(sim):
    """A couple of age, both put at home."""
    for c in sorted(sim.characters.values(), key=lambda c: c.id):
        p = family.partner_of(c, sim.characters)
        if p and family.fertile(c) and family.fertile(p) and c.sex == "female":
            home = sim.world.places[c.home].tiles()
            c.pos, p.pos = home[0], home[1]
            # room in the house, whatever the founders' households hold
            for o in family.young_at_home(c.home, sim.characters):
                o.home = "home_1" if c.home != "home_1" else "home_2"
            return c, p
    raise AssertionError("no couple of age in the greater village")


def resolve(sim, who, food_low=False):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots, food_low=food_low)
    return build_registry().process("[!have_child]", context=ctx)[1]


def events(sim):
    sim.log.flush()
    return [json.loads(line) for line in open(sim.log.dir / "events.jsonl", encoding="utf-8")]


def test_a_couple_at_home_sees_a_family_is_possible(sim):
    mother, father = couple(sim)
    tags = sim.brain.context_tags(mother, sim.characters)
    assert "fertile" in tags and "partner_home" in tags
    father.pos = sim.world.places["market"].tiles()[0]
    assert "partner_home" not in sim.brain.context_tags(mother, sim.characters)


def test_only_a_couple_who_can_support_a_child_has_one(sim):
    mother, father = couple(sim)
    assert resolve(sim, mother), "a couple of age at home with room should be able to"
    assert resolve(sim, mother, food_low=True) == []            # the granary is low
    father.pos = sim.world.places["market"].tiles()[0]
    assert resolve(sim, mother) == []                           # not home together
    father.pos = sim.world.places[father.home].tiles()[1]
    old = father.age
    father.age = family.FERTILE_AGES[1] + 1
    assert resolve(sim, mother) == []                           # past the age
    father.age = old
    solo = next(c for c in sim.characters.values() if not c.partner and c.stage == "adult")
    assert resolve(sim, solo) == []                             # no partner


def test_the_house_fills_and_children_are_spaced(sim):
    mother, father = couple(sim)
    first = sim.family.birth(mother, father, sim.clock.tick)
    assert resolve(sim, mother) == [], "a second child the same day"
    first.age = family.BIRTH_SPACING_YEARS
    assert resolve(sim, mother)
    while len(family.young_at_home(mother.home, sim.characters)) < family.MAX_YOUNG:
        extra = sim.family.birth(mother, father, sim.clock.tick)
        extra.age = family.BIRTH_SPACING_YEARS
    assert resolve(sim, mother) == [], "the house is full"


def test_a_child_takes_one_copy_of_each_gene_from_each_parent(sim):
    mother, father = couple(sim)
    child = sim.family.birth(mother, father, sim.clock.tick)
    assert child.stage == "infant" and child.age == 0 and child.home == mother.home
    assert child.parents == [mother.id, father.id]
    for locus, (a, b) in child.genotype.items():
        assert a in mother.genotype[locus] and b in father.genotype[locus], locus
    assert sim.corpus.get(f"persona-{child.id}") is not None
    kinds = [e["type"] for e in events(sim)]
    assert "born" in kinds and "roster" in kinds
    # whoever was home witnessed it, and it can be told
    assert any(f.root.startswith("birth:") for f in sim.diffuser.store_for(mother.id).facts)


def test_a_baby_is_not_told_news_or_counted_a_witness(sim):
    mother, father = couple(sim)
    baby = sim.family.birth(mother, father, sim.clock.tick)
    ctx = MarkerContext(sim.world, sim.clock, mother, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius)
    far = sim.world.places["forest_edge"].tiles()[0]
    for o in sim.characters.values():                           # only the baby is near
        if o.id not in (mother.id, baby.id):
            o.pos = far
    assert build_registry().process("[!talk(target=nearby)]", context=ctx)[1] == []
    assert baby.id not in sim._nearest_witnesses(mother.home, cap=30)


def test_an_infant_becomes_a_child_at_two_without_writing_anything(tmp_path):
    sim = make_sim(tmp_path)
    try:
        mother, father = couple(sim)
        baby = sim.family.birth(mother, father, sim.clock.tick)
        baby.age = GATES["infant"].min_age
        before = len(sim.corpus)
        sim._grow()
        asyncio.run(sim._consolidate_advanced())
        assert baby.stage == "child" and len(sim.corpus) == before
    finally:
        sim.close()


def test_a_couple_can_retrieve_the_decision(sim):
    mother, father = couple(sim)
    sim.clock.tick = (19 - sim.clock.start_hour) * 6          # an evening
    tags = sim.brain.context_tags(mother, sim.characters)
    ids = [s.id for s in sim.retriever.retrieve("home together in the evening",
                                                 Context(tags=tags), top_k=200)]
    assert "family-have-child" in ids


def test_a_child_born_here_survives_a_checkpoint(sim, tmp_path):
    mother, father = couple(sim)
    baby = sim.family.birth(mother, father, sim.clock.tick)
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        back = resumed.characters[baby.id]
        assert back.stage == "infant" and back.parents == baby.parents
        assert back.genotype == baby.genotype and back.temperament == baby.temperament
        assert resumed.family.born == 1
        assert resumed.corpus.get(f"persona-{baby.id}") is not None
    finally:
        resumed.close()


def test_a_resume_rebuilds_the_index_once_however_many_were_born(sim, tmp_path):
    """Rebuilt after each child, the live village took six minutes to come
    back with 132 villagers through the embedding service."""
    mother, father = couple(sim)
    babies = [sim.family.birth(mother, father, sim.clock.tick + i) for i in range(3)]
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    builds = []
    real = resumed.retriever.build_index
    resumed.retriever.build_index = lambda *a, **k: (builds.append(1), real(*a, **k))[1]
    try:
        resumed.resume_from(path)
        assert len(builds) == 1
        assert all(resumed.corpus.get(f"persona-{b.id}") is not None for b in babies)
        persona = resumed.corpus.get(f"persona-{babies[2].id}")
        ids = [s.id for s in resumed.retriever.retrieve(persona.content,
                                                         Context(tags=persona.scope.required_tags),
                                                         top_k=500)]
        assert persona.id in ids                                   # and it is in the index
    finally:
        resumed.close()


def test_a_couple_tries_once_a_day_and_both_deciding_gives_one_child(sim):
    """Both partners can decide in the same tick, before either acts. Without a
    check at the moment of acting, couples had twins every time."""
    mother, father = couple(sim)
    import hearthwick.family as fam
    old = fam.CONCEPTION_CHANCE
    fam.CONCEPTION_CHANCE = 1.0
    try:
        for who in (mother, father):
            for a in resolve(sim, who):
                who.activity = None
                who.queue.append(sim._activity(a, "family-have-child"))
        sim._advance(mother)
        sim._advance(father)
    finally:
        fam.CONCEPTION_CHANCE = old
    born = [c for c in sim.characters.values() if mother.id in c.parents and c.stage == "infant"]
    assert len(born) == 1
    assert mother.tried_for_child == father.tried_for_child == sim.clock.day
    assert resolve(sim, mother) == [], "a second try the same day"


def test_trying_is_not_always_conceiving(sim):
    mother, father = couple(sim)
    import hearthwick.family as fam
    outcomes = []
    for day in range(40):
        sim.clock.tick = day * sim.clock.ticks_per_day + 60
        before = sim.family.born
        sim.family.attempt(mother, father, sim.clock.tick, food_low=False)
        outcomes.append(sim.family.born > before)
        for c in list(sim.characters.values()):          # make room and time again
            if mother.id in c.parents:
                c.home, c.age = "elsewhere", 5.0
    assert 0 < sum(outcomes) < len(outcomes)
