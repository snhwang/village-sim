"""Death of old age.

Nobody died in the village until this, so a village left running only grew.
As DESIGN.md section 7 planned, each villager has a lifespan, drawn between
35 and 50 in-game years, and dies at the first midnight past it. The draw
comes from the run's seed and the villager's id, so it is fixed at birth,
the same every time it is asked for, and a checkpoint needs nothing new to
carry it. The founders' elders are 26 to 32, and no generated founder is
older than 34, so nobody starts a run past its span, and the first deaths come
some years in. Visitors are passing through and do not die here. Sickness and
raids do not shorten a life yet.

Death is simulation code, not a decision. A death changes what the village
is made of, and nothing else is told to change. The villager is gone from the
frames and does nothing more. What it knew stays in the run's record, for
provenance, but nobody can hear it any more, so it lives on only in what
others kept. Its partner is widowed: the record of whom it married stays, so
it still knows, and a partner who has died leaves the survivor free to marry
again (hearthwick/courtship.py). Its apprentices each go to the master of the
trade they are fondest of, if one has room, and otherwise practise on alone.
Its household, or whoever is nearest if it lived alone, knows by morning, and
the news travels like any other.
"""

from __future__ import annotations

import random

from hearthwick import trades
from hearthwick.character import Character

LIFESPAN = (35.0, 50.0)     # in-game years


def lifespan(c: Character, seed: int) -> float:
    return random.Random(f"{seed}:lifespan:{c.id}").uniform(*LIFESPAN)


class Mortality:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.died = 0

    def new_day(self) -> None:
        sim = self.sim
        if not sim.config.mortality:
            return
        for c in sorted(sim.characters.values(), key=lambda o: o.id):
            if c.alive and not c.visitor and c.age >= lifespan(c, sim.config.seed):
                self.die(c, sim.clock.tick)

    def die(self, c: Character, tick: int) -> None:
        sim = self.sim
        if c.conversation_id and c.conversation_id in sim.conversations.active:
            sim.conversations.end(sim.conversations.active[c.conversation_id])
        # Those who share its home are there when it dies. Read before it is
        # gone, and the youngest cannot tell anyone.
        household = sorted(o.id for o in sim.characters.values()
                           if o.alive and o.id != c.id and not o.visitor
                           and o.home == c.home and o.stage != "infant")
        c.alive = False
        c.activity, c.path = None, []
        c.queue.clear()
        self.died += 1
        moved = self._rehome_apprentices(c, tick)
        if getattr(sim, "economy", None) is not None:
            sim.economy.died(c, tick)
        sim.log.event(tick, "died", character=c.id, age=round(c.age, 2),
                      stage=c.stage, role=c.role, partner=c.partner,
                      apprentices=moved)
        witnesses = household or sim._nearest_to(c.pos)
        sim.diffuser.witness("death", c.home, witnesses, {"topic": c.name}, tick,
                             root=f"death:{c.id}")

    def _rehome_apprentices(self, master: Character, tick: int) -> dict[str, str | None]:
        """Each of its apprentices to the master of its trade it is fondest
        of, among those with room. With none free, it practises on alone and
        still qualifies when its skill is enough."""
        sim = self.sim
        moved: dict[str, str | None] = {}
        for a in sorted(trades.apprentices_of(master.id, sim.characters), key=lambda o: o.id):
            new = trades.find_master(a, a.trade, sim.characters,
                                     fondness=sim.courtship.of) if a.trade else None
            moved[a.id] = new
            if new is not None:
                a.mentor = new
                sim.log.event(tick, "new_master", character=a.id, trade=a.trade,
                              master=new, was=master.id,
                              fondness=round(sim.courtship.of(a.id, new), 2))
        return moved
