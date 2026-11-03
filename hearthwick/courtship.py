"""Courtship: a man and a woman grow fond, one proposes, the other answers.

Affinity comes from shared life, not from traits. Two villagers grow fond of
each other by talking and by spending time near each other, and the fondness
fades without contact. Temperament matters only through behaviour: a sociable
villager meets more people. Attraction is not computed from temperament or
genes, because mate choice that depends on genes is selection, which belongs
to the behavioural-genetics paper (SPECIFICATION section 2.7b).

Everything a villager does about it is retrieval. It sees ``courting`` when it
has a sweetheart, ``sweetheart_near`` when one is close, and ``fond_enough``
once the two are fond enough to marry. Asked, it sees ``proposed_to``, with
``prefers_another`` when it is fonder of someone else than of who asked and
``hardly_knows_asker`` while their fondness is still new. Its instructions
decide the rest. The last three are premises the instructions state, so they
are hard gates (SPECIFICATION section 3, rule 1). Handlers only check what is possible,
and every rule is checked again when an action is carried out, since two
villagers can act in the same tick.

A new couple lives in an empty home if there is one. Otherwise they move into
whichever of their homes has fewer others in it. If that is a family home
with others still living there, they wait for a house of their own, and the
village needs one built (hearthwick/building.py).
"""

from __future__ import annotations

from hearthwick.character import Character
from hearthwick.world import distance

PER_CONVERSATION = 1.0
PER_HOUR_NEAR = 0.25
DAILY_DECAY = 0.1           # the share of affinity that fades each day
SWEETHEART = 6.0            # affinity that makes someone a sweetheart
PROPOSE = 10.0              # affinity at which a proposal can be made
KNOWN_WELL = 15.0           # below this, one asked can say it hardly knows the asker
MAX_AGE_GAP = 6.0           # in-game years
PROPOSAL_DAYS = 1           # a proposal not answered within a day lapses
DECLINED_COOLDOWN_DAYS = 4  # before asking the same person again


def pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def kin(a: Character, b: Character) -> bool:
    return (a.id in b.parents or b.id in a.parents
            or bool(set(a.parents) & set(b.parents)))


def free(c: Character, characters) -> bool:
    """Unpartnered, or widowed. The record of whom a villager married stays
    when its partner dies (hearthwick/mortality.py), and leaves it free to
    marry again."""
    p = characters.get(c.partner) if c.partner else None
    return p is None or not p.alive


def of_age(c: Character, elders: bool = False) -> bool:
    """Old enough to court and marry: an adult, or an elder too with the wider
    window (``SimConfig.fertility``, SPECIFICATION.md section 2.9j), since an
    elder may have children then and a widow may marry again."""
    return c.stage == "adult" or (elders and c.stage == "elder")


def eligible(a: Character, b: Character, characters, elders: bool = False) -> bool:
    """A man and a woman, free adults who live here (elders too with the wider
    window), not too far apart in age, and not close kin.

    The age gap has a little slack. Two villagers exactly six years apart
    age by the same small step every tick, and the rounding put them more
    than six apart from the first tick of a run."""
    return (a.id != b.id and a.alive and b.alive and not a.visitor and not b.visitor
            and of_age(a, elders) and of_age(b, elders)
            and free(a, characters) and free(b, characters)
            and {a.sex, b.sex} == {"male", "female"}
            and abs(a.age - b.age) <= MAX_AGE_GAP + 1e-6 and not kin(a, b))


