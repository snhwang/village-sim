"""What every villager speaks from: the facts of its life, its village, what it
knows that bears on the moment, and how to conduct itself.

A villager's voice comes from the speech instructions it retrieves (its
temperament, role, stage, persona and the weather). Those say how it speaks,
not what is true of it. Without the truth of its own life and village, the
model fills the gaps. Asked about her parents, Mabel said they were "buried or
busy". Sten quoted an "Old Marta" nobody in the village had heard of, offered a
"northern road" to a village whose only road runs east, and asked a stranger
for the source of news he had given himself.

Every conversation prompt, between villagers or with a human, is built on this
foundation (hearthwick/conversation.py, hearthwick/player.py). All of it comes
from the simulation's state, so it is the villager's own data, like its
instructions.
"""

from __future__ import annotations

from hearthwick.conversation import STAGE_WORDS

# All the villagers are named when there are this few. Beyond it, only those
# a villager is close to: its household, its kin, its partner, its master and
# apprentices, and those it is fondest of.
NAME_EVERYONE_UP_TO = 40
FONDEST_NAMED = 15

CONDUCT = (
    "Answer what was actually said to you, and do not put words in anyone's "
    "mouth. Say only what you would know, and name only the people and places "
    "of Hearthwick given here. If you are asked about something your life and "
    "what you know do not tell you, say plainly that you do not know or do not "
    "remember, rather than making it up."
)

NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight"]


def manner(guidance: str) -> str:
    """The speech instructions a villager retrieved, framed as its character.

    Each instruction is written as a standing order ("You are suspicious...
    ask who told them"), one for each gene, the role, the stage and the
    weather. Handed over as a list, the model obeyed all of them in every
    line: "who told you?" and the rain turned up in nearly everything anyone
    said. A character shows itself where it fits, not all at once.
    """
    return ("Your character. Let it show where it fits, not all at once and not "
            f"in every line:\n{guidance}")


def life(sim, c) -> str:
    """The facts of a villager's own life, from the simulation's state."""
    chars = sim.characters
    out = []
    partner = chars.get(c.partner) if c.partner else None
    if partner is not None:
        out.append(f"Your partner is {partner.name}." if partner.alive
                   else f"Your partner, {partner.name}, has died.")
    children = sorted((o for o in chars.values() if c.id in o.parents), key=lambda o: -o.age)
    if children:
        n = len(children)
        count = NUMBER_WORDS[n - 1] if n <= len(NUMBER_WORDS) else str(n)
        out.append(f"You have {count} {'child' if n == 1 else 'children'}: " + ", ".join(
            f"{o.name}, {'who has died' if not o.alive else STAGE_WORDS[o.stage]}"
            for o in children) + ".")
    parents = [chars[p] for p in c.parents if p in chars]
    if parents:
        out.append("Your parents are " + " and ".join(
            p.name + ("" if p.alive else ", who has died") for p in parents) + ".")
    else:
        # A founder came with no parents in the village. That they live
        # elsewhere is the least it implies: "not in Hearthwick" was taken as
        # having no parents at all.
        out.append("Your parents live elsewhere, outside Hearthwick.")
    household = [o.name for o in chars.values() if o.alive and not o.visitor
                 and o.home == c.home and o.id != c.id]
    if household:
        out.append("You live with " + ", ".join(household) + ".")
    master = chars.get(c.mentor) if c.mentor else None
    if master is not None:
        learning = "are learning" if c.stage == "apprentice" else "learned"
        out.append(f"You {learning} your trade from {master.name}"
                   + ("." if master.alive else ", who has died."))
    # Where it works, so a merchant standing in the fields does not call them
    # "my fields".
    site = sim.world.role_sites.get(c.role) if c.role else None
    if site in sim.world.places:
        out.append(f"Your work is at {sim.world.places[site].name}.")
    return " ".join(out)


def places(sim) -> str:
    """The village's places by name, the homes as one."""
    all_places = sim.world.places.values()
    named = sorted(p.name for p in all_places if p.kind not in ("home", "site"))
    homes = sum(1 for p in all_places if p.kind == "home")
    return ", ".join(named + [f"{homes} houses"])


def people(sim, c) -> str:
    """The villagers it can name: everyone in a small village, and in a large
    one those it is close to."""
    chars = sim.characters
    residents = [o for o in chars.values() if o.alive and not o.visitor and o.id != c.id]
    if len(residents) <= NAME_EVERYONE_UP_TO:
        known = residents
    else:
        close = {o.id for o in residents
                 if o.home == c.home or o.id in c.parents or c.id in o.parents
                 or o.id == c.partner or o.id == c.mentor or o.mentor == c.id}
        court = getattr(sim, "courtship", None)
        if court is not None:
            fondest = sorted(residents, key=lambda o: -court.of(c.id, o.id))[:FONDEST_NAMED]
            close |= {o.id for o in fondest if court.of(c.id, o.id) > 0}
        known = [o for o in residents if o.id in close]
    return ", ".join(sorted(f"{o.name} ({o.role or STAGE_WORDS[o.stage]})" for o in known))


def known(sim, c, about: str, limit: int = 3) -> str:
    """What it holds that bears most on ``about``, as lines for the prompt."""
    store = sim.diffuser.store_for(c.id)
    vector = None
    if sim.embedder is not None:
        try:
            vector = sim.embedder.embed_single(about, is_query=True)
        except Exception:  # noqa: BLE001 - recall falls back to recency
            vector = None
    return "\n".join(f"- {f.text}" for f in store.recall(vector, limit=limit, text=about))


def foundation(sim, c, about: str) -> str:
    """The block every conversation prompt carries."""
    out = [f"Your life: {life(sim, c)}",
           f"Hearthwick's places: {places(sim)}.",
           f"People of Hearthwick you know: {people(sim, c)}."]
    things = known(sim, c, about)
    if things:
        out.append(f"Things you know that may bear on it:\n{things}")
    return "\n\n".join(out)
