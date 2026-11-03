"""What each villager knows, and how it changes on the way between them.

The claim this project makes is that the instructions shaping how a character
speaks also shape what it keeps. So a fact is not copied from one villager to
another: the listener retrieves its own lens, rewrites what it heard through
that lens, and stores the rewrite — or discards it as something it already
knows or does not care about. Two villagers who hear the same thing end up
holding different sentences, and act on them differently.

Every stored fact carries where it came from: the world event at the root, the
entry it was rewritten from, who told it, and how many tellings ago. That chain
is a ``bear.provenance.Provenance`` record per hop, so "why does Nell believe
this?" is answerable from the log.

Affordance tags are the link back to behavior. Storing a fact adds tags like
``knows_sickness_well`` to the holder's context, so instructions gated on
knowing it become retrievable, and knowledge changes what the villager does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from bear.provenance import Provenance

# A closed vocabulary: an LLM that invents a kind is corrected to "news".
KINDS = ("hazard", "sickness", "opportunity", "news", "rumor")

# What a villager remembers of its own life, as against what it knows about the
# world. These never diffuse -- "I talked with Rosa about the well" is not news
# anyone else can be told -- and they carry no knows_ tag, because they are not
# knowledge about a place or a danger. They reach behaviour by being recalled
# into the situation a villager retrieves against.
#
# Before this existed a villager held only news: it could not remember a
# conversation it had just had, so two villagers could tell each other the same
# thing on consecutive days and neither would know.
# Roots of news from beyond the village: a storyteller's tale, or a
# traveller's word. With config.afar_news such news, and anything retold from
# it, is held as from afar.
AFAR_ROOTS = ("tale:", "traveler:")

# News from beyond the village about something that can come here: raiders,
# a sickness going round, wolves. With config.short_warnings such news is
# tagged CAN_COME where it is first heard, the tag passes on with every
# retelling, and held as from afar it sets knows_danger_coming rather than
# knows_<kind>_afar. Far-off news of anything else warns nobody.
CAN_COME = "can_come"
CAN_COME_TOPICS = ("fighting", "raider", "sickness", "wolves", "wolf")


def can_come(topic: str) -> bool:
    text = (topic or "").lower()
    return any(word in text for word in CAN_COME_TOPICS)


# How long, in years, an entry of each kind drives behaviour after it was
# learned or last lived again (config.news_fades). Rumours and sickness fade
# within a year, a hazard within two. Other kinds do not fade.
FADE_YEARS = {"rumor": 1.0, "sickness": 1.0, "hazard": 2.0}

# What a villager did or lived through itself. It is never offered and sets
# no knows_ tag.
EXPERIENCE_KINDS = ("met", "did", "told")

# How the world's events read as facts when someone witnesses them directly.
WITNESS_KINDS = {"raid": "hazard", "sicken": "sickness", "traveler": "news",
                 "festival": "news", "weather": "news", "harvest": "news",
                 "visitor": "news", "tale": "news", "birth": "news",
                 "wedding": "news", "house": "news", "death": "news",
                 "blight_cleared": "news",
                 "sickness_passed": "news", "danger_passed": "news"}
WITNESS_TEXT = {
    "raid": "Raiders came to {place}. I saw it myself.",
    "sicken": "Something at {place} has turned, and those near it are falling ill.",
    "sicken:well": "The water at {place} has turned. It is making people ill.",
    "sicken:fields": "A blight is on the crop at {place}. What it touches rots.",
    "sicken:mill": "The grain at {place} has gone bad in the sacks.",
    "traveler": "A traveler came up the east road with {topic}.",
    # A traveling storyteller's arrival, seen by whoever was near the road,
    # and the news the storyteller brings, which it holds as its own.
    "visitor": "A traveling storyteller came up the east road and is staying at the inn.",
    "tale": "On the road here I heard {topic}.",
    # A child born in the village, seen by whoever was home.
    "birth": "{topic}, was born at {place}.",
    # A couple agreeing to marry, seen by whoever was near, and a house the
    # crafters finished for a couple who had nowhere of their own.
    "wedding": "{topic} are to be married.",
    "house": "The crafters have finished a new house, {place}.",
    # A blight the villagers cut out of the fields together (section 2.9j).
    "blight_cleared": "The blight has been cut out of {place}.",
    # A sickness or a danger wearing off, told only with config.news_ends
    # (SPECIFICATION-memory.md section 9).
    "sickness_passed": "Whatever had turned at {place} has passed.",
    "sickness_passed:well": "The water at {place} is good again.",
    "sickness_passed:fields": "The blight at {place} has run its course.",
    "sickness_passed:mill": "The bad grain at {place} has been cleared out.",
    "danger_passed": "The trouble at {place} has passed, and people use it again.",
    # A villager dying of old age, known by morning to those it lived with.
    "death": "{topic} died in the night.",
    "festival": "The whole village gathered at {place} tonight.",
    # Weather and harvest were in WITNESS_KINDS but had no line here, and
    # witness() returns nothing without one, so two fifths of what the world
    # did could never become anything anyone knew. Ordinary weather still
    # cannot: rain is not news, and a village that gossips about clear skies
    # drowns the news that matters.
    "harvest:good": "The harvest is in at {place}, and it is a good one.",
    "harvest:poor": "The harvest at {place} came in thin this year.",
    "weather:storm": "A storm broke over the village and kept everyone indoors.",
    "weather:frost": "A hard frost came early and took what was in the fields.",
}


# What each ending ends: the news of a danger at the same place, by the kind
# of event at its root (config.news_ends, SPECIFICATION-memory.md section 9).
ENDINGS = {"blight_cleared": ("sicken",), "sickness_passed": ("sicken",),
           "danger_passed": ("raid",)}


def arrival_kinds(text: str) -> tuple[str, ...]:
    """The events in the village that would show a danger from beyond it had
    come here (config.false_alarms): raiders for fighting, a sickness for a
    sickness. Wolves have no event, so word of them is never borne out."""
    t = (text or "").lower()
    kinds = []
    if "fighting" in t or "raider" in t:
        kinds.append("raid")
    if "sickness" in t:
        kinds.append("sicken")
    return tuple(kinds)


def root_parts(root: str | None, fallback_tick: int) -> tuple[str, str, int]:
    """(kind, place, tick) of a root such as ``raid:east_road:1234``. A tale's
    root carries more after the tick, and a root without a tick takes
    ``fallback_tick``."""
    parts = (root or "").split(":")
    kind = parts[0] if parts else ""
    place = parts[1] if len(parts) > 1 else ""
    try:
        tick = int(parts[2].split("-")[0]) if len(parts) > 2 else fallback_tick
    except ValueError:
        tick = fallback_tick
    return kind, place, tick


def witness_line(event: str, data: dict) -> str | None:
    """The words for an event, which for some kinds depend on which one it was.

    A storm is worth telling and a clear sky is not, so weather and harvest are
    keyed on their own detail and fall back to nothing rather than to a generic
    line.
    """
    detail = data.get("kind") or data.get("yield") or data.get("place")
    if detail is not None and f"{event}:{detail}" in WITNESS_TEXT:
        return WITNESS_TEXT[f"{event}:{detail}"]
    return WITNESS_TEXT.get(event)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


@dataclass
class Fact:
    """One thing a villager holds, in that villager's own words."""

    id: str
    holder: str
    text: str
    kind: str
    place: str | None
    root: str                 # the world event (or seed) this descends from
    parent: str | None        # the entry it was rewritten from
    teller: str | None        # who said it; None when witnessed
    hop: int                  # tellings between the event and this holder
    tick: int
    reinforced: int = 1
    vector: np.ndarray | None = field(default=None, repr=False, compare=False)
    # What the entry is about beyond its kind, such as news of a danger that
    # can come here (config.short_warnings).
    tags: tuple[str, ...] = ()
    # News from beyond the village, held as from afar (config.afar_news).
    from_afar: bool = False
    # When its clock last restarted, by living it again. A hazard fades from
    # behaviour some time after this, or after tick if never (news_fades).
    refreshed: int | None = None

    @property
    def is_experience(self) -> bool:
        """Something this villager lived, rather than something it learned."""
        return self.kind in EXPERIENCE_KINDS

    @property
    def afar(self) -> bool:
        """Something read on the web, or told on from it. A page knows nothing
        of Hearthwick, so what it says is about somewhere else or how things go
        in general, never news of the village, however the telling words it."""
        return self.from_afar or self.root.startswith("web:")

    @property
    def tag(self) -> str | None:
        if self.is_experience:
            return None
        if self.afar:
            # Far off, but it could come here (config.short_warnings).
            if CAN_COME in self.tags:
                return "knows_danger_coming"
            return f"knows_{self.kind}_afar"
        return f"knows_{self.kind}_{slug(self.place)}" if self.place else f"knows_{self.kind}"

    def to_dict(self) -> dict:
        return {"id": self.id, "holder": self.holder, "text": self.text,
                "kind": self.kind, "place": self.place, "root": self.root,
                "parent": self.parent, "teller": self.teller, "hop": self.hop,
                "tick": self.tick, "reinforced": self.reinforced,
                # Only when set, so a record made without the new switches
                # reads exactly as before.
                **({"tags": list(self.tags)} if self.tags else {}),
                **({"from_afar": True} if self.from_afar else {}),
                **({"refreshed": self.refreshed} if self.refreshed is not None else {})}

    def provenance(self, decision: str, reason: str = "") -> Provenance:
        """One record per hop: who decided what about this fact, and why."""
        return Provenance(
            subject_kind="fact", subject_id=self.id, actor=self.holder,
            decision=decision, reason=reason,
            parents=[self.parent] if self.parent else [],
            context={"root": self.root, "teller": self.teller, "hop": self.hop,
                     "tick": self.tick, "kind": self.kind, "place": self.place},
        )


