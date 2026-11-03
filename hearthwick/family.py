"""Families: couples who have a child when they can support one.

Having a child is a decision, retrieved like any other. A couple at home
together may retrieve ``family-have-child``, which carries ``[!have_child]``,
and temperament and the moment tilt whether it wins. The handler then refuses
unless the couple can support a child:

- both are adults between ``FERTILE_AGES`` years old,
- both are at home, in the same home,
- the granary is not low (``food_low``),
- the house holds fewer than ``MAX_YOUNG`` infants and children,
- their youngest child is at least ``BIRTH_SPACING_YEARS`` old, and
- they have not already tried today.

Wanting a child is not having one that day. A couple tries at most once a
day, and a try succeeds with ``CONCEPTION_CHANCE``. Without it every couple of
age had a child on the first evening of a run, and again the moment the rules
next allowed. There is no pregnancy. When a try succeeds the child appears at
home. Its
two copies of every gene are bred from theirs with BEAR's ``breed``, one
copy from each, and what it expresses is its temperament. It starts as an
infant with an empty memory, and grows up like any other child.

Couples form by courtship (hearthwick/courtship.py). Death is not built.
"""

from __future__ import annotations

import random

from hearthwick.character import LOCI, TRAIT_PHRASES, Character
from hearthwick.genome import bred, diploid, phenotype

FERTILE_AGES = (11.0, 20.0)     # in-game years, from early adulthood to elderhood
# With the wider window (``SimConfig.fertility``, SPECIFICATION.md section
# 2.9j) an elder can have children too, to 40. The live village died out under
# the narrow one: its last children grew through 11 to 20 in a lean decade and
# had none, and nobody older could.
WIDE_FERTILE_AGES = (11.0, 40.0)
MAX_YOUNG = 3                   # infants and children under one roof
BIRTH_SPACING_YEARS = 1.0       # a year is eight in-game days
CONCEPTION_CHANCE = 0.2         # of a child, each day a couple tries, in an eight-day year


def conception_chance(days_per_year: int) -> float:
    """The chance a day's try succeeds, so that a year of trying gives the
    same odds whatever its length. In a year of 28 days, 0.2 a day made a
    child all but certain each year, against 0.83 in eight days."""
    if days_per_year == 8:
        return CONCEPTION_CHANCE
    return 1 - (1 - CONCEPTION_CHANCE) ** (8 / days_per_year)

# Names for children born in the village, apart from the founders' so a
# newborn never shares a founder's name.
NEWBORN_NAMES = {
    "male": ["Aldo", "Bertil", "Col", "Dag", "Eilif", "Frode", "Gunne", "Hakon",
             "Ivar", "Jory", "Kell", "Lorne", "Mads", "Nils", "Odd", "Per"],
    "female": ["Alda", "Brit", "Cilla", "Dagny", "Elin", "Frida", "Gerd", "Hedda",
               "Inga", "Jorun", "Kari", "Liv", "Maja", "Nora", "Oda", "Runa"],
}


def persona_now(c: Character, characters) -> str:
    """Who a villager born in Hearthwick is now, for its persona: what it
    does, whose child it is, how it is (in the words a temperament is put in
    elsewhere, character.TRAIT_PHRASES), who taught it its trade and whom it
    married. Written once at birth, a persona said only "a baby, born to ...",
    and the live village's grown villagers were told they were babies every
    time they spoke (2026-10-02). Names, not pronouns, as a visitor's has."""
    def name(cid: str | None) -> str:
        return characters[cid].name if cid in characters else str(cid)

    def a(word: str) -> str:
        return f"{'an' if word[:1] in 'aeiou' else 'a'} {word}"

    if len(c.parents) == 2:
        mother, father = name(c.parents[0]), name(c.parents[1])
        kin = f"{'son' if c.sex == 'male' else 'daughter'} of {mother} and {father}"
    else:
        mother = father = None
        kin = "born in Hearthwick"
    if c.stage == "infant":
        return (f"{c.name} is a baby, born to {mother} and {father}." if mother
                else f"{c.name} is a baby, born in Hearthwick.")
    trade = c.role or c.trade
    if c.stage == "child":
        who = f"{c.name} is a child of the village, {kin}, and goes to school."
    elif c.stage == "apprentice":
        who = (f"{c.name} is {a('apprentice ' + trade)}, {kin}, learning the trade from "
               f"{name(c.mentor)}." if trade and c.mentor else f"{c.name} is an apprentice, {kin}.")
    elif c.stage == "adult":
        who = (f"{c.name} is {a(trade)} of the village, {kin}." if trade
               else f"{c.name} is a grown villager with no trade yet, {kin}.")
    else:
        who = (f"{c.name} is one of the village's elders, {a(trade)} by trade, {kin}." if trade
               else f"{c.name} is one of the village's elders, {kin}.")
    traits = [TRAIT_PHRASES[c.temperament[locus]] for locus in LOCI
              if c.temperament.get(locus) in TRAIT_PHRASES]
    how = ""
    if traits:
        how = f" {c.name} " + (", ".join(traits[:-1]) + ", and " + traits[-1]
                               if len(traits) > 1 else traits[0]) + "."
    taught = (f" {name(c.mentor)} taught {c.name} the trade."
              if c.stage in ("adult", "elder") and trade and c.mentor else "")
    married = ""
    if c.partner:
        spouse = characters.get(c.partner)
        married = (f" {c.name} is married to {name(c.partner)}." if spouse is None or spouse.alive
                   else f" {c.name} was married to {name(c.partner)}, who has died.")
    return who + how + taught + married


