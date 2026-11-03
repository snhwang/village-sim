"""Couples form by courtship, and the one asked decides (hearthwick/courtship.py)."""

import asyncio
import json

import pytest
from bear import Context

from hearthwick import courtship
from hearthwick.config import SimConfig
from hearthwick.markers import MarkerContext, build_registry
from hearthwick.sim import Simulation


def make_sim(tmp_path):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0))


@pytest.fixture
def sim(tmp_path):
    s = make_sim(tmp_path)
    yield s
    s.close()


def resolve(sim, who, marker):
    ctx = MarkerContext(sim.world, sim.clock, who, sim.characters, sim.rng_for("t", "t"),
                        sim.config.near_radius, news=sim.brain._news_roots,
                        courtship=sim.courtship, building=sim.building)
    return build_registry().process(marker, context=ctx)[1]


def act(sim, who, marker, instruction):
    """Decide on a marker and carry it out, as a step would."""
    for a in resolve(sim, who, marker):
        who.activity = None
        who.queue.append(sim._activity(a, instruction))
    sim._advance(who)


def events(sim, kind):
    sim.log.flush()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if e["type"] == kind]


def fond(sim, a, b, amount=12.0, together=True):
    sim.courtship.affinity[courtship.pair(a.id, b.id)] = amount
    if together:
        b.pos = a.pos


# In the greater village, Maren is the one unpartnered woman of age. Fen is
# a year older and lives alone. Sten is six years younger.


def test_who_can_marry_whom(sim):
    ch = sim.characters
    maren, fen, sten, dunn = ch["maren"], ch["fen"], ch["sten"], ch["dunn"]
    assert courtship.eligible(maren, fen, ch)
    assert courtship.eligible(maren, sten, ch)                    # six years apart is not too far
    for _ in range(sim.clock.ticks_per_day):                  # and stays so as both age
        maren.age += sim.clock.years_per_tick()
        sten.age += sim.clock.years_per_tick()
    assert courtship.eligible(maren, sten, ch)
    assert not courtship.eligible(maren, dunn, ch)                # eight years apart is
    assert not courtship.eligible(fen, sten, ch)                  # two men
    assert not courtship.eligible(maren, ch["osric"], ch)         # already partnered
    assert not courtship.eligible(maren, ch["merrick"], ch)       # an elder
    orla, peder = ch["orla"], ch["peder"]
    orla.stage = peder.stage = "adult"
    assert not courtship.eligible(orla, peder, ch)                # brother and sister
    assert not courtship.eligible(ch["thea"], peder, ch)          # mother and son


