"""Knowledge spreads, changes on the way, and changes what villagers do."""

import asyncio
import json

import numpy as np
import pytest
from bear import Context

from hearthwick.config import SimConfig
from hearthwick.knowledge import Fact, KnowledgeStore
from hearthwick.sim import Simulation


@pytest.fixture
def sim(tmp_path):
    s = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path,
                             embedder="bm25", retrieval_threshold=0.0))
    yield s
    s.close()


def fact(**kw):
    base = dict(id="f1", holder="rosa", text="The well has turned.", kind="sickness",
                place="well", root="sicken:well:100", parent=None, teller=None,
                hop=0, tick=100)
    return Fact(**{**base, **kw})


# --- the store ------------------------------------------------------------

def test_a_fact_tags_its_holder_by_what_it_is_about():
    assert fact().tag == "knows_sickness_well"
    assert fact(kind="hazard", place="east_road").tag == "knows_hazard_east_road"
    assert fact(place=None, kind="news").tag == "knows_news"


def test_the_same_news_in_different_words_is_one_fact():
    store = KnowledgeStore("rosa", duplicate_above=0.85)
    store.add(fact(vector=np.array([1.0, 0.0])))

    near = np.array([0.99, 0.14])          # same news, different words
    far = np.array([0.0, 1.0])             # unrelated
    assert store.duplicate_of(near)[0] is not None
    assert store.duplicate_of(far)[0] is None


def test_what_a_villager_brings_up_first_is_what_matters_most():
    store = KnowledgeStore("rosa")
    store.add(fact(id="a", kind="news", tick=200))
    store.add(fact(id="b", kind="hazard", tick=100))
    assert [f.id for f in store.tellable(1)] == ["b"]


def test_a_hazard_from_the_web_is_news_of_elsewhere():
    """Told first as hazards, the web's floods and wildfires crowded the
    village's own news out of talk in the live village of 2026-10-01."""
    afar = fact(id="w", kind="hazard", place=None, root="web:s7", tick=300)
    told_on = fact(id="w2", kind="hazard", place=None, root="web:s7", parent="w",
                   teller="nell", hop=4, tick=400)
    assert afar.afar and told_on.afar and not fact().afar
    assert afar.tag == "knows_hazard_afar"           # gates nothing in the village
    store = KnowledgeStore("rosa")
    store.add(afar)
    store.add(fact(id="r", kind="rumor", place=None, root="rumor:x", tick=100))
    store.add(fact(id="n", kind="news", place=None, root="traveler:x", tick=200))
    # Brought up as news: after the village's rumour, and among its news by
    # how recent it is.
    assert [f.id for f in store.tellable(3)] == ["r", "w", "n"]


def test_provenance_records_the_chain():
    told = fact(id="f2", holder="nell", parent="f1", teller="rosa", hop=1, tick=120)
    record = told.provenance("store", "told")
    assert record.subject == "fact:f2"
    assert record.actor == "nell" and record.parents == ["f1"]
    assert record.context["teller"] == "rosa" and record.context["hop"] == 1


# --- witnessing and telling ----------------------------------------------

def test_only_witnesses_hold_an_event_first_hand(sim):
    sim.diffuser.witness("sicken", "well", ["rosa", "pip"], {}, tick=50)
    assert len(sim.diffuser.store_for("rosa")) == 1
    assert len(sim.diffuser.store_for("garrick")) == 0

    held = sim.diffuser.store_for("rosa").facts[0]
    assert held.hop == 0 and held.teller is None and held.kind == "sickness"


def test_telling_adds_a_hop_and_remembers_who_said_it(sim):
    sim.diffuser.witness("sicken", "well", ["rosa"], {}, tick=50)
    source = sim.diffuser.store_for("rosa").facts[0]

    result = asyncio.run(sim.diffuser.offer(source, sim.characters["rosa"],
                                            sim.characters["nell"]))
    assert result.outcome in ("stored", "unchanged")
    received = sim.diffuser.store_for("nell").facts[0]
    assert received.hop == 1
    assert received.teller == "rosa" and received.parent == source.id
    assert received.root == source.root      # same event at the root


