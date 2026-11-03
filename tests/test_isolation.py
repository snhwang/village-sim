"""No villager may retrieve what belongs to another.

Instructions live in one shared corpus and ownership is expressed by a tag:
``persona-bryn`` is gated on ``char_bryn``, and the growth milestone will add
instructions a villager learned from its own life the same way. That is the
right structure -- most instructions are shared, so one copy should serve
everyone -- but it puts one villager's private behaviour in a pool everyone
scores against, with a tag as the only thing keeping it out of reach.

Memory has no such risk, because each villager's store is a separate object and
there is no query that could return another's. Instructions do, so the
invariant is asserted here across the whole roster rather than trusted.

The consolidation probe showed why this matters: generated instructions came
back with an empty scope. Added to the corpus as-is, one child's hard-won
lesson would have become village law.

Owner gating is BEAR's (bear.ownership). ``violations`` checks the
structure of the whole corpus. Whether a query can reach another's
instruction depends on how Hearthwick builds its contexts, so those checks
stay here.
"""

import pytest
from bear import Context, MarkerAction
from bear.ownership import owner_of, violations

from hearthwick.character import load_founders
from hearthwick.config import DATA_DIR, SimConfig
from hearthwick.corpus import build_corpus, build_retriever
from hearthwick.sim import Simulation


@pytest.fixture(scope="module")
def village():
    founders = load_founders(DATA_DIR / "villages" / "greater" / "founders.yaml")
    corpus = build_corpus(DATA_DIR, founders)
    return founders, corpus, build_retriever(corpus, None, 0.0)


GROUPS = ["world"]      # the world agent's instructions, apart from every villager's


def test_the_corpus_is_structurally_sound(village):
    """At most one owner each, never a soft owner tag, never an owner and a
    group together, only owners who exist, and every persona owned."""
    founders, corpus, _ = village
    found = violations(corpus, groups=GROUPS, known_owners=[f.id for f in founders],
                       require_owner=[f"persona-{f.id}" for f in founders])
    assert not found, [v.message for v in found]


def test_what_is_added_while_running_is_sound(tmp_path):
    """Owners join mid-run: a storyteller who arrives. The sweep takes the
    roster as it stands."""
    sim = Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0))
    try:
        sim._apply_world_action(MarkerAction("visitor", {"kind": "storyteller",
                                                         "place": "east_road"}))
        found = violations(sim.corpus, groups=GROUPS, known_owners=list(sim.characters))
        assert not found, [v.message for v in found]
        assert any(owner_of(i) == sim.visitors.present()[0].id for i in sim.corpus)
    finally:
        sim.close()


def test_a_villager_never_retrieves_another_villagers_instruction(village):
    """The invariant. Asserted for every villager against the whole corpus."""
    founders, corpus, retriever = village
    for character in founders:
        tags = [f"char_{character.id}", f"stage_{character.stage}", "daytime",
                "talking", "absorbing", "near_someone"]
        if character.role:
            tags.append(f"role_{character.role}")
        tags += [f"temp_{allele}" for allele in character.temperament.values()]

        query = f"{character.name} is in the village and decides what to do."
        for scored in retriever.retrieve(query, Context(tags=sorted(tags)), top_k=40):
            owner = owner_of(scored.instruction)
            assert owner in (None, character.id), (
                f"{character.id} retrieved {scored.id}, which belongs to {owner}")


def test_an_unowned_context_retrieves_nothing_owned(village):
    """A context with no char_ tag at all must reach no villager's private text."""
    _, _, retriever = village
    tags = ["stage_adult", "daytime", "talking", "role_farmer"]
    for scored in retriever.retrieve("Somebody is in the village.",
                                     Context(tags=tags), top_k=40):
        assert owner_of(scored.instruction) is None, \
            f"an anonymous context retrieved {scored.id}"


def test_the_world_and_the_villagers_cannot_reach_each_other(village):
    """The other half of the same rule, for the world's own instructions."""
    founders, corpus, retriever = village
    world_tags = ["world", "season_summer", "news_stale", "road_untended"]
    for scored in retriever.retrieve("It is summer in the village.",
                                     Context(tags=world_tags), top_k=40):
        assert "world" in (scored.instruction.scope.required_tags or ()), \
            f"the world retrieved {scored.id}, which is not its own"

    character = founders[0]
    tags = [f"char_{character.id}", f"stage_{character.stage}", "daytime"]
    for scored in retriever.retrieve("A villager decides what to do.",
                                     Context(tags=tags), top_k=40):
        assert "world" not in (scored.instruction.scope.required_tags or ()), \
            f"a villager retrieved the world's {scored.id}"


def test_a_learned_instruction_without_a_scope_is_refused(tmp_path):
    """What consolidation must never be allowed to do.

    generate_with_llm returns instructions with an empty scope. Adding one to
    the shared corpus ungated makes it retrievable by the whole village, so the
    growth milestone has to gate it on its owner before it goes in. This pins
    the failure mode so the guard cannot be quietly dropped later.
    """
    from bear import Instruction, InstructionType, ScopeCondition

    sim = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path,
                               embedder="bm25", retrieval_threshold=0.0))
    try:
        learner, other = list(sim.characters.values())[:2]
        ungated = Instruction(
            id="learned-ungated", type=InstructionType.DIRECTIVE, priority=50,
            content="You distrust the east road and take the long way. [!avoid(place=east_road)]",
            scope=ScopeCondition(required_tags=[]),
        )
        sim.retriever.corpus.add(ungated)
        sim.retriever.build_index()

        # Query with the instruction's own words, so ranking cannot hide the
        # gating: if it is admissible at all it comes back first.
        tags = sim.brain.context_tags(other, sim.characters)
        query = "distrust the east road and take the long way"
        reached = [s.id for s in sim.retriever.retrieve(query, Context(tags=tags), top_k=40)]
        assert "learned-ungated" in reached, (
            "an ungated instruction should be reachable by anyone -- that is "
            "precisely the hazard this test exists to document")

        # Gated on its owner, the same villager can no longer reach it.
        sim.retriever.corpus.remove("learned-ungated")
        ungated.scope = ScopeCondition(required_tags=[f"char_{learner.id}"])
        sim.retriever.corpus.add(ungated)
        sim.retriever.build_index()
        reached = [s.id for s in sim.retriever.retrieve(query, Context(tags=tags), top_k=40)]
        assert "learned-ungated" not in reached
    finally:
        sim.close()