def test_fondness_grows_by_talking_and_company_and_fades(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    sim.courtship.conversed(maren, fen)
    assert sim.courtship.of("maren", "fen") == courtship.PER_CONVERSATION
    fen.pos = maren.pos
    sim.courtship.hour_together()
    assert sim.courtship.of("fen", "maren") == courtship.PER_CONVERSATION + courtship.PER_HOUR_NEAR
    before = sim.courtship.of("maren", "fen")
    sim.courtship.new_day()
    assert sim.courtship.of("maren", "fen") == pytest.approx(before * (1 - courtship.DAILY_DECAY))


def test_a_conversation_ending_makes_two_fonder(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fen.pos = maren.pos
    conv = sim.conversations.start(maren, fen, "the weather", None)
    sim.conversations.end(conv)
    assert sim.courtship.of("maren", "fen") == courtship.PER_CONVERSATION


def test_what_a_villager_sees_of_courting(sim):
    maren, fen, sten = (sim.characters[k] for k in ("maren", "fen", "sten"))
    assert "courting" not in sim.brain.context_tags(maren, sim.characters)
    fond(sim, maren, fen, courtship.SWEETHEART)
    tags = sim.brain.context_tags(maren, sim.characters)
    assert "courting" in tags and "sweetheart_near" in tags and "fond_enough" not in tags
    fond(sim, maren, fen, courtship.PROPOSE)
    assert "fond_enough" in sim.brain.context_tags(maren, sim.characters)
    fen.pos = sim.world.places["forest_edge"].tiles()[0]
    assert "sweetheart_near" not in sim.brain.context_tags(maren, sim.characters)
    # Asked by Sten while fonder of Fen.
    sim.courtship.proposals["maren"] = ("sten", sim.clock.tick)
    tags = sim.brain.context_tags(maren, sim.characters)
    assert "proposed_to" in tags and "prefers_another" in tags and "hardly_knows_asker" in tags
    fond(sim, maren, sten, courtship.KNOWN_WELL + 1, together=False)
    tags = sim.brain.context_tags(maren, sim.characters)
    assert "hardly_knows_asker" not in tags and "prefers_another" not in tags
    assert "courting" not in sim.brain.context_tags(sim.characters["osric"], sim.characters)


def test_a_proposal_needs_fondness_and_the_sweetheart_near(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen, courtship.PROPOSE - 1)
    assert resolve(sim, fen, "[!propose]") == []               # not fond enough yet
    fond(sim, maren, fen, courtship.PROPOSE)
    assert [a.data["target"] for a in resolve(sim, fen, "[!propose]")] == ["maren"]
    fen.pos = sim.world.places["forest_edge"].tiles()[0]
    assert resolve(sim, fen, "[!propose]") == []               # she is not here
    assert resolve(sim, maren, "[!accept_proposal]") == []     # nobody asked her


def test_the_one_asked_says_yes_and_they_make_a_home(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen)
    act(sim, fen, "[!propose]", "family-propose")
    assert sim.courtship.pending_for(maren) == "fen"
    assert resolve(sim, fen, "[!propose]") == []               # asked already
    act(sim, maren, "[!accept_proposal]", "family-accept-proposal")
    assert maren.partner == "fen" and fen.partner == "maren"
    # Fen lives alone, so they live at his house, and nobody waits for one.
    assert maren.home == fen.home == "home_9"
    assert sim.courtship.waiting == []
    married = events(sim, "married")
    assert len(married) == 1 and married[0]["asker"] == "fen" and not married[0]["waiting"]
    assert any(f.root.startswith("wedding:") for f in sim.diffuser.store_for("maren").facts)
    assert "courting" not in sim.brain.context_tags(maren, sim.characters)


def test_saying_no_keeps_them_from_asking_again_for_a_while(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen)
    act(sim, fen, "[!propose]", "family-propose")
    act(sim, maren, "[!decline_proposal]", "family-decline-not-ready")
    assert maren.partner is None and fen.partner is None
    assert len(events(sim, "declined")) == 1
    assert resolve(sim, fen, "[!propose]") == []
    sim.clock.tick += courtship.DECLINED_COOLDOWN_DAYS * sim.clock.ticks_per_day
    assert resolve(sim, fen, "[!propose]")


def test_a_question_not_answered_in_a_day_lapses(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen)
    act(sim, fen, "[!propose]", "family-propose")
    sim.clock.tick += sim.clock.ticks_per_day
    assert sim.courtship.pending_for(maren) is None
    assert resolve(sim, maren, "[!accept_proposal]") == []


def test_both_asking_in_the_same_tick_makes_one_proposal(sim):
    """Both can decide before either acts. The second finds a question
    standing when it comes to ask."""
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen)
    for who in (fen, maren):
        for a in resolve(sim, who, "[!propose]"):
            who.activity = None
            who.queue.append(sim._activity(a, "family-propose"))
    sim._advance(fen)
    sim._advance(maren)
    assert len(events(sim, "proposed")) == 1


def test_a_couple_from_family_homes_waits_for_a_house(sim):
    """Gisla lives with her parents and Dunn with Katrin. Dunn's house has
    fewer others in it, so they live there, and wait for a house."""
    ch = sim.characters
    gisla, dunn = ch["gisla"], ch["dunn"]
    gisla.stage, gisla.age = "adult", 8.0
    fond(sim, gisla, dunn)
    act(sim, dunn, "[!propose]", "family-propose")
    act(sim, gisla, "[!accept_proposal]", "family-accept-proposal")
    assert gisla.home == dunn.home == "home_2"
    assert sim.courtship.waiting == [("dunn", "gisla")]
    assert events(sim, "married")[0]["waiting"]


def test_an_empty_house_is_taken_first(sim):
    ch = sim.characters
    ch["freya"].home = "home_2"                    # house 7 stands empty
    maren, fen = ch["maren"], ch["fen"]
    fond(sim, maren, fen)
    act(sim, fen, "[!propose]", "family-propose")
    act(sim, maren, "[!accept_proposal]", "family-accept-proposal")
    assert maren.home == fen.home == "home_7"


def test_a_courting_villager_can_retrieve_what_to_do(sim):
    maren, fen = sim.characters["maren"], sim.characters["fen"]
    fond(sim, maren, fen)
    tags = sim.brain.context_tags(fen, sim.characters)
    ids = [s.id for s in sim.retriever.retrieve("with someone in the evening",
                                                 Context(tags=tags), top_k=300)]
    assert "family-propose" in ids and "family-seek-sweetheart" in ids
    sim.courtship.proposals["maren"] = ("fen", sim.clock.tick)
    tags = sim.brain.context_tags(maren, sim.characters)
    ids = [s.id for s in sim.retriever.retrieve("asked to marry",
                                                 Context(tags=tags), top_k=300)]
    assert "family-accept-proposal" in ids and "family-decline-not-ready" in ids
    assert "family-decline-prefer-another" not in ids
    # Fond of the asker for long enough, "I hardly know them" is not an answer.
    fond(sim, maren, fen, courtship.KNOWN_WELL)
    tags = sim.brain.context_tags(maren, sim.characters)
    ids = [s.id for s in sim.retriever.retrieve("asked to marry",
                                                 Context(tags=tags), top_k=300)]
    assert "family-accept-proposal" in ids and "family-decline-not-ready" not in ids


def test_couples_and_fondness_survive_a_checkpoint(sim, tmp_path):
    ch = sim.characters
    gisla, dunn = ch["gisla"], ch["dunn"]
    gisla.stage, gisla.age = "adult", 8.0
    fond(sim, gisla, dunn)
    fond(sim, ch["maren"], ch["fen"], 7.5)
    act(sim, dunn, "[!propose]", "family-propose")
    act(sim, gisla, "[!accept_proposal]", "family-accept-proposal")
    path = asyncio.run(sim.save())
    resumed = make_sim(tmp_path / "again")
    try:
        resumed.resume_from(path)
        back = resumed.characters
        assert back["gisla"].partner == "dunn" and back["gisla"].home == "home_2"
        assert resumed.courtship.waiting == [("dunn", "gisla")]
        assert resumed.courtship.of("maren", "fen") == 7.5
    finally:
        resumed.close()