def test_news_from_an_event_you_already_know_is_not_stored_twice(sim):
    sim.diffuser.witness("sicken", "well", ["rosa", "nell"], {}, tick=50)
    source = sim.diffuser.store_for("rosa").facts[0]

    result = asyncio.run(sim.diffuser.offer(source, sim.characters["rosa"],
                                            sim.characters["nell"]))
    assert result.outcome == "duplicate"
    assert len(sim.diffuser.store_for("nell")) == 1
    assert sim.diffuser.store_for("nell").facts[0].reinforced == 2


# --- knowledge changes behavior ------------------------------------------

def test_knowing_makes_instructions_retrievable_that_were_not(sim):
    rosa = sim.characters["rosa"]

    def can_reach(instruction_id):
        tags = sim.brain.context_tags(rosa, sim.characters)
        query = sim.brain.situation(rosa, sim.characters)
        return instruction_id in {s.id for s in
                                  sim.retriever.retrieve(query, Context(tags=tags), top_k=30)}

    assert not can_reach("knows-avoid-sick-well")
    sim.diffuser.witness("sicken", "well", ["rosa"], {}, tick=sim.clock.tick)
    assert "knows_sickness_well" in sim.brain.context_tags(rosa, sim.characters)
    assert can_reach("knows-avoid-sick-well")


def test_a_place_being_avoided_is_not_chosen_as_a_destination(sim):
    import random

    from bear import parse_actions
    from hearthwick.markers import AvoidHandler, MarkerContext, resolve_place

    rosa = sim.characters["rosa"]
    ctx = MarkerContext(sim.world, sim.clock, rosa, sim.characters, random.Random(0), 4)
    assert resolve_place("well", ctx) == "well"

    rosa.avoiding["well"] = sim.clock.tick + 100
    assert resolve_place("well", ctx) is None
    # and deciding to avoid it again is not a decision
    marker = parse_actions("[!avoid(place=well)]")[0]
    assert AvoidHandler().to_action(marker, ctx) is None


