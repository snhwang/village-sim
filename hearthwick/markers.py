"""Village action markers.

Instructions name places and people symbolically (``home``, ``own``,
``nearby_child``). Handlers registered with BEAR's core ``MarkerRegistry``
resolve those names against the current world state. A marker that cannot be
resolved (a child has no workplace, nobody is nearby) returns ``None`` and is
dropped, so the brain falls through to its next candidate instruction.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from bear import (ActionMarker, MarkerAction, MarkerRegistry, coerce_enum,
                  coerce_int, parse_kv_args)

from hearthwick.character import Character
from hearthwick.world import Clock, World, distance

MAX_TICKS = 36


@dataclass
class MarkerContext:
    world: World
    clock: Clock
    character: Character
    characters: dict[str, Character]
    rng: random.Random
    near_radius: int
    # The news roots a villager holds, when the caller can say. A warning to
    # someone who already knows everything the warner does changes nothing.
    news: Callable[[str], set[str]] | None = None
    # What a villager remembers another having, because it told them or heard
    # it from them (config.told_memory). Given, it decides who has something to
    # learn in place of ``news``, which reads the other's own store.
    known_to: Callable[[str, str], set[str]] | None = None
    # A warning is a word to someone within reach, never an errand
    # (config.quick_warnings).
    quick_warnings: bool = False
    # Telling of news a topic names only to someone who has not had it from
    # the teller (config.novel_telling).
    novel_telling: bool = False
    # The news a warning is about, given the warner, the instruction that
    # chose it and its topic (config.fresh_warnings). Given, it takes the
    # place of ``news`` for warnings.
    warn_news: Callable[[str, object, str], set[str]] | None = None
    # The instruction whose markers are being resolved, set for each candidate.
    instruction: object = None
    # Whether two villagers already talked about a topic today, so the same
    # talk is had once a day (config.talk_once_a_day).
    talked_today: Callable[[str, str, str], bool] | None = None
    # Whether the granary will last to the next harvest. A couple who cannot
    # feed another child does not have one (hearthwick/family.py).
    food_low: bool = False
    # Who is fond of whom and who has asked whom (hearthwick/courtship.py),
    # and the village's timber and house going up (hearthwick/building.py).
    # Handlers only read them.
    courtship: object = None
    building: object = None


def _arg(marker: ActionMarker, key: str, pos: int = 0) -> str | None:
    args = parse_kv_args(marker.args_raw)
    return args.get(key, args.get(f"_pos_{pos}"))


def _ticks(marker: ActionMarker, default: int) -> int:
    n = coerce_int(_arg(marker, "ticks", 1), default=default)
    return max(1, min(MAX_TICKS, n))


def _others(ctx: MarkerContext) -> list[Character]:
    return [o for o in ctx.characters.values() if o.alive and o.id != ctx.character.id]


def _occupancy(ctx: MarkerContext, place_id: str) -> int:
    place = ctx.world.places[place_id]
    return sum(1 for o in _others(ctx) if place.contains(*o.pos))


def resolve_place(name: str | None, ctx: MarkerContext) -> str | None:
    place = _resolve_place(name, ctx)
    # A villager who decided to avoid somewhere will not then choose to go
    # there: the marker simply fails to resolve and the next candidate is tried.
    if place and place in ctx.character.avoiding and name != "place":
        return None
    return place


def _resolve_place(name: str | None, ctx: MarkerContext) -> str | None:
    c, world = ctx.character, ctx.world
    if not name:
        return None
    if name == "home":
        return c.home
    if name == "own":
        return world.role_sites.get(c.role) if c.role else None
    if name == "mentor":
        mentor = ctx.characters.get(c.mentor) if c.mentor else None
        if mentor is None or not mentor.alive or not mentor.role:
            return None
        return world.role_sites.get(mentor.role)
    if name == "usual_place":
        return resolve_place("own", ctx) or c.home
    if name == "quiet_place":
        options = ["shrine", "forest_edge", c.home]
        ctx.rng.shuffle(options)
        return min(options, key=lambda p: _occupancy(ctx, p))
    if name == "unvisited_place":
        here = world.place_at(c.pos)
        options = sorted(
            p.id for p in world.places.values()
            if p.kind != "home" and p.id not in c.visited_today and (here is None or p.id != here.id)
        )
        return ctx.rng.choice(options) if options else None
    if name == "random_home":
        homes = sorted({o.home for o in _others(ctx)} - {c.home})
        return ctx.rng.choice(homes) if homes else None
    if name == "site":
        site = ctx.building.site if ctx.building is not None else None
        return site.id if site is not None else None
    return name if name in world.places else None


def resolve_target(name: str | None, ctx: MarkerContext,
                   also: Callable[[Character], bool] | None = None) -> str | None:
    """Who a marker means. ``also`` narrows it, for a marker that only makes
    sense toward some people. An alias such as ``nearby`` then looks past the
    nearest villager to the nearest one who qualifies."""
    c = ctx.character
    if not name:
        return None
    if also is not None and not name.startswith("nearby"):
        found = resolve_target(name, ctx)
        return found if found is not None and also(ctx.characters[found]) else None

    def nearest(pred) -> str | None:
        # Nobody tells news to a baby, plays tag with one, or follows one.
        candidates = [
            o for o in _others(ctx)
            if o.stage != "infant" and pred(o) and (also is None or also(o))
            and not o.resting and distance(o.pos, c.pos) <= ctx.near_radius
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda o: (distance(o.pos, c.pos), o.id)).id

    if name == "nearby":
        return nearest(lambda o: True)
    if name == "nearby_child":
        return nearest(lambda o: o.stage == "child")
    if name == "nearby_adult":
        return nearest(lambda o: o.stage in ("adult", "elder"))
    # Someone worth talking to for their news, or to tell yours. Going back to
    # a storyteller whose every tale you already hold, or telling someone who
    # already knows all you do, changes nothing. A storyteller in one run was
    # sought out 117 times by 14 villagers.
    news = ctx.news
    if name == "stranger":
        mine = news(c.id) if news else set()
        return nearest(lambda o: o.visitor and (news is None or bool(news(o.id) - mine)))
    if name == "listener":
        mine = news(c.id) if news else set()
        if ctx.known_to is not None:
            return nearest(lambda o: bool(mine - ctx.known_to(c.id, o.id)))
        return nearest(lambda o: news is None or bool(mine - news(o.id)))
    if name == "parent":
        parents = [ctx.characters[p] for p in c.parents if p in ctx.characters and ctx.characters[p].alive]
        if not parents:
            return None
        return min(parents, key=lambda o: (distance(o.pos, c.pos), o.id)).id
    if name == "partner":
        p = ctx.characters.get(c.partner) if c.partner else None
        return p.id if p and p.alive else None
    if name == "sweetheart":
        s = ctx.courtship.sweetheart(c) if ctx.courtship is not None else None
        return s.id if s is not None and not s.resting else None
    o = ctx.characters.get(name)
    return o.id if o and o.alive and o.id != c.id else None


class _Handler:
    name: str

    def to_action(self, marker: ActionMarker, context: MarkerContext | None = None) -> MarkerAction | None:
        raise NotImplementedError


class GoHandler(_Handler):
    name = "go"

    def to_action(self, marker, context=None):
        place = resolve_place(_arg(marker, "to"), context)
        if not place:
            return None
        # Going where you already are does nothing. Left to resolve, a bold
        # villager at the forest edge chose "walk out to the forest edge" seven
        # times running, and spent the morning there instead of in the fields.
        if context.world.places[place].contains(*context.character.pos):
            return None
        return MarkerAction("go", {"place": place}, marker)


class WanderHandler(_Handler):
    name = "wander"

    def to_action(self, marker, context=None):
        return MarkerAction("wander", {}, marker)


class RestHandler(_Handler):
    name = "rest"

    def to_action(self, marker, context=None):
        until = _arg(marker, "until")
        if until == "morning":
            return MarkerAction("rest", {"until": "morning"}, marker)
        return MarkerAction("rest", {"ticks": _ticks(marker, 4)}, marker)


class WorkHandler(_Handler):
    name = "work"

    def to_action(self, marker, context=None):
        place = resolve_place(_arg(marker, "site"), context)
        if not place:
            return None
        # Work in the fields goes to whichever field has fewest hands, once
        # there is more than one (section 2.9j).
        if context.world.places[place].kind == "fields":
            fields = [p.id for p in context.world.places.values()
                      if p.kind == "fields" and p.id not in context.character.avoiding]
            place = min(fields, key=lambda f: (_occupancy(context, f), f != place, f), default=place)
        return MarkerAction("work", {"place": place, "ticks": _ticks(marker, 12)}, marker)


class ClearHandler(_Handler):
    """Clear new ground at the edge of a place, so it grows.

    Refused when the place has no room left to grow into, so a village that
    has run out of land stops trying rather than working for nothing.
    """

    name = "clear"

    def to_action(self, marker, context=None):
        place = resolve_place(_arg(marker, "place"), context)
        if not place:
            return None
        if context.world.growth(place) is None:
            # A field with no room may still be cleared for: another field
            # grows, or a new one is broken where the land allows (2.9j).
            world, sim = context.world, _sim(context)
            if world.places[place].kind != "fields" or not (
                    any(world.growth(p.id) for p in world.places.values() if p.kind == "fields")
                    or (sim is not None and sim.land.able)):
                return None
        return MarkerAction("clear", {"place": place, "ticks": _ticks(marker, 12)}, marker)


class ApprenticeHandler(_Handler):
    """A graduate takes up a trade under a master who will have it.

    Refused for anyone who is not a graduate without a trade, for a trade the
    village does not have, and when every master of it already has as many
    apprentices as they can take. Feasibility re-ranking then passes to the
    graduate's next choice.
    """

    name = "apprentice"

    def to_action(self, marker, context=None):
        from hearthwick.trades import find_master
        trade = (_arg(marker, "trade") or "").strip().lower()
        c = context.character if context is not None else None
        if c is None or c.stage != "apprentice" or c.trade:
            return None
        if trade not in context.world.role_sites:
            return None
        court = getattr(context, "courtship", None)
        master = find_master(c, trade, context.characters,
                             court.of if court is not None else None)
        if master is None:
            return None
        return MarkerAction("apprentice", {"trade": trade, "master": master}, marker)


class HaveChildHandler(_Handler):
    """A couple at home welcome a child, when they can support one.

    Refused unless both are of age and home together, the granary is not low,
    the house has room, and their last child is at least a year old.
    """

    name = "have_child"

    def to_action(self, marker, context=None):
        from hearthwick.family import partner_of, refusal
        if context is None:
            return None
        c = context.character
        sim = _sim(context)
        wide = bool(sim is not None and sim.config.fertility)
        if refusal(c, context.characters, context.world, context.food_low, context.clock.day,
                   wide=wide):
            return None
        return MarkerAction("have_child", {"partner": partner_of(c, context.characters).id},
                            marker)


class ProposeHandler(_Handler):
    """Ask one's sweetheart to marry.

    Refused unless the two are fond enough and free to marry, the sweetheart
    is near and awake, and no question already stands for either of them, or
    was turned down between them in the last few days (hearthwick/courtship.py).
    """

    name = "propose"

    def to_action(self, marker, context=None):
        court = getattr(context, "courtship", None)
        if court is None:
            return None
        c = context.character
        s = court.can_propose(c)
        if s is None or s.resting or distance(s.pos, c.pos) > context.near_radius:
            return None
        return MarkerAction("propose", {"target": s.id}, marker)


class _AnswerHandler(_Handler):
    """Answer a proposal. Refused unless one stands for this villager."""

    def to_action(self, marker, context=None):
        court = getattr(context, "courtship", None)
        asker = court.can_answer(context.character) if court is not None else None
        if asker is None:
            return None
        return MarkerAction(self.name, {"asker": asker.id}, marker)


class AcceptHandler(_AnswerHandler):
    name = "accept_proposal"


class DeclineHandler(_AnswerHandler):
    name = "decline_proposal"


class FellHandler(_Handler):
    """Fell timber at the forest edge for a house.

    Only a crafter can, and only while a couple waits for a house and there is
    not yet timber enough to finish it (hearthwick/building.py).
    """

    name = "fell"

    def to_action(self, marker, context=None):
        from hearthwick.building import FOREST
        b = getattr(context, "building", None)
        if b is None or not b.can_fell(context.character):
            return None
        place = resolve_place(FOREST, context)
        if not place:
            return None
        return MarkerAction("fell", {"place": place, "ticks": _ticks(marker, 12)}, marker)


class BuildHandler(_Handler):
    """Work on the house going up, or lay one out if none is started.

    Only a crafter can, and only while a couple waits for a house, there is
    timber to build with, and there is a house going up or room for one.
    """

    name = "build"

    def to_action(self, marker, context=None):
        b = getattr(context, "building", None)
        if b is None or not b.can_build(context.character):
            return None
        # None until the plot is laid out, which the simulation does.
        site = b.site.id if b.site is not None else None
        if site is not None and site in context.character.avoiding:
            return None
        return MarkerAction("build", {"place": site, "ticks": _ticks(marker, 12)}, marker)


def _sim(context) -> object | None:
    return getattr(getattr(context, "building", None), "sim", None)


class GatherHandler(_Handler):
    """Gather a good where it is found (data/goods.yaml): for what the
    crafters are building (``for=building``), by a crafter while it is short,
    or for oneself, to sell or to put toward a want, by any villager old
    enough once there is money (hearthwick/economy.py)."""

    name = "gather"

    def to_action(self, marker, context=None):
        sim = _sim(context)
        goods = getattr(sim, "goods", None)
        if goods is None or context is None:
            return None
        what, purpose = _arg(marker, "what"), _arg(marker, "for") or "self"
        source = goods.source(what) if what else None
        if source is None or source not in context.world.places:
            return None
        c = context.character
        if purpose == "building":
            if not sim.building.can_gather(c, what):
                return None
        elif purpose != "self" or not sim.economy.can_gather(c):
            return None
        place = resolve_place(source, context)
        if not place:
            return None
        return MarkerAction("gather", {"what": what, "for": purpose, "place": place,
                                       "ticks": _ticks(marker, 12)}, marker)


class _WantedThingHandler(_Handler):
    """Pay at the market for what a wanted thing is to be made of
    (``[!buy]``), or gather toward it (``[!save]``). Wants are not in this
    edition (README), so nothing ever waits to be paid for and both always
    refuse. They stay so that the market's instructions, and the markers a
    villager may write into its lessons, are the paper's runs' own."""

    def to_action(self, marker, context=None):
        return None


class SaveHandler(_WantedThingHandler):
    name = "save"


class SmeltHandler(_Handler):
    """Make iron from ore and timber at the forge, for what the crafters are
    building, while iron is short and there is ore to smelt."""

    name = "smelt"

    def to_action(self, marker, context=None):
        from hearthwick.building import FORGE
        sim = _sim(context)
        if sim is None or context is None or not sim.building.can_smelt(context.character):
            return None
        place = resolve_place(FORGE, context)
        if not place:
            return None
        return MarkerAction("smelt", {"place": place, "ticks": _ticks(marker, 12)}, marker)


class FetchHandler(_Handler):
    """A merchant fetches from the road a good only the road brings, for what
    the crafters are building, while it is short."""

    name = "fetch"

    def to_action(self, marker, context=None):
        sim = _sim(context)
        what = _arg(marker, "what")
        if sim is None or context is None or not what or not sim.building.can_fetch(context.character, what):
            return None
        place = resolve_place(sim.goods.market.get("road", "east_road"), context)
        if not place:
            return None
        return MarkerAction("fetch", {"what": what, "place": place,
                                      "ticks": _ticks(marker, 12)}, marker)


class SellHandler(_Handler):
    """Take what one carries to the market and sell it."""

    name = "sell"

    def to_action(self, marker, context=None):
        sim = _sim(context)
        economy = getattr(sim, "economy", None)
        if economy is None or context is None or not economy.can_sell(context.character):
            return None
        place = resolve_place(sim.goods.market.get("place", "market"), context)
        if not place:
            return None
        return MarkerAction("sell", {"place": place}, marker)


class BuyHandler(_WantedThingHandler):
    name = "buy"


class FightBlightHandler(_Handler):
    """Go to the blighted fields and cut the rot out, with whoever else comes
    (section 2.9j). Refused when there is no blight there, when the switch is
    off, and for anyone too young or only passing through."""

    name = "fight_blight"

    def to_action(self, marker, context=None):
        from hearthwick.food import FIELDS
        sim = _sim(context)
        if sim is None or context is None or not sim.config.blight_fighting:
            return None
        c = context.character
        if c.visitor or c.stage not in ("apprentice", "adult", "elder"):
            return None
        if FIELDS not in sim.world_agent.state.sick_places:
            return None
        place = resolve_place(FIELDS, context)
        if not place:
            return None
        return MarkerAction("fight_blight", {"place": place, "ticks": _ticks(marker, 12)}, marker)


class DepartHandler(_Handler):
    """A visitor leaves the village. Nobody who lives here can."""

    name = "depart"

    def to_action(self, marker, context=None):
        if context is None or not context.character.visitor:
            return None
        return MarkerAction("depart", {}, marker)


class TalkHandler(_Handler):
    name = "talk"

    def to_action(self, marker, context=None):
        topic = _arg(marker, "topic", 1) or "whatever comes to mind"
        target = resolve_target(_arg(marker, "target"), context, _fresh(topic, context))
        if not target:
            return None
        return MarkerAction("talk", {"target": target, "topic": topic}, marker)


def _fresh(topic: str, context):
    """Who a talk about ``topic`` may go to: someone it would tell something new
    (config.novel_telling), and someone the speaker has not already talked
    with about it today (config.talk_once_a_day). In the seventh long run an
    elder told the same child "a story from the old days" 138 times in a
    year. None when neither applies."""
    novel = _novel(topic, context)
    once = None
    if context is not None and context.talked_today is not None:
        me = context.character.id
        once = lambda other: not context.talked_today(me, other.id, topic)  # noqa: E731
    if novel is None or once is None:
        return novel or once
    return lambda other: novel(other) and once(other)  # noqa: E731


def _novel(topic: str, context):
    """With config.novel_telling, a talk about news its topic names, by a
    place, goes only to someone who has not had that news from the speaker.
    In the fifth long run a lesson to mention a birth at house 13 was chosen
    3,132 times, told to the same people again and again. A topic that names
    no place, or names one the speaker has no news of, is talk rather than
    telling, and goes to anyone as before."""
    if (context is None or not context.novel_telling or context.known_to is None
            or context.news is None):
        return None
    text = topic.lower()
    named = {pid for pid, place in context.world.places.items()
             if pid.replace("_", " ") in text
             or (place.name or "").lower().removeprefix("the ") in text}
    if not named:
        return None
    mine = {r for r in context.news(context.character.id) if r.split(":")[1] in named}
    if not mine:
        return None
    me = context.character.id
    return lambda other: bool(mine - context.known_to(me, other.id))


class AvoidHandler(_Handler):
    """Steer clear of somewhere. Knowing a place is dangerous is only
    interesting if it changes where the villager goes."""

    name = "avoid"

    def to_action(self, marker, context=None):
        place = _resolve_place(_arg(marker, "place"), context)
        if not place or place in context.character.avoiding:
            return None          # already keeping away; nothing to decide
        c = context.character
        if c.role and context.world.role_sites.get(c.role) == place:
            # Nobody keeps away from their own work. A farmer who heard of the
            # blight avoided the fields, and then could not tend the crop it
            # was spoiling.
            return None
        return MarkerAction("avoid", {"place": place}, marker)


def _about(roots: set[str], topic: str, world: World) -> set[str]:
    """The news among ``roots`` that ``topic`` is about, by the place it names.

    A root is ``kind:place:tick``. A topic that names no place is about
    anything the villager knows.
    """
    text = topic.lower()
    named = {pid for pid, place in world.places.items()
             if pid.replace("_", " ") in text
             or (place.name or "").lower().removeprefix("the ") in text}
    if not named:
        return roots
    return {r for r in roots if r.split(":")[1] in named}


class WarnHandler(_Handler):
    """Tell someone nearby about something, on purpose rather than in passing."""

    name = "warn"

    def to_action(self, marker, context=None):
        # Only toward someone with something to learn. Once blight was common,
        # villagers who knew of it chose this warning in 29% of all decisions,
        # telling neighbours who already knew. That is the rule that a
        # decision which changes nothing is not a decision, applied to people.
        # A warning about a place is news about that place. Narrowed only to
        # having any news the listener lacked, warnings still took 17% of all
        # decisions, because nearly everyone lacked something.
        topic = _arg(marker, "topic", 1) or "something you should know"
        also = None
        fresh = None
        if context is not None and context.warn_news is not None:
            # Only the fresh news that unlocked the warning
            # (config.fresh_warnings). Matched by the place its topic names,
            # or by anything held when it names none, every fact a warner had
            # ever heard could qualify a listener and go with the warning. In
            # the paper-v3 runs a villager warned up to 134 times a day, the
            # same listener up to 58 times, mostly with old news the listener
            # already had (SPECIFICATION-warnings.md section 13).
            fresh = context.warn_news(context.character.id, context.instruction, topic)
            if not fresh:
                return None
        if context is not None and (fresh is not None or context.news is not None):
            mine = fresh if fresh is not None else _about(
                context.news(context.character.id), topic, context.world)
            if context.known_to is not None:
                # By what the warner remembers sharing with them, not by what
                # they hold, which the warner cannot see (config.told_memory).
                me = context.character.id
                also = lambda other: bool(mine - context.known_to(me, other.id))  # noqa: E731
            else:
                also = lambda other: bool(mine - context.news(other.id))  # noqa: E731
        if context is not None and context.quick_warnings:
            # Only someone within reach and awake, so telling is a word in
            # passing rather than a walk across the village.
            here, reach, has_news = context.character.pos, context.near_radius, also
            also = lambda other: (not other.resting  # noqa: E731
                                  and distance(other.pos, here) <= reach
                                  and (has_news is None or has_news(other)))
        target = resolve_target(_arg(marker, "target"), context, also)
        if not target:
            return None
        if fresh is not None:
            return MarkerAction("warn", {"target": target, "topic": topic,
                                         "news": sorted(fresh)}, marker)
        return MarkerAction("warn", {"target": target, "topic": topic}, marker)


class _AccompanyHandler(_Handler):
    def to_action(self, marker, context=None):
        target = resolve_target(_arg(marker, "target"), context)
        if not target:
            return None
        return MarkerAction(self.name, {"target": target, "ticks": _ticks(marker, 6)}, marker)


class FollowHandler(_AccompanyHandler):
    name = "follow"


class PlayHandler(_AccompanyHandler):
    name = "play"


# ---------------------------------------------------------------------------
# World markers. The world agent decides; the simulation carries the decision
# out and tags whoever it touches (DESIGN.md §2.1).


@dataclass
class WorldMarkerContext:
    world: World
    clock: Clock
    state: object            # hearthwick.world_agent.WorldState


class WeatherHandler(_Handler):
    name = "weather"
    KINDS = {"clear", "rain", "storm", "frost", "drought"}

    def to_action(self, marker, context=None):
        kind = coerce_enum(_arg(marker, "kind"), self.KINDS)
        if not kind:
            return None
        if context is not None and context.state.weather == kind:
            return None          # the weather already is this
        return MarkerAction("weather", {"kind": kind}, marker)


class VisitorHandler(_Handler):
    """Someone from outside comes up the east road to stay a while.

    Refused while a visitor is here, and for a few days after one has gone, or
    the village would never be without a stranger at the inn.
    """

    name = "visitor"
    KINDS = {"storyteller"}

    def to_action(self, marker, context=None):
        kind = coerce_enum(_arg(marker, "kind"), self.KINDS)
        if not kind:
            return None
        if context is not None:
            from hearthwick.visitors import VISITOR_GAP_DAYS
            s = context.state
            if s.visitors_here:
                return None
            if (s.last_visitor_day is not None
                    and context.clock.day - s.last_visitor_day < VISITOR_GAP_DAYS):
                return None
        return MarkerAction("visitor", {"kind": kind, "place": "east_road"}, marker)


class _PlaceEventHandler(_Handler):
    """Events at a place, refused when that event is already in effect there.

    Otherwise the world re-decides the same thing every day: the well cannot
    sicken three days running, it is already sick.
    """

    def already(self, state, place: str) -> bool:
        return False

    def to_action(self, marker, context=None):
        name = _arg(marker, "place")
        if not context or name not in context.world.places:
            return None
        if self.already(context.state, name):
            return None
        return MarkerAction(self.name, {"place": name}, marker)


class RaidHandler(_PlaceEventHandler):
    name = "raid"

    def already(self, state, place):
        # raiders do not come back the same week
        return place in state.hazards and state.hazards[place] > 0


class SickenHandler(_PlaceEventHandler):
    name = "sicken"

    def already(self, state, place):
        return place in state.sick_places


class TravelerHandler(_Handler):
    """A traveler, unless the last one's news is still going round.

    This was the one world handler that never refused, so once every other
    event was already in force the world had nothing else it could do and sent
    a traveler every day: six of nine events in a ten-day run. A decision that
    changes nothing is not a decision, and that has to hold for the world too.
    """

    name = "traveler"

    def to_action(self, marker, context=None):
        if context is not None:
            from hearthwick.world_agent import NEWS_FRESH_DAYS
            last = context.state.last_traveler_day
            if last is not None and context.clock.day - last <= NEWS_FRESH_DAYS:
                return None
        topic = _arg(marker, "topic") or "news from the road"
        return MarkerAction("traveler", {"topic": topic, "place": "east_road"}, marker)


class FestivalHandler(_Handler):
    name = "festival"

    def to_action(self, marker, context=None):
        if context is not None and context.state.festival_recent(context.clock.day):
            return None          # the village has only just gathered
        return MarkerAction("festival", {"place": "well"}, marker)


def build_world_registry() -> MarkerRegistry:
    """Separate from the villagers' registry: neither can use the other's verbs."""
    registry = MarkerRegistry()
    # No harvest verb. How good the harvest is was the world's to decide, and
    # it is now what the villagers brought in (hearthwick/food.py).
    for handler in (WeatherHandler(), RaidHandler(), SickenHandler(),
                    TravelerHandler(), FestivalHandler(), VisitorHandler()):
        registry.register(handler)
    return registry


def build_registry() -> MarkerRegistry:
    registry = MarkerRegistry()
    for handler in (GoHandler(), WanderHandler(), RestHandler(), WorkHandler(), ClearHandler(),
                    TalkHandler(), FollowHandler(), PlayHandler(),
                    AvoidHandler(), WarnHandler(), DepartHandler(), ApprenticeHandler(),
                    HaveChildHandler(), ProposeHandler(), AcceptHandler(), DeclineHandler(),
                    FellHandler(), BuildHandler(), GatherHandler(), SaveHandler(),
                    SmeltHandler(), FetchHandler(), SellHandler(), BuyHandler(),
                    FightBlightHandler()):
        registry.register(handler)
    return registry