class Courtship:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.affinity: dict[tuple[str, str], float] = {}
        self.proposals: dict[str, tuple[str, int]] = {}      # asked -> (asker, tick)
        self.declined: dict[tuple[str, str], int] = {}       # (asker, asked) -> day
        self.waiting: list[tuple[str, str]] = []             # couples with no home yet

    # -- affinity ---------------------------------------------------------

    def of(self, a: str, b: str) -> float:
        return self.affinity.get(pair(a, b), 0.0)

    def _add(self, a: Character, b: Character, amount: float) -> None:
        if a.visitor or b.visitor or "infant" in (a.stage, b.stage):
            return
        key = pair(a.id, b.id)
        self.affinity[key] = self.affinity.get(key, 0.0) + amount

    def conversed(self, a: Character, b: Character) -> None:
        self._add(a, b, PER_CONVERSATION)

    def hour_together(self) -> None:
        """Called once an in-game hour: everyone awake near someone grows fonder."""
        near = self.sim.config.near_radius
        people = [c for c in self.sim.characters.values()
                  if c.alive and not c.resting and not c.visitor and c.stage != "infant"]
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                if distance(a.pos, b.pos) <= near:
                    self._add(a, b, PER_HOUR_NEAR)

    def new_day(self) -> None:
        self.affinity = {k: v * (1 - DAILY_DECAY) for k, v in self.affinity.items()
                         if v * (1 - DAILY_DECAY) > 0.05}
        self.proposals = {k: v for k, v in self.proposals.items() if self._stands(v[1])}

    def fondest(self, limit: int = 10) -> list[list]:
        """The eligible pairs fondest of each other, for the dawn record."""
        chars = self.sim.characters
        pairs = [[a, b, round(v, 2)] for (a, b), v in self.affinity.items()
                 if a in chars and b in chars and eligible(chars[a], chars[b], chars, self.elders)]
        return sorted(pairs, key=lambda p: (-p[2], p[0], p[1]))[:limit]

    # -- who, to whom ----------------------------------------------------

    def candidates(self, c: Character) -> list[tuple[float, Character]]:
        chars = self.sim.characters
        return sorted(((self.of(c.id, o.id), o) for o in chars.values()
                       if eligible(c, o, chars, self.elders)),
                      key=lambda x: (-x[0], x[1].id))

    def sweetheart(self, c: Character) -> Character | None:
        best = self.candidates(c)
        return best[0][1] if best and best[0][0] >= SWEETHEART else None

    def _stands(self, asked_at: int) -> bool:
        clock = self.sim.clock
        return clock.tick - asked_at < PROPOSAL_DAYS * clock.ticks_per_day

    def pending_for(self, c: Character) -> str | None:
        """Who has asked this villager, if the question still stands."""
        asked = self.proposals.get(c.id)
        return asked[0] if asked is not None and self._stands(asked[1]) else None

    @property
    def elders(self) -> bool:
        """Elders court too, with the wider fertile window."""
        return bool(getattr(self.sim.config, "fertility", False))

    def asking(self, c: Character) -> bool:
        return any(asker == c.id and self._stands(t) for asker, t in self.proposals.values())

    def tags(self, c: Character) -> list[str]:
        out = []
        if not of_age(c, self.elders) or not free(c, self.sim.characters) or c.visitor:
            return out
        # The courting instructions are gated on this rather than on being an
        # adult, so an elder can court when the window is wide.
        out.append("marriageable")
        s = self.sweetheart(c)
        if s is not None:
            out.append("courting")
            if distance(s.pos, c.pos) <= self.sim.config.near_radius and not s.resting:
                out.append("sweetheart_near")
            if self.of(c.id, s.id) >= PROPOSE:
                out.append("fond_enough")
        asker = self.pending_for(c)
        if asker is not None:
            out.append("proposed_to")
            best = self.candidates(c)
            if best and best[0][1].id != asker and best[0][0] > self.of(c.id, asker):
                out.append("prefers_another")
            if self.of(c.id, asker) < KNOWN_WELL:
                out.append("hardly_knows_asker")
        return out

    # -- what can be done (read-only, for the handlers) ------------------

    def can_propose(self, c: Character) -> Character | None:
        s = self.sweetheart(c)
        if s is None or self.of(c.id, s.id) < PROPOSE:
            return None
        if self.pending_for(c) or self.pending_for(s) or self.asking(c) or self.asking(s):
            return None
        last = self.declined.get((c.id, s.id))
        if last is not None and self.sim.clock.day - last < DECLINED_COOLDOWN_DAYS:
            return None
        return s

    def can_answer(self, c: Character) -> Character | None:
        asker_id = self.pending_for(c)
        asker = self.sim.characters.get(asker_id) if asker_id else None
        return (asker if asker is not None and eligible(c, asker, self.sim.characters, self.elders)
                else None)

    # -- carried out (in the simulation step, not in a handler) ----------

    def propose(self, c: Character, target_id: str, tick: int) -> None:
        target = self.sim.characters.get(target_id)
        if target is None or self.can_propose(c) is not target:
            return
        self.proposals[target.id] = (c.id, tick)
        self.sim.log.event(tick, "proposed", asker=c.id, asked=target.id,
                           affinity=round(self.of(c.id, target.id), 2))

    def decline(self, c: Character, tick: int) -> None:
        asker = self.can_answer(c)
        if asker is None:
            return
        self.proposals.pop(c.id, None)
        self.declined[(asker.id, c.id)] = self.sim.clock.day
        self.sim.log.event(tick, "declined", asker=asker.id, asked=c.id,
                           affinity=round(self.of(c.id, asker.id), 2))

    def accept(self, c: Character, tick: int) -> None:
        asker = self.can_answer(c)
        if asker is None:
            return
        self.proposals.pop(c.id, None)
        c.partner, asker.partner = asker.id, c.id
        home = self._home_for(c, asker)
        self.sim.log.event(tick, "married", asker=asker.id, asked=c.id, home=home,
                           waiting=(pair(c.id, asker.id) in self.waiting),
                           affinity=round(self.of(c.id, asker.id), 2))
        # Whoever was near when it was said knows first, the couple among them.
        sim = self.sim
        for spouse in (asker, c):
            if hasattr(sim, "regrow_persona"):
                sim.regrow_persona(spouse)
        here = sim.world.place_at(c.pos)
        sim.diffuser.witness("wedding", here.id if here else None, sim._nearest_to(c.pos),
                             {"topic": f"{asker.name} and {c.name}"}, tick,
                             root=f"wedding:{pair(c.id, asker.id)[0]}:{tick}")

    # -- where they live ---------------------------------------------------

    def residents(self, home: str) -> list[Character]:
        return [o for o in self.sim.characters.values()
                if o.alive and not o.visitor and o.home == home]

    def _home_for(self, a: Character, b: Character) -> str:
        """An empty home if there is one, else whichever of their homes has
        fewer others in it. If others live there too, the couple waits for a
        house of their own, and the village needs one built."""
        world = self.sim.world
        empty = sorted(p.id for p in world.places.values()
                       if p.kind == "home" and not self.residents(p.id))
        if empty:
            a.home = b.home = empty[0]
            return empty[0]

        def others(h: str) -> int:
            return sum(1 for o in self.residents(h) if o.id not in (a.id, b.id))

        home = min((a.home, b.home), key=lambda h: (others(h), h))
        crowded = others(home) > 0
        a.home = b.home = home
        if crowded:
            self.waiting.append(pair(a.id, b.id))
        return home

    def settle(self, couple: tuple[str, str], home: str) -> None:
        """A waiting couple moves into a house built for them, with their children."""
        chars = self.sim.characters
        for cid in couple:
            chars[cid].home = home
        for o in chars.values():
            if o.alive and set(couple) <= set(o.parents) and o.stage in ("infant", "child"):
                o.home = home
        if couple in self.waiting:
            self.waiting.remove(couple)

    # -- checkpoints -----------------------------------------------------

    def to_dict(self) -> dict:
        return {"affinity": [[a, b, v] for (a, b), v in self.affinity.items()],
                "proposals": {k: list(v) for k, v in self.proposals.items()},
                "declined": [[a, b, d] for (a, b), d in self.declined.items()],
                "waiting": [list(c) for c in self.waiting]}

    def load(self, d: dict) -> None:
        self.affinity = {(a, b): v for a, b, v in d.get("affinity", [])}
        self.proposals = {k: (v[0], v[1]) for k, v in d.get("proposals", {}).items()}
        self.declined = {(a, b): day for a, b, day in d.get("declined", [])}
        self.waiting = [tuple(c) for c in d.get("waiting", [])]
