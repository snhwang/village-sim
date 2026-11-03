"""Growing up, on three tracks, with no forced promotion.

A villager advances a life stage only by meeting every requirement: an age, and
thresholds on what it knows, what it can do, and what it has lived through. One
that reaches the age without the rest stays where it is, keeps ageing, and can
die a child. Late bloomers and people who never grow up are part of the story,
not an error, so every refusal records which track fell short.

The three tracks are counted rather than awarded, and each is shaped to resist
the obvious way of gaming it:

  knowledge    distinct root events held, not facts held. Hearing the same
               rumour six times is one thing known, which is why a store that
               reinforces rather than duplicates matters here
  skill        practice at a place, in levels. Rises from working, so it is
               earned by what a villager chose to do rather than fixed at birth
  experience   distinct kinds of thing lived through, with diminishing returns
               within a kind. Two raids are worth more than one and much less
               than twice one, so grinding a single activity does not advance

Stage tags are swapped on advancement, which is the whole mechanism: a new
stage makes a different part of the corpus retrievable and the villager starts
behaving differently because different instructions are now in reach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

STAGES = ("infant", "child", "apprentice", "adult", "elder")

# Ticks of work at one site before a level. Deliberately coarse: a skill is
# meant to take in-game days, not an afternoon.
TICKS_PER_LEVEL = 120
MAX_SKILL = 5
SCHOOL = "schoolyard"


@dataclass(frozen=True)
class Gate:
    """What a villager must have to leave a stage."""

    to: str
    min_age: float
    knowledge: int
    experience: int
    best_skill: int = 0
    school: int = 0          # level of schooling to graduate (hours at the schoolyard)
    trade_skill: int = 0     # level in one's own trade to qualify

    def unmet(self, growth: Growth, age: float, site: str | None = None) -> list[str]:
        """Which requirements fall short, in words, or an empty list.

        ``site`` is where the villager's trade is worked, for a gate that asks
        for skill in it.
        """
        missing = []
        if age < self.min_age:
            missing.append(f"age {age:.1f} of {self.min_age}")
        if growth.knowledge < self.knowledge:
            missing.append(f"knowledge {growth.knowledge} of {self.knowledge}")
        if growth.experience < self.experience:
            missing.append(f"experience {growth.experience} of {self.experience}")
        if self.best_skill and growth.best_skill < self.best_skill:
            missing.append(f"skill {growth.best_skill} of {self.best_skill}")
        if self.school:
            have = growth.skills.get(SCHOOL, 0)
            if have < self.school:
                missing.append(f"school {have} of {self.school}")
        if self.trade_skill:
            if site is None:
                missing.append("skill: no trade chosen")
            elif growth.skills.get(site, 0) < self.trade_skill:
                missing.append(f"skill {growth.skills.get(site, 0)} of {self.trade_skill} "
                               f"at {site}")
        return missing


# Starting values. Tuned so most of a cohort reaches adulthood and some do not:
# gates set too high shrink the village, since only adults can partner.
#
# A child graduates from school, and an apprentice qualifies in its own trade
# (hearthwick/trades.py). Before trades, the apprentice gate asked for skill 2
# anywhere, and a new adult had no trade to go to.
GATES = {
    # An infant becomes a child at two, the age of the youngest founder
    # children, whatever it knows. It has no school to leave yet.
    "infant": Gate(to="child", min_age=2, knowledge=0, experience=0),
    "child": Gate(to="apprentice", min_age=4, knowledge=3, experience=4, school=1),
    "apprentice": Gate(to="adult", min_age=7, knowledge=6, experience=10, trade_skill=2),
    "adult": Gate(to="elder", min_age=20, knowledge=12, experience=25),
}


@dataclass
class Growth:
    """What one villager has accumulated, and how it got there."""

    roots: set[str] = field(default_factory=set)          # distinct events known
    lived: dict[str, int] = field(default_factory=dict)   # kind -> times lived
    practice: dict[str, int] = field(default_factory=dict)  # site -> ticks worked
    advanced: list[dict] = field(default_factory=list)    # a record per stage change

    # -- the three tracks ---------------------------------------------------

    @property
    def knowledge(self) -> int:
        """Distinct events known about, not sentences held."""
        return len(self.roots)

    @property
    def experience(self) -> int:
        """Distinct kinds lived through, with diminishing returns inside a kind.

        The first of anything counts fully; the tenth barely registers. A
        villager who only ever works the fields does not become experienced by
        working them harder.
        """
        return int(sum(1 + math.log2(n) for n in self.lived.values() if n > 0))

    @property
    def skills(self) -> dict[str, int]:
        return {site: min(MAX_SKILL, ticks // TICKS_PER_LEVEL)
                for site, ticks in self.practice.items()}

    @property
    def best_skill(self) -> int:
        return max(self.skills.values(), default=0)

    # -- accumulating -------------------------------------------------------

    def learned(self, root: str) -> None:
        self.roots.add(root)

    def lived_through(self, kind: str) -> None:
        self.lived[kind] = self.lived.get(kind, 0) + 1

    def practised(self, site: str, ticks: int = 1) -> None:
        self.practice[site] = self.practice.get(site, 0) + ticks

    def to_dict(self) -> dict:
        return {"knowledge": self.knowledge, "experience": self.experience,
                "skills": self.skills, "best_skill": self.best_skill,
                "lived": dict(self.lived), "advanced": list(self.advanced)}


def check(stage: str, growth: Growth, age: float,
          site: str | None = None) -> tuple[str | None, list[str]]:
    """The next stage if every requirement is met, and what is missing if not.

    Returns ``(None, [])`` for an elder, who has nowhere further to go, and
    ``(None, reasons)`` for anyone held back -- so a villager who never grows up
    can be asked why.
    """
    gate = GATES.get(stage)
    if gate is None:
        return None, []
    missing = gate.unmet(growth, age, site)
    return (None, missing) if missing else (gate.to, [])