def fertile(c: Character, wide: bool = False) -> bool:
    if not c.alive or c.visitor:
        return False
    if wide:
        return c.stage in ("adult", "elder") and WIDE_FERTILE_AGES[0] <= c.age <= WIDE_FERTILE_AGES[1]
    return c.stage == "adult" and FERTILE_AGES[0] <= c.age <= FERTILE_AGES[1]


def partner_of(c: Character, characters) -> Character | None:
    p = characters.get(c.partner) if c.partner else None
    return p if p is not None and p.alive else None


def at_home(c: Character, world) -> bool:
    place = world.place_at(c.pos)
    return place is not None and place.id == c.home


def home_together(c: Character, p: Character | None, world) -> bool:
    return p is not None and c.home == p.home and at_home(c, world) and at_home(p, world)


def young_at_home(home: str, characters) -> list[Character]:
    return [o for o in characters.values()
            if o.alive and o.home == home and o.stage in ("infant", "child")]


def youngest_of(c: Character, p: Character, characters) -> float | None:
    ages = [o.age for o in characters.values()
            if o.alive and c.id in o.parents and p.id in o.parents]
    return min(ages) if ages else None


def refusal(c: Character, characters, world, food_low: bool,
            day: int | None = None, wide: bool = False) -> str | None:
    """Why this couple cannot try for a child now, or None if they can."""
    p = partner_of(c, characters)
    if p is None:
        return "no partner"
    if day is not None and day in (c.tried_for_child, p.tried_for_child):
        return "already tried today"
    if not (fertile(c, wide) and fertile(p, wide)):
        return "not of age"
    if not home_together(c, p, world):
        return "not at home together"
    if food_low:
        return "the granary will not stretch to another"
    if len(young_at_home(c.home, characters)) >= MAX_YOUNG:
        return "the house is full"
    youngest = youngest_of(c, p, characters)
    if youngest is not None and youngest < BIRTH_SPACING_YEARS:
        return "too soon after the last"
    return None


def tags(c: Character, characters, world, wide: bool = False) -> list[str]:
    """What an adult sees of whether a family is possible now."""
    out = []
    if fertile(c, wide):
        out.append("fertile")
    if home_together(c, partner_of(c, characters), world):
        out.append("partner_home")
    return out


class Family:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.born = 0           # how many children, for names and seeds

    def _name(self, sex: str, rng: random.Random) -> tuple[str, str]:
        taken = {c.id for c in self.sim.characters.values()}
        free = [n for n in NEWBORN_NAMES[sex] if n.lower() not in taken]
        name = rng.choice(free) if free else f"{rng.choice(NEWBORN_NAMES[sex])}{self.born}"
        cid, n = name.lower(), 2
        while cid in taken:
            cid, n = f"{name.lower()}{n}", n + 1
        return name, cid

    def attempt(self, a: Character, b: Character, tick: int, food_low: bool) -> Character | None:
        """A couple tries for a child: once a day, and not always with one.

        Checked again here, since both partners can decide in the same tick
        before either has acted. Without that, couples had twins every time.
        """
        sim = self.sim
        day = sim.clock.day
        if refusal(a, sim.characters, sim.world, food_low, day,
                   sim.config.fertility) is not None:
            return None
        a.tried_for_child = b.tried_for_child = day
        couple = ":".join(sorted((a.id, b.id)))
        roll = random.Random(f"{sim.config.seed}:conceive:{couple}:{day}").random()
        conceived = roll < conception_chance(sim.clock.days_per_year)
        sim.log.event(tick, "tried_for_child", couple=sorted((a.id, b.id)), conceived=conceived)
        return self.birth(a, b, tick) if conceived else None

    def birth(self, a: Character, b: Character, tick: int) -> Character:
        """A child, at home, with one copy of every gene from each parent."""
        sim = self.sim
        mother, father = (a, b) if a.sex == "female" else (b, a)
        rng = random.Random(f"{sim.config.seed}:birth:{self.born}")
        self.born += 1
        sex = rng.choice(["male", "female"])
        name, cid = self._name(sex, rng)
        copies = bred(mother.genotype, father.genotype, cid, seed=rng.randrange(2 ** 31))
        c = Character(
            id=cid, name=name, sex=sex, age=0.0, stage="infant", role=None,
            home=mother.home, parents=[mother.id, father.id], partner=None, mentor=None,
            temperament=phenotype(diploid(copies, cid)),
            persona=f"{name} is a baby, born to {mother.name} and {father.name}.",
            genotype=copies)
        c.pos = mother.pos
        sim.join(c)
        sim.log.event(tick, "roster", characters=[c.profile()])
        sim.log.event(tick, "born", character=cid, mother=mother.id, father=father.id,
                      home=c.home, genotype=copies, temperament=c.temperament)
        # Who was home saw it happen, and it is news to everyone else.
        home = sim.world.places[c.home]
        present = sorted(o.id for o in sim.characters.values()
                         if o.alive and o.id != cid and o.stage != "infant"
                         and home.contains(*o.pos))
        sim.diffuser.witness("birth", c.home, present,
                             {"topic": f"{name}, the child of {mother.name} and {father.name}"},
                             tick)
        return c