def test_a_run_records_what_everyone_knew_and_how_they_learned_it(sim):
    asyncio.run(sim.run(sim.clock.ticks_per_day * 3))
    sim.close()

    knowledge = json.loads((sim.log.dir / "knowledge.json").read_text(encoding="utf-8"))
    assert any(facts for facts in knowledge.values())

    events = [json.loads(l) for l in
              (sim.log.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    stored = [e for e in events if e["type"] == "knowledge_stored"]
    assert stored, "three days should produce some knowledge"
    assert all("provenance" in e and e["provenance"]["subject_kind"] == "fact"
               for e in stored)


def test_a_warning_goes_only_to_someone_with_something_to_learn(sim):
    """Once blight was common, villagers chose this warning in 29% of all
    decisions, telling neighbours who already knew."""
    import random

    from bear import parse_actions
    from hearthwick.markers import MarkerContext, WarnHandler

    rosa = sim.characters["rosa"]
    others = sorted((o for o in sim.characters.values() if o.id != "rosa"),
                    key=lambda o: o.id)[:2]
    near, nearer = others
    for o in others:
        o.activity = None          # awake, so a warning can reach them
    near.pos = (rosa.pos[0] + 2, rosa.pos[1])
    nearer.pos = (rosa.pos[0] + 1, rosa.pos[1])
    for o in sim.characters.values():
        if o.id not in ("rosa", near.id, nearer.id):
            o.pos = (0, 0)

    ctx = MarkerContext(sim.world, sim.clock, rosa, sim.characters, random.Random(0), 4,
                        news=sim.brain._news_roots)
    warn = parse_actions("[!warn(target=nearby, topic=the well)]")[0]
    by_name = parse_actions(f"[!warn(target={nearer.id}, topic=the well)]")[0]

    sim.diffuser.witness("sicken", "well", ["rosa"], {}, tick=sim.clock.tick)
    assert WarnHandler().to_action(warn, ctx).data["target"] == nearer.id

    # The nearest already knows, so the warning goes past them.
    sim.diffuser.witness("sicken", "well", [nearer.id], {}, tick=sim.clock.tick)
    assert WarnHandler().to_action(warn, ctx).data["target"] == near.id
    assert WarnHandler().to_action(by_name, ctx) is None

    # Everyone near knows, so there is nobody to warn.
    sim.diffuser.witness("sicken", "well", [near.id], {}, tick=sim.clock.tick)
    assert WarnHandler().to_action(warn, ctx) is None

    # Rosa has other news they lack, but this warning is about the well.
    sim.diffuser.witness("traveler", "east_road", ["rosa"], {"topic": "news"},
                         tick=sim.clock.tick + 1)
    assert WarnHandler().to_action(warn, ctx) is None
    road = parse_actions("[!warn(target=nearby, topic=raiders on the east road)]")[0]
    assert WarnHandler().to_action(road, ctx).data["target"] == nearer.id



def test_refused_options_never_crowd_out_what_can_be_done(sim, monkeypatch):
    """Late in a run Ilsa stood idle in the rain for tick after tick. Her four
    best candidates were warning about the blight and the well with nobody left
    to warn, and avoiding the fields and the well, which she already avoided.
    The brain sampled among the top four and gave up when all four refused, so
    sheltering from the rain, fifth, was never tried. This is her ranking."""
    from bear import ScoredInstruction

    rosa = sim.characters["rosa"]
    for place in ("well", "fields"):
        rosa.avoiding[place] = sim.clock.tick + 500
    for other in sim.characters.values():
        if other.id != "rosa":
            other.pos = (0, 0)                     # nobody near enough to warn
    rosa.pos = (20, 15)
    rosa.activity = None
    ranking = ["knows-warn-about-blight", "knows-avoid-blighted-field",
               "knows-avoid-sick-well", "knows-warn-about-well", "weather-wait-out-rain"]
    scored = [ScoredInstruction(instruction=sim.corpus.get(i), similarity=0.5,
                                final_score=0.9 - 0.01 * n) for n, i in enumerate(ranking)]
    monkeypatch.setattr(sim.retriever, "retrieve", lambda *a, **k: scored)

    decision, actions = sim.brain.decide(rosa, sim.characters)
    assert decision.chosen == "weather-wait-out-rain" and actions
    assert decision.refused == ranking[:4]


class CountingEmbedder:
    """Every text gets a vector of its own, and every call is counted."""

    def __init__(self):
        self.calls = []

    def embed(self, texts, is_query=False):
        self.calls.append(list(texts))
        return np.array([[float(len(t)), float(sum(map(ord, t)) % 97), 1.0] for t in texts])

    def embed_single(self, text, is_query=False):
        return self.embed([text], is_query)[0]

    def info(self):
        return {"kind": "counting"}


def test_a_restore_embeds_each_known_text_once_and_together(tmp_path):
    """One fact at a time, the live village's 34,000 facts took ten minutes
    to come back through the embedding service."""
    s = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path, embedder="bm25",
                             retrieval_threshold=0.0))
    holders = sorted(s.characters)[:6]
    for i, holder in enumerate(holders):
        for n in range(5):
            s.diffuser.remember(holder, f"News number {n} came by the road.", "did", 10 + i)
    path = asyncio.run(s.save())
    s.close()
    again = Simulation(SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path / "again",
                                 embedder="bm25", retrieval_threshold=0.0))
    try:
        again.embedder = CountingEmbedder()
        again.resume_from(path)
        texts = [t for call in again.embedder.calls for t in call]
        assert len(again.embedder.calls) <= 2 and len(texts) == len(set(texts))
        held = [f for h in holders for f in again.diffuser.store_for(h).facts]
        assert len(held) >= 30 and all(f.vector is not None for f in held)
    finally:
        again.close()
