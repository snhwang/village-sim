"""The world decides too.

Weather, raiders, travelers and sickness are not scheduled. They are retrieved,
by an agent whose context is the village's history: the season, how long since
rain, the last harvest, whether anyone has walked the east road. The deciding is
BEAR; the raining is physics (:mod:`hearthwick.sim`), and the villagers then
respond to the weather through their own retrieval.

It shares the corpus and retriever with the villagers. Its instructions are
gated on ``world``, which no villager context carries, and it carries no
character, stage or role tag, so neither can retrieve the other's instructions.

It decides twice a day, with a different focus each time. At dawn it decides
the sky, and then it decides whether anything happens. Weather happens every
day, so when the two shared one decision the weather took about a third of all
days, and a day spent deciding the weather produced no news. Weather is never
told, so the village had less to talk about than the world had to say. The
focus is a context tag, `sky` or `happening`, and each world instruction
requires one, so the split happens before retrieval rather than after it.

A weather system with a memory, not a puppeteer.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from bear import Context, MarkerAction, MarkerRegistry, ScoredInstruction, parse_actions

from hearthwick.brain import Decision
from hearthwick.food import Food
from hearthwick.world import SEASONS, Clock  # noqa: F401  (SEASONS re-exported)

# What the world decides about, one decision each per day.
FOCI = ("sky", "happening")

DRY_SPELL_DAYS = 3
WEATHERS = ("clear", "rain", "storm", "frost")

# How long an event stays in force. Without these the world is a ratchet: a
# well that sickens is sick for ever, raiders never come twice, and the set of
# events that are not already in force shrinks every day until only the one
# handler that never refuses is left. Measured on a ten-day run, that produced
# six travelers out of nine events.
SICKNESS_DAYS = 4       # bad water passes, and can turn again later
HAZARD_DAYS = 5         # a raided road stops being news
NEWS_FRESH_DAYS = 2     # a second traveler while the last one is still being
                        # talked about tells the village nothing new
FESTIVAL_RECENT_DAYS = 2  # a gathering the day after a gathering. Once the sky
                        # had its own decision, festivals fired on consecutive
                        # days in four of six seeds, and a festival is never
                        # told, so each repeat was a day with no news

# How busy a place has to be before the world notices, as a share of the living
# village rather than a count of heads.
#
# These were absolute counts -- three on the road, four at the well, two in the
# fields -- calibrated for the ten-villager village. At thirty they are all
# exceeded every single day: road_watched fired on 54 of 54 world decisions,
# well_busy on 52. A tag that is always present cannot tell one day from
# another, so the world's perception collapsed to a constant, its query stopped
# varying, and the raider instruction -- whose precondition was an empty road --
# became unreachable at the size the evaluation had just moved to.
#
# A threshold on how busy somewhere is belongs in proportion to how many people
# there are to make it busy.
ROAD_WATCHED_SHARE = 0.30    # was 3 of about 10
WELL_BUSY_SHARE = 0.40       # was 4 of about 10
FIELDS_WORKED_SHARE = 0.20   # was 2 of about 10

# Whether the fields were worked is judged on the busiest of the last few
# days, not on yesterday alone. A good harvest needs the fields well watered
# and well worked, and well watered means rain yesterday or today. On a rainy
# day villagers shelter, so yesterday's fields were empty whenever the rain
# had come, and in six ten-day runs the two tags never met. Rain does not undo
# the work done before it.
FIELDS_WORKED_DAYS = 3


def season_of(clock: Clock) -> str:
    return clock.season


@dataclass
class WorldState:
    """What the world remembers about the village."""

    weather: str = "clear"
    weather_until: int = 0
    days_since_rain: int = 0
    last_harvest: str | None = None
    last_harvest_year: int | None = None
    festival_day: int | None = None
    last_traveler_day: int | None = None
    sick_places: dict[str, int] = field(default_factory=dict)  # place -> day it turned
    fought: dict[str, float] = field(default_factory=dict)     # place -> worker-ticks against it
    hazards: dict[str, int] = field(default_factory=dict)   # place -> tick it appeared
    # counted daily from what the villagers actually did
    # who did what today, by character, so "the road was walked" counts
    # villagers rather than ticks spent standing on it
    road_walkers: set[str] = field(default_factory=set)
    well_drawers: set[str] = field(default_factory=set)
    field_workers: set[str] = field(default_factory=set)
    yesterday: dict = field(default_factory=lambda: {"road": 0, "well": 0, "fields": 0})
    fields_recent: list[int] = field(default_factory=list)   # field workers per day, oldest first
    food: Food = field(default_factory=Food)    # the granary and the standing crop
    visitors_here: list[str] = field(default_factory=list)   # visitors staying now
    last_visitor_day: int | None = None       # when the last one left

    def festival_recent(self, day: int) -> bool:
        return self.festival_day is not None and day - self.festival_day <= FESTIVAL_RECENT_DAYS

    def roll_day(self, day: int = 0, ticks_per_day: int = 144) -> list[tuple[str, str]]:
        self.yesterday = {"road": len(self.road_walkers), "well": len(self.well_drawers),
                          "fields": len(self.field_workers)}
        self.fields_recent = (self.fields_recent + [len(self.field_workers)])[-FIELDS_WORKED_DAYS:]
        self.road_walkers, self.well_drawers, self.field_workers = set(), set(), set()
        self.days_since_rain += 1
        return self.recover(day, ticks_per_day)

    def recover(self, day: int, ticks_per_day: int) -> list[tuple[str, str]]:
        """Let what the world did wear off, so it can do it again.

        Every world marker is refused while its effect is already in force,
        which is right -- the well cannot sicken twice running. But nothing
        lifted those effects, so each one was a one-way door and the world ran
        out of things to do.

        Returns what wore off, as (ending, place), for the simulation to tell
        when endings are news (config.news_ends).
        """
        ended: list[tuple[str, str]] = []
        for place, started in list(self.sick_places.items()):
            if day - started >= SICKNESS_DAYS:
                del self.sick_places[place]
                ended.append(("sickness_passed", place))
        # What was done against a sickness goes with it.
        self.fought = {p: w for p, w in self.fought.items() if p in self.sick_places}
        for place, tick in list(self.hazards.items()):
            if day * ticks_per_day - tick >= HAZARD_DAYS * ticks_per_day:
                del self.hazards[place]
                ended.append(("danger_passed", place))
        return ended

    def to_dict(self) -> dict:
        return {"weather": self.weather, "days_since_rain": self.days_since_rain,
                "last_harvest": self.last_harvest, "sick_places": sorted(self.sick_places),
                "last_traveler_day": self.last_traveler_day,
                "hazards": sorted(self.hazards), "yesterday": self.yesterday,
                "fields_recent": list(self.fields_recent), "food": self.food.to_dict(),
                "visitors_here": list(self.visitors_here),
                "last_visitor_day": self.last_visitor_day}


class WorldAgent:
    """Retrieves the day's sky, then the day's event, from the world's own corpus."""

    def __init__(self, retriever, registry: MarkerRegistry, clock: Clock, seed: int,
                 temperature: float = 0.0, population: int = 10):
        self.retriever = retriever
        self.registry = registry
        self.clock = clock
        self.seed = seed
        self.temperature = temperature
        self.population = max(1, population)   # kept current by the simulation
        self.state = WorldState()

    # -- perception ---------------------------------------------------------

    def context_tags(self) -> list[str]:
        s, clock = self.state, self.clock
        tags = ["world", f"season_{season_of(clock)}"]
        if s.days_since_rain >= DRY_SPELL_DAYS:
            tags.append("dry_spell")
        if s.days_since_rain >= DRY_SPELL_DAYS * 2:
            tags.append("unsettled")
        if s.last_harvest and s.last_harvest_year == clock.year:
            tags.append(f"harvest_{s.last_harvest}")   # this year's, not a memory
        if season_of(clock) == "autumn":
            tags.append("harvest_near")
        watched = max(1, round(ROAD_WATCHED_SHARE * self.population))
        if s.yesterday["road"] == 0:
            tags.append("road_unwatched")
        else:
            tags.append("road_quiet" if s.yesterday["road"] < watched else "road_watched")
        # "Few enough eyes on the road" covers both of the first two, because a
        # scope cannot say "not road_watched".
        if s.yesterday["road"] < watched:
            tags.append("road_untended")
        if s.yesterday["well"] >= max(1, round(WELL_BUSY_SHARE * self.population)):
            tags.append("well_busy")
        worked = max(s.fields_recent, default=0)
        if worked >= max(1, round(FIELDS_WORKED_SHARE * self.population)):
            tags.append("well_worked")
        elif worked == 0:
            tags.append("fields_neglected")
        if s.days_since_rain <= 1:
            tags.append("well_watered")
        if s.festival_recent(clock.day):
            tags.append("festival_recent")
        # Exactly one of these, the way the road tags work, so a precondition
        # can be written as a hard gate rather than as an absence.
        tags.append("news_fresh" if (s.last_traveler_day is not None
                                     and clock.day - s.last_traveler_day <= NEWS_FRESH_DAYS)
                    else "news_stale")
        if s.sick_places:
            tags.append("sickness_about")
        return sorted(tags)

    def situation(self) -> str:
        s = self.state
        parts = [f"It is {season_of(self.clock)}, day {self.clock.day} in the village."]
        parts.append("It has not rained for %d days." % s.days_since_rain
                     if s.days_since_rain > 1 else "It rained recently.")
        if s.last_harvest:
            parts.append(f"The last harvest was {s.last_harvest}.")
        y = s.yesterday
        parts.append("Nobody walked the east road yesterday." if y["road"] == 0
                     else f"{y['road']} villagers walked the east road yesterday.")
        parts.append(f"{y['fields']} worked the fields and {y['well']} drew from the well.")
        if s.sick_places:
            parts.append("Sickness lingers at " + ", ".join(sorted(s.sick_places)) + ".")
        return " ".join(parts)

    # -- decision -----------------------------------------------------------

    def decide(self, marker_context,
               focus: str = "happening") -> tuple[Decision, list[MarkerAction]]:
        if focus not in FOCI:
            raise ValueError(f"the world decides {FOCI}, not {focus!r}")
        tags = sorted(self.context_tags() + [focus])
        query = self.situation()
        # Every world instruction the gates admit, not a fixed top few, so
        # refused candidates can never crowd out one that could happen.
        scored = self.retriever.retrieve(query, Context(tags=tags),
                                         top_k=max(8, len(self.retriever.corpus)))

        pool = [s for s in scored if parse_actions(s.content)]
        chosen: ScoredInstruction | None = None
        actions: list[MarkerAction] = []
        # Which candidates the handlers refused, and why the world settled on
        # what it did. Without this a world that has run out of things it can
        # do looks identical in the log to one that wanted a traveler.
        refused: list[str] = []
        rng = random.Random(f"{self.seed}:world:{self.clock.day}:{focus}")
        remaining = list(pool)
        while remaining:
            candidate = self._sample(remaining, rng)
            _, actions = self.registry.process(candidate.content, context=marker_context)
            if actions:
                chosen = candidate
                break
            refused.append(candidate.id)
            remaining.remove(candidate)

        decision = Decision(
            tick=self.clock.tick, character="world", tags=tags, query=query,
            retrieved=[{"id": s.id, "score": round(s.final_score, 4),
                        "similarity": round(s.similarity, 4), "priority": s.priority,
                        "actionable": bool(parse_actions(s.content)),
                        "refused": s.id in refused} for s in scored],
            chosen=chosen.id if chosen else None,
            actions=[{"kind": a.kind, "data": a.data} for a in actions],
            by_score=max(pool, key=lambda s: s.final_score).id if pool else None,
            by_priority=(max(pool, key=lambda s: (s.priority, -pool.index(s))).id
                         if pool else None),
        )
        return decision, actions

    def _sample(self, pool: list[ScoredInstruction], rng: random.Random) -> ScoredInstruction:
        """One of the world's best candidates, the way a villager picks its own.

        The world used to take the top-scoring candidate outright. Its
        perception is coarse -- the road is unwatched, quiet or watched, and
        little else -- so different villager trajectories landed on the same
        tags, and every seed produced the same ten days. Seeds that cannot
        disagree are not replicates, which matters more for evaluation than it
        does for the village.
        """
        if self.temperature <= 0:
            return max(pool, key=lambda s: (s.final_score, s.priority, s.id))
        best = max(s.final_score for s in pool)
        weights = [math.exp((s.final_score - best) / self.temperature) for s in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
