"""Placements: where the young learn, from whom, and what they become.

School and apprenticeship are one mechanism at two stages. A placement is a
learner, a place and a teacher.

    child        a pupil at the schoolyard, taught by an elder
    apprentice   at a master's workplace, in a trade it chose
    adult        practising that trade, as its role

A child graduates when it meets the child gate, which includes enough hours
at school (``GATES["child"].school``). It then carries ``graduating`` until
it chooses a trade. Choosing is retrieval, not code: each trade has an
instruction carrying ``[!apprentice(trade=...)]``, and soft tags say what a
graduate leans toward (its temperament, a parent's trade, where it has spent
its time, what the village lacks). The handler finds the master it is
fondest of among those with room, and with no fondness to go on a parent in
that trade first and otherwise the practitioner with the fewest apprentices.
A trade with no free master is refused, and feasibility re-ranking passes to
the next. An apprentice qualifies when its skill in its trade reaches
``GATES["apprentice"].trade_skill``, and becomes an adult with the trade as
its role.

Skill is practice at a place, in levels (hearthwick/growth.py). It grows
faster with the master working at the same place, and it scales what work
produces. So far only the fields produce anything.
"""

from __future__ import annotations

from hearthwick.growth import MAX_SKILL, SCHOOL, TICKS_PER_LEVEL

MAX_APPRENTICES = 2          # a master takes on no more than this at a time
MASTER_SPEEDUP = 2           # practice counts double beside one's master
# The trades a working village is made of, by weight. The village generator
# assigns founders' roles from these, and a trade with fewer practitioners
# than its share of the working village is `needed_<trade>`.
TRADE_WEIGHTS = {"farmer": 8, "crafter": 3, "merchant": 3,
                 "guard": 2, "healer": 2, "storyteller": 1}


def output_factor(level: int) -> float:
    """What a villager's work yields, against the base rate: half at level 0,
    the base rate at level 2 or 3, and half again at the top."""
    return 0.5 + 0.2 * max(0, min(MAX_SKILL, level))


def level_at(c, site: str | None) -> int:
    return c.growth.skills.get(site, 0) if site else 0


def site_of(trade: str | None, world) -> str | None:
    return world.role_sites.get(trade) if trade else None


def working(characters) -> list:
    """Residents of working age, not visitors."""
    return [c for c in characters.values() if c.alive and not c.visitor
            and c.stage in ("adult", "elder")]


def practitioners(trade: str, characters) -> list:
    return [c for c in working(characters) if c.role == trade]


def apprentices_of(master_id: str, characters) -> list:
    return [c for c in characters.values() if c.alive and c.stage == "apprentice"
            and c.mentor == master_id]


def find_master(c, trade: str, characters, fondness=None) -> str | None:
    """Of the masters in the trade with room for another apprentice, the one
    the graduate is fondest of.

    Fondness is what courtship measures between any two villagers, grown by
    conversations and time spent near each other (hearthwick/courtship.py).
    A child who spends its afternoons at the mill seeks out the miller. A
    parent wins only if the child is fondest of it. In the 40-day development
    run none did: four graduates had a parent in the trade they chose, with
    room for an apprentice, and each went to someone it had grown fonder of,
    two of them to elders who teach at the school. With no fondness to go on,
    a parent comes first, then whoever has the fewest apprentices.
    """
    free = [m for m in practitioners(trade, characters)
            if len(apprentices_of(m.id, characters)) < MAX_APPRENTICES]
    if not free:
        return None
    fond = fondness or (lambda a, b: 0.0)
    return min(free, key=lambda m: (-fond(c.id, m.id), m.id not in c.parents,
                                    len(apprentices_of(m.id, characters)), m.id)).id


def needed(characters) -> set[str]:
    """Trades with fewer practitioners than their share of the working village."""
    workers = len(working(characters))
    total = sum(TRADE_WEIGHTS.values())
    return {t for t, w in TRADE_WEIGHTS.items()
            if len(practitioners(t, characters)) < max(1, round(w / total * workers))}


def tags(c, characters, world, food_tags=()) -> list[str]:
    """What a young villager sees of its own path."""
    out = []
    if c.stage == "apprentice" and not c.trade:
        out.append("graduating")
        short = needed(characters)
        if "food_low" in food_tags or "fields_small" in food_tags:
            short.add("farmer")
        out += [f"needed_{t}" for t in sorted(short)]
        out += sorted({f"parent_{characters[p].role}" for p in c.parents
                       if p in characters and characters[p].role})
        out += [f"skill_{site}" for site, level in sorted(c.growth.skills.items())
                if level >= 1 and site != SCHOOL]
    return out


def founding_practice(c, world, characters) -> dict[str, int]:
    """The practice a founder has behind it when the run begins.

    A founder is not new to its life. An adult has worked its trade since it
    qualified, so it starts at level 2 at 11 years and rises a level every
    three, to the top. An apprentice has been at its master's side since six.
    A child has been at school since three.
    """
    if c.stage in ("adult", "elder") and c.role:
        level = MAX_SKILL if c.stage == "elder" else min(MAX_SKILL, 2 + int(c.age - 11) // 3)
        site = site_of(c.role, world)
        return {site: level * TICKS_PER_LEVEL} if site else {}
    if c.stage == "apprentice":
        master = characters.get(c.mentor) if c.mentor else None
        site = site_of(master.role if master else None, world)
        return {site: max(0, int((c.age - 6) * 80))} if site else {}
    if c.stage == "child":
        return {SCHOOL: max(0, int((c.age - 3) * 60))}
    return {}