class KnowledgeStore:
    """One villager's facts, deduplicated against each other.

    Deduplication is why the dense embedder matters: "the well is bad" and "the
    water at the well turned" are the same news in different words, and a
    lexical score cannot tell that from an unrelated sentence.
    """

    def __init__(self, holder: str, duplicate_above: float = 0.85):
        self.holder = holder
        self.duplicate_above = duplicate_above
        self.facts: list[Fact] = []

    def __len__(self) -> int:
        return len(self.facts)

    def duplicate_of(self, vector: np.ndarray | None) -> tuple[Fact | None, float]:
        """The closest fact already held, if it is close enough to be the same."""
        if vector is None or not self.facts:
            return None, 0.0
        known = [f for f in self.facts if f.vector is not None]
        if not known:
            return None, 0.0
        matrix = np.vstack([f.vector for f in known])
        scores = matrix @ vector / (
            np.linalg.norm(matrix, axis=1) * np.linalg.norm(vector) + 1e-12)
        best = int(np.argmax(scores))
        return (known[best], float(scores[best])) if scores[best] >= self.duplicate_above \
            else (None, float(scores[best]))

    def add(self, fact: Fact) -> None:
        self.facts.append(fact)

    def clear(self) -> None:
        self.facts.clear()

    def reinforce(self, fact: Fact, refreshed: int | None = None) -> None:
        """Held again. ``refreshed`` restarts its clock, which only living it
        again does (diffusion._commit). Hearing it again does not, or warnings
        would keep one another alive, as they did in the open-ended run."""
        fact.reinforced += 1
        if refreshed is not None:
            fact.refreshed = refreshed

    def tags(self, now: int | None = None, fade: dict[str, int] | None = None) -> list[str]:
        """Its knows_ tags. With ``fade`` (ticks by kind) and ``now``, an entry
        of a fading kind older than its time, since it was learned or last
        lived again, sets none: still held and recalled, but no longer
        driving what the villager does (config.news_fades)."""
        def fresh(f: Fact) -> bool:
            if not fade or now is None or f.kind not in fade:
                return True
            since = f.refreshed if f.refreshed is not None else f.tick
            return now - since <= fade[f.kind]
        return sorted({f.tag for f in self.facts if f.tag and fresh(f)})

    def recall(self, vector: np.ndarray | None, limit: int = 2,
               text: str | None = None) -> list[Fact]:
        """The things this villager holds that bear most on the moment.

        Selection used to be by recency -- the last two facts, whatever they
        were about. A villager standing at the well would not bring to mind
        that the well is bad unless it had heard so in the last few minutes,
        even though it held the fact the whole time. Scoring its own entries
        against its situation fixes that.

        ``text`` is the words ``vector`` was made from. This store does not
        need them. One that asks BEAR does (hearthwick/memory.py).
        """
        def best(pool: list[Fact], want: int) -> list[Fact]:
            if want <= 0 or not pool:
                return []
            if vector is None:
                return sorted(pool, key=lambda f: -f.tick)[:want]
            scored = [f for f in pool if f.vector is not None]
            if not scored:
                return sorted(pool, key=lambda f: -f.tick)[:want]
            matrix = np.vstack([f.vector for f in scored])
            values = matrix @ vector / (
                np.linalg.norm(matrix, axis=1) * np.linalg.norm(vector) + 1e-12)
            order = np.argsort(values)[::-1][:want]
            return [scored[int(i)] for i in order]

        # News first. A villager holds far more memories of its own afternoons
        # than pieces of news -- 144 against 30 in a three-day run -- so scoring
        # them together buries the one thing that gates behaviour under an
        # endless supply of who it chatted to. Experience fills what is left.
        news = best([f for f in self.facts if not f.is_experience], limit)
        lived = best([f for f in self.facts if f.is_experience], limit - len(news))
        return news + lived

    def roots(self) -> set[str]:
        return {f.root for f in self.facts}

    def tellable(self, limit: int = 2) -> list[Fact]:
        """What this villager would bring up: hazards first, then recent news.

        Experience is excluded. What a villager did yesterday is not news, and
        letting it spread would put memories of one villager's afternoon into
        another villager's head as though it had lived them.

        A hazard elsewhere is not a hazard here, so what came from the web is
        brought up as news, whatever it warns of. Told first as hazards, the
        web's floods and wildfires crowded the village's own news out of
        talk and out of school in the live village of 2026-10-01.
        """
        order = {"hazard": 0, "sickness": 1, "opportunity": 2, "rumor": 3, "news": 4}
        news = [f for f in self.facts if not f.is_experience]
        return sorted(news, key=lambda f: (order.get("news" if f.afar else f.kind, 5),
                                           -f.tick))[:limit]

    def to_dicts(self) -> list[dict]:
        return [f.to_dict() for f in self.facts]
