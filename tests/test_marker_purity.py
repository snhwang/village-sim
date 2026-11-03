"""Resolving a marker computes an action and changes nothing.

The decision resolves candidates down the ranking before choosing, and throws
away every one it does not choose (hearthwick/brain.py). That is only safe if
resolving has no effect: every change happens later, in ``sim._begin`` for a
villager and ``sim._apply_world_action`` for the world. This was a convention.
Here it is pinned, so a handler that starts acting as it resolves fails a test
instead of quietly corrupting every refused candidate.

The one thing resolving may touch is the random stream the context supplies,
which the place aliases ``quiet_place``, ``unvisited_place`` and
``random_home`` draw from.
"""

import json
import random

import pytest
from bear import MarkerAction, parse_actions

from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, WorldMarkerContext
from hearthwick.sim import Simulation


@pytest.fixture
def sim(tmp_path):
    s = Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", retrieval_threshold=0.0))
    # Every kind of resolver in play: a visitor who can depart, and graduates
    # whose apprentice markers look for a master.
    s._apply_world_action(MarkerAction("visitor", {"kind": "storyteller", "place": "east_road"}))
    for c in [c for c in s.characters.values() if c.stage == "child"][:2]:
        c.stage, c.trade = "apprentice", None
    # A courting pair side by side who could propose, a proposal standing for
    # another, and a couple waiting for a house the crafters could fell and
    # build for.
    ch = s.characters
    ch["gisla"].stage, ch["gisla"].age = "adult", 8.0
    ch["dunn"].pos = ch["gisla"].pos
    s.courtship.affinity[("dunn", "gisla")] = 12.0
    s.courtship.proposals["maren"] = ("fen", s.clock.tick)
    s.courtship.waiting.append(("edek", "mabel"))
    # Some timber to build with, and grain to sell.
    s.economy.ensure(0)
    s.building.stock.update(timber=2.0)
    farmers = [c for c in ch.values() if c.role == "farmer" and c.alive][:3]
    s.economy._add(farmers[0].id, "grain", 5.0)
    yield s
    s.close()


def state(sim) -> tuple:
    people = {c.id: json.dumps({**c.profile(), "pos": c.pos, "path": c.path,
                                "activity": str(c.activity), "queue": [str(a) for a in c.queue],
                                "avoiding": c.avoiding, "energy": c.energy},
                               sort_keys=True, default=str)
              for c in sim.characters.values()}
    world = json.dumps(sim.world_agent.state.to_dict(), sort_keys=True, default=str)
    places = json.dumps(sim.world.to_dict(), sort_keys=True)
    stores = {holder: len(store.facts) for holder, store in sim.diffuser.stores.items()}
    world += json.dumps([sim.courtship.to_dict(), sim.building.to_dict(), sim.economy.to_dict()],
                        sort_keys=True)
    return people, world, places, stores, sorted(i.id for i in sim.corpus), len(sim._pending_events)


def test_resolving_every_marker_for_everyone_changes_nothing(sim):
    marked = [i.content for i in sim.corpus if parse_actions(i.content)]
    before = state(sim)
    resolved = set()
    for c in list(sim.characters.values()):
        ctx = MarkerContext(sim.world, sim.clock, c, sim.characters, random.Random(1),
                            sim.config.near_radius, news=sim.brain._news_roots,
                            courtship=sim.courtship, building=sim.building)
        for content in marked:
            resolved |= {a.kind for a in sim.registry.process(content, context=ctx)[1]}
    # The fixture exists so that these resolve. A check that none of them
    # changes anything is empty if none of them ran.
    assert {"propose", "accept_proposal", "decline_proposal", "fell", "build",
            "sell"} <= resolved
    world = WorldMarkerContext(sim.world, sim.clock, sim.world_agent.state)
    for content in marked:
        sim.world_agent.registry.process(content, context=world)
    after = state(sim)
    for name, a, b in zip(("villagers", "world state", "map", "knowledge", "corpus", "pending"),
                          before, after):
        assert a == b, f"resolving a marker changed the {name}"


def test_a_candidate_resolves_the_same_whatever_was_tried_above_it(sim):
    """Each candidate draws from its own random stream. With one stream for the
    whole decision, a refused candidate above shifted where a random_home or an
    unvisited_place below it led."""
    from bear import ScoredInstruction

    c = next(v for v in sim.characters.values() if v.stage == "adult" and not v.visitor)
    corpus = sim.corpus
    draws = [i for i in corpus if "random_home" in i.content or "unvisited_place" in i.content
             or "quiet_place" in i.content]
    assert len(draws) >= 2
    first, second = (ScoredInstruction(instruction=i, score=0.5, final_score=0.5) for i in draws[:2])

    def resolve(order):
        ctx = MarkerContext(sim.world, sim.clock, c, sim.characters, random.Random(0),
                            sim.config.near_radius, news=sim.brain._news_roots)
        return {s.id: [(a.kind, a.data) for a in sim.brain._resolve(s, ctx, c)] for s in order}

    assert resolve([first, second])[second.id] == resolve([second])[second.id]
