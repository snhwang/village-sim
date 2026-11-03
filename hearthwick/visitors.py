"""Visitors: people from outside who come up the east road, stay, and go.

So far the only visitor is a traveling storyteller. The world decides when one
comes (``[!visitor(storyteller)]``). The storyteller is then an entity like any
villager. It retrieves from the same corpus, through its own tags, and talks,
listens and keeps what it hears through its own lens. What makes it a visitor:

- It arrives holding news from beyond the village, first-hand as far as the
  village can tell, so every chain that news starts traces back to it.
- It lodges at the inn, which is its home while it stays.
- After ``VISITOR_DAYS`` it takes the east road out. What it heard here goes
  with it. Its store stays in the record, so news that left the village can be
  traced as well as news that came in.

A storyteller's temperament is drawn the way a founder's is, two copies of
every gene, so no two are alike.
"""

from __future__ import annotations

import logging
import random

from hearthwick.character import TRAIT_PHRASES, Character
from hearthwick.genome import alleles, diploid, library, load_loci, phenotype

logger = logging.getLogger(__name__)

VISITOR_DAYS = 2          # how long a storyteller stays
VISITOR_GAP_DAYS = 3      # before the next may come, once one has gone
NEWS_CARRIED = 3          # pieces of news from beyond, per storyteller
LODGING = "inn"
ROAD = "east_road"

# What the roads beyond the village are talking about. The world's travelers
# bring some of the same, which is as it should be: a storyteller who has been
# down the same road has heard the same things.
OUTSIDE_NEWS = (
    "that there is to be a fair beyond the forest",
    "that a sickness is going round two valleys over",
    "that there has been fighting beyond the forest",
    "that the low road is washed out at the ford",
    "that the lord's men are counting heads for a new tax",
    "that wolves have been seen at the edge of the high pastures",
    "that the miller at Ashby found a hoard of old coins in his wall",
    "that grain is dear in the market towns this year",
)

NAMES = {"Aldous": "male", "Brannoc": "male", "Cadell": "male", "Doran": "male",
         "Wystan": "male", "Elspeth": "female", "Isolde": "female", "Maudie": "female",
         "Tamsin": "female", "Rowena": "female"}


def persona(name: str, traits: dict[str, str]) -> str:
    return (f"{name} is a traveling storyteller, passing through with tales from other "
            f"villages and news from the roads between. {name} "
            f"{TRAIT_PHRASES[traits['sociability']]}, {TRAIT_PHRASES[traits['curiosity']]}, "
            f"and {TRAIT_PHRASES[traits['candor']]}.")


class Visitors:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.arrived = 0          # how many have come, for names and seeds

    def present(self) -> list[Character]:
        return [c for c in self.sim.characters.values() if c.visitor and c.alive]

    def arrive(self, tick: int) -> Character:
        """A storyteller comes up the east road, carrying news from beyond."""
        sim = self.sim
        rng = random.Random(f"{sim.config.seed}:visitor:{self.arrived}")
        self.arrived += 1
        taken = {c.id for c in sim.characters.values()}
        free = [n for n in NAMES if n.lower() not in taken]
        name = rng.choice(free) if free else f"Stranger{self.arrived}"
        registry = load_loci()
        copies = {locus: [rng.choice(values), rng.choice(values)]
                  for locus, values in alleles(library(), registry).items()}
        cid = name.lower()
        temperament = phenotype(diploid(copies, cid), registry)
        c = Character(
            id=cid, name=name, sex=NAMES.get(name, rng.choice(["male", "female"])),
            age=float(rng.randint(11, 18)), stage="adult", role="storyteller",
            home=LODGING, parents=[], partner=None, mentor=None,
            temperament=temperament, persona=persona(name, temperament),
            genotype=copies, visitor=True,
            leaves_at=tick + VISITOR_DAYS * sim.clock.ticks_per_day)
        road = sim.world.places[ROAD]
        c.pos = max(road.tiles())               # the far end, where the road comes in
        sim.join(c)
        sim.world_agent.state.visitors_here.append(cid)

        news = rng.sample(OUTSIDE_NEWS, NEWS_CARRIED)
        for i, topic in enumerate(news):
            sim.diffuser.witness("tale", ROAD, [cid], {"topic": topic}, tick,
                                 root=f"tale:{ROAD}:{tick}-{i}")
        sim.log.event(tick, "roster", characters=[c.profile()])
        sim.log.event(tick, "visitor_arrived", character=cid, carries=news,
                      leaves_at=c.leaves_at)
        return c

    def depart(self, c: Character, tick: int) -> None:
        """The storyteller takes the east road out, and what it heard goes too."""
        if not c.alive:
            return
        if c.conversation_id and c.conversation_id in self.sim.conversations.active:
            self.sim.conversations.end(self.sim.conversations.active[c.conversation_id])
        c.alive = False
        c.activity, c.path = None, []
        c.queue.clear()
        store = self.sim.diffuser.store_for(c.id)
        village = sorted({f.root for f in store.facts
                          if f.teller is not None and not f.root.startswith("tale:")})
        state = self.sim.world_agent.state
        state.last_visitor_day = self.sim.clock.day
        if c.id in state.visitors_here:
            state.visitors_here.remove(c.id)
        self.sim.log.event(tick, "visitor_departed", character=c.id,
                           takes=village, holds=len(store.facts))
