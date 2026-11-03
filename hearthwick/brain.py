"""Perception, retrieval and action selection.

Every behavioral choice goes through BEAR: the brain turns a character's
situation into context tags and a query, retrieves gated instructions, picks
one that carries action markers, and dispatches those markers. No LLM is
involved in choosing actions.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from bear import (
    Composer,
    CompositionStrategy,
    Context,
    MarkerAction,
    MarkerRegistry,
    Retriever,
    ScoredInstruction,
    parse_actions,
    strip_actions,
)
from bear.ownership import context_tags as ownership_tags

from hearthwick.character import Character
from hearthwick.config import SimConfig
from hearthwick.corpus import PUPILS_WAITING
from hearthwick.food import FIELDS, field_tiles, need_per_day
from hearthwick.family import tags as family_tags
from hearthwick.trades import tags as trade_tags
from hearthwick.knowledge import FADE_YEARS
from hearthwick.markers import MarkerContext, _about
from hearthwick.world import Clock, World, distance

# How many of the ranked candidates a decision records. The choice itself is
# made over every candidate the gates admit.
LOGGED_CANDIDATES = 12

PART_PHRASES = {
    "night": "It is night and dark, time to sleep.",
    "morning": "It is morning.",
    "midday": "It is midday.",
    "afternoon": "It is afternoon.",
    "evening": "Evening is coming.",
}


@dataclass
class Decision:
    tick: int
    character: str
    tags: list[str]
    query: str
    retrieved: list[dict]
    chosen: str | None
    actions: list[dict] = field(default_factory=list)
    # What the candidate pool would have chosen on each signal alone. If these
    # always agree, retrieval is a priority-ordered lookup wearing BEAR's
    # clothes, and the corpus is not doing situational work.
    by_score: str | None = None
    by_priority: str | None = None
    # Candidates that ranked above the choice but could not be carried out, so
    # a villager whose best options are all refused can be seen in the log.
    refused: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "character": self.character, "tags": self.tags, "query": self.query,
            "retrieved": self.retrieved, "chosen": self.chosen, "actions": self.actions,
            "by_score": self.by_score, "by_priority": self.by_priority,
            "refused": self.refused,
        }


def relation(c: Character, other: Character) -> str | None:
    """How ``other`` is related to ``c``, in words, or None."""
    if other.id in c.parents:
        return "mother" if other.sex == "female" else "father"
    if c.id in other.parents:
        return "daughter" if other.sex == "female" else "son"
    if c.partner == other.id:
        return "wife" if other.sex == "female" else "husband"
    if set(c.parents) & set(other.parents):
        return "sister" if other.sex == "female" else "brother"
    if c.mentor == other.id:
        return "mentor"
    if other.mentor == c.id:
        return "apprentice"
    return None


class Brain:
    def __init__(self, world: World, clock: Clock, retriever: Retriever,
                 registry: MarkerRegistry, config: SimConfig):
        self.world = world
        self.clock = clock
        self.retriever = retriever
        self.registry = registry
        self.config = config
        self.speech_composer = Composer(
            strategy=CompositionStrategy.HIERARCHICAL, header="", footer="",
        )
        # Set by the simulation once the world agent exists: the weather and
        # what the world has done lately are part of every villager's
        # situation, which is how a world decision changes what they retrieve.
        self.world_state = None
        # Set by the simulation: character id -> KnowledgeStore. What a villager
        # knows is part of its situation, which is how knowledge changes what it
        # retrieves and therefore what it does.
        self.knowledge = {}
        # Set by the simulation: what one villager remembers sharing with
        # another (Diffuser.known_to), used with config.told_memory.
        self.known_to = None
        # Set by the simulation: whether two villagers talked about a topic
        # today (Conversations.talked_today), with config.talk_once_a_day.
        self.talked_today = None
        # Set by the simulation. Reaching into the retriever for this silently
        # got None -- it exposes _embedder, not embedder -- and relevance
        # recall fell back to recency without anything saying so.
        self.embedder = None
        # Set by the simulation: who is fond of whom, the house going up, and
        # what each villager has to spend.
        self.courtship = None
        self.building = None
        self.economy = None

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    def pupils_waiting(self, characters: dict[str, Character]) -> bool:
        """Whether the school has fewer teachers than its children need, one
        for each ``pupils_per_teacher`` (config.teachers_by_pupils). A teacher
        is anyone teaching at the schoolyard or on the way to, so elders
        deciding in the same tick see each other's choice."""
        from hearthwick.growth import SCHOOL

        def teaching(o: Character) -> bool:
            planned = ([o.activity] if o.activity else []) + list(o.queue)
            return any(a.kind == "work" and a.data.get("place") == SCHOOL for a in planned)

        living = [o for o in characters.values() if o.alive and not o.visitor]
        pupils = sum(1 for o in living if o.stage == "child")
        if not pupils:
            return False
        needed = -(-pupils // max(1, self.config.pupils_per_teacher))
        return sum(1 for o in living if o.stage != "child" and teaching(o)) < needed

    def neighbors(self, c: Character, characters: dict[str, Character]) -> list[Character]:
        return sorted(
            (o for o in characters.values()
             if o.alive and o.id != c.id and not o.resting
             and distance(o.pos, c.pos) <= self.config.near_radius),
            key=lambda o: (distance(o.pos, c.pos), o.id),
        )

    def context_tags(self, c: Character, characters: dict[str, Character]) -> list[str]:
        part = self.clock.part_of_day
        # The character id gates that villager's own instructions (its persona,
        # and later what it has learned). It is also part of the text BEAR
        # embeds for the query, so two peers never score identically.
        tags = ownership_tags(c.id)
        tags += [f"stage_{c.stage}", f"time_{part}"]
        if part != "night":
            tags.append("daytime")
            if c.social < self.config.wants_company_below:
                tags.append("wants_company")
        if c.role:
            tags.append(f"role_{c.role}")
        if (self.config.teachers_by_pupils and c.stage == "elder" and part != "night"
                and self.pupils_waiting(characters)):
            tags.append(PUPILS_WAITING)
        tags += [f"temp_{allele}" for allele in c.temperament.values()]
        if c.energy < 0.3:
            tags.append("energy_low")
        if c.visitor:
            tags.append("visitor")
            if c.leaves_at is not None and self.clock.tick >= c.leaves_at:
                tags.append("leaving")

        place = self.world.place_at(c.pos)
        if place:
            tags.append(f"at_{place.id}")
            if place.id == c.home:
                tags.append("at_home")
            if c.role and place.id == self.world.role_sites.get(c.role):
                tags.append("at_work")

        store = self.knowledge.get(c.id)
        if store is not None:
            if self.config.news_fades or self.config.short_warnings:
                year = self.clock.ticks_per_day * self.clock.days_per_year
                fade = {kind: int(years * year) for kind, years in FADE_YEARS.items()}
                tags += store.tags(now=self.clock.tick, fade=fade)
            else:
                tags += store.tags()
        # Keeping away from somewhere is part of a villager's situation, not a
        # hidden variable: without this, two villagers with identical tags could
        # still act differently because one of them was avoiding the market.
        tags += [f"avoiding_{place}" for place in sorted(c.avoiding)]

        if self.world_state is not None:
            if self.world_state.weather != "clear":
                tags.append(f"weather_{self.world_state.weather}")
            if self.world_state.festival_day == self.clock.day:
                tags.append("festival")
            for hazard in self.world_state.hazards:
                tags.append(f"trouble_at_{hazard}")
            # The season and the food situation are common knowledge: everyone
            # eats from the granary and can see the fields.
            clock = self.clock
            tags.append(f"season_{clock.season}")
            fields = self.world.places.get(FIELDS)
            food_tags = []
            if fields is not None:
                food_tags = self.world_state.food.tags(
                    clock.season, clock.day, clock.days_per_year,
                    need_per_day(characters.values()), field_tiles(self.world),
                    clock.growing_progress)
                tags += food_tags
            # A graduate choosing a trade sees what it leans toward.
            tags += trade_tags(c, characters, self.world, food_tags)
        # An adult sees whether a family is possible now, and whether it is
        # courting or has been asked. A crafter sees whether a house is needed.
        tags += family_tags(c, characters, self.world, self.config.fertility)
        if self.courtship is not None:
            tags += self.courtship.tags(c)
        if self.building is not None:
            tags += self.building.tags(c)
        if self.economy is not None:
            tags += self.economy.tags(c)

        near =self.neighbors(c, characters)
        if not near:
            tags.append("alone")
        else:
            tags.append("near_someone")
            if len(near) >= 3:
                tags.append("near_crowd")
            if any(o.stage == "child" for o in near):
                tags.append("near_child")
            if any(o.stage in ("adult", "elder") for o in near):
                tags.append("near_adult")
            if any(o.id in c.parents for o in near):
                tags.append("near_parent")
            if c.partner and any(o.id == c.partner for o in near):
                tags.append("near_partner")
            if not c.visitor and any(o.visitor for o in near):
                tags.append("near_stranger")
        # Sorted: the tags become part of the text BEAR embeds for the query, so
        # the order they were appended in would otherwise change the scores.
        return sorted(tags)

    def situation(self, c: Character, characters: dict[str, Character]) -> str:
        """The sentence retrieval scores against.

        It names the villager, the people beside it and what it knows, which
        is part of what makes two villagers' retrieval differ.
        """
        place = self.world.place_at(c.pos)
        where = f"at {place.name}" if place else "out in the village"
        weather = getattr(self.world_state, "weather", "clear")
        weather_phrase = {"rain": "It is raining.", "storm": "A storm is blowing.",
                          "frost": "There is frost on the ground.",
                          "drought": "The ground is parched."}.get(weather, "")
        parts = [PART_PHRASES[self.clock.part_of_day], weather_phrase,
                 f"{c.name} is {where}."]
        parts = [p for p in parts if p]
        near = self.neighbors(c, characters)
        if near:
            described = []
            for o in near[:4]:
                rel = relation(c, o)
                described.append(f"{o.name} ({rel})" if rel else f"{o.name}, a {o.stage}")
            parts.append("Nearby: " + ", ".join(described) + ".")
        else:
            parts.append("Nobody is nearby.")
        if c.energy < 0.3:
            parts.append(f"{c.name} is tired.")
        store = self.knowledge.get(c.id)
        if store is not None and store.facts and self.config.memory_recall:
            # What this villager brings to mind, scored against the situation
            # so far rather than taken off the top of the pile. The base
            # sentence is embedded once for that; the retriever then embeds the
            # full query including what was recalled.
            base = " ".join(parts)
            vector = self._recall_vector(base)
            recalled = store.recall(vector, self.config.memory_recall, text=base)
            if recalled:
                parts.append("Knows: " + " ".join(f.text for f in recalled))
        return " ".join(parts)

    def _recall_vector(self, text: str):
        """The situation as a vector, for scoring a villager's own memories.

        None when there is no embedder or relevance is switched off, and
        KnowledgeStore.recall then falls back to recency.
        """
        if not self.config.memory_by_relevance or self.embedder is None:
            return None
        embedder = self.embedder
        try:
            return embedder.embed_single(text, is_query=True)
        except Exception:  # noqa: BLE001 - a decision must not fail on the service
            return None

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def _decision_context(self, tags: list[str]) -> Context:
        """What a decision asks with. With lessons as fading BEAR items
        (config.fading_lessons) it also opens BEAR's item facet, gated beside
        the tags so the query's words are unchanged, and fades by the clock so
        a lesson whose news has gone stale sinks and then drops out."""
        if not self.config.fading_lessons:
            return Context(tags=tags)
        from bear.items import ITEM_FACET
        from hearthwick.memory import LESSON_FLOOR
        return Context(tags=tags, gate_tags=[ITEM_FACET], now=float(self.clock.tick),
                       min_salience=LESSON_FLOOR)

    def _news_roots(self, character_id: str) -> set[str]:
        """The events a villager has news of. Its own experiences are not news."""
        store = self.knowledge.get(character_id)
        return {f.root for f in store.facts if not f.is_experience} if store else set()

    def _warn_news(self, character_id: str, instruction, topic: str) -> set[str]:
        """The events a warning is about (config.fresh_warnings): news the
        warner holds that still drives behaviour, as BEAR's salient items,
        and that the instruction answers. For an authored warning that is
        the news setting a knows_ tag the instruction is gated on, so its
        kind and place. For a lesson it is the news the lesson was written
        from, or, resting on none, the news its topic names."""
        store = self.knowledge.get(character_id)
        if store is None or not hasattr(store, "fresh"):
            return set()
        fresh = [f for f in store.fresh(self.clock.tick) if not f.is_experience]
        scope = getattr(instruction, "scope", None)
        gates = {t for t in (scope.required_tags if scope else []) if t.startswith("knows_")}
        if gates:
            return {f.root for f in fresh if f.tag in gates}
        sources = set((getattr(instruction, "metadata", None) or {}).get("parents") or [])
        if sources:
            return {f.root for f in fresh if f.id in sources}
        return _about({f.root for f in fresh}, topic, self.world)

    def decide(self, c: Character, characters: dict[str, Character]) -> tuple[Decision, list[MarkerAction]]:
        tags = self.context_tags(c, characters)
        query = self.situation(c, characters)
        # Everything the gates admit, ranked, not a fixed top few. How many
        # candidates end up refused grows with what a villager knows, so any
        # fixed cut can be filled with them.
        scored = self.retriever.retrieve(query, self._decision_context(tags),
                                         top_k=max(LOGGED_CANDIDATES, len(self.retriever.corpus)))

        rng = random.Random(f"{self.config.seed}:{self.clock.tick}:{c.id}")
        ctx = MarkerContext(world=self.world, clock=self.clock, character=c,
                            characters=characters, rng=rng,
                            near_radius=self.config.near_radius,
                            news=self._news_roots, food_low="food_low" in tags,
                            known_to=self.known_to if self.config.told_memory else None,
                            quick_warnings=self.config.quick_warnings,
                            novel_telling=self.config.novel_telling,
                            warn_news=self._warn_news if self.config.fresh_warnings else None,
                            talked_today=(self.talked_today
                                          if self.config.talk_once_a_day else None),
                            courtship=self.courtship, building=self.building)

        # Choose among what can actually be done. Down the ranking, each
        # candidate is resolved, and one whose markers resolve to nothing is
        # set aside, until the pool holds ``choice_pool`` that can. A decision
        # that changes nothing is not a decision, so it takes no place in the
        # choice either. Resolving after sampling from a fixed top four let
        # refused instructions fill all four: late in a run a villager who
        # knew of the blight and the sick well stood idle, because warning
        # nobody and avoiding places it already avoided were its best options.
        pool: list[tuple[ScoredInstruction, list[MarkerAction]]] = []
        refused: list[str] = []
        for s in scored:
            if not parse_actions(s.content):
                continue
            resolved = self._resolve(s, ctx, c)
            if resolved:
                pool.append((s, resolved))
                if len(pool) >= self.config.choice_pool:
                    break
            else:
                refused.append(s.id)

        chosen: ScoredInstruction | None = None
        actions: list[MarkerAction] = []
        if pool:
            chosen = self._sample([s for s, _ in pool], rng)
            actions = next(a for s, a in pool if s is chosen)

        scored = scored[:LOGGED_CANDIDATES]
        # "Similarity decided" asks whether ranking by score and by priority
        # alone would pick differently among the retrieved action candidates.
        # It measures retrieval, so it is taken over the ranking before the
        # feasibility re-rank. Taken over the feasible candidates instead, it
        # fell sharply without any change in how retrieval ranked, because the
        # re-rank removes options that similarity had preferred.
        candidates = [s for s in scored if parse_actions(s.content)]
        decision = Decision(
            tick=self.clock.tick,
            character=c.id,
            tags=tags,
            query=query,
            retrieved=[{"id": s.id, "score": round(s.final_score, 4),
                        "similarity": round(s.similarity, 4), "priority": s.priority,
                        "actionable": bool(parse_actions(s.content))} for s in scored],
            chosen=chosen.id if chosen else None,
            actions=[{"kind": a.kind, "data": a.data} for a in actions],
            by_score=max(candidates, key=lambda s: s.final_score).id if candidates else None,
            by_priority=(max(candidates, key=lambda s: (s.priority, -candidates.index(s))).id
                         if candidates else None),
            refused=refused,
        )
        return decision, actions

    def _resolve(self, candidate: ScoredInstruction, ctx: MarkerContext,
                 c: Character) -> list[MarkerAction]:
        """A candidate's actions, drawn with a random stream of its own.

        The place aliases (quiet_place, unvisited_place, random_home) draw
        from the context's stream. With one stream for the whole decision, a
        candidate that was resolved and refused shifted what every candidate
        below it resolved to, and what the sampler then chose among them. So
        each candidate gets its own stream, seeded from the decision and its
        own id, and the sampler keeps the decision's stream untouched.

        The derivation is Hearthwick's own. When the decision moves onto a
        library selector, pass this as its per-candidate RNG rather than
        taking the library's default, so a rerun depends on nothing outside
        this repository. Setting ``ctx.rng`` on the shared context is safe
        only because decisions run one at a time. Decisions run in parallel
        would need a context, or an RNG argument, per resolution.
        """
        ctx.rng = random.Random(f"{self.config.seed}:{self.clock.tick}:{c.id}:{candidate.id}")
        # What a warning is about depends on the instruction that chose it
        # (config.fresh_warnings).
        ctx.instruction = candidate.instruction
        return self.registry.process(candidate.content, context=ctx)[1]

    def _sample(self, pool: list[ScoredInstruction], rng: random.Random) -> ScoredInstruction:
        """One of the best candidates, or strictly the best when not sampling.

        Sampling keeps a village from looping, but it also muddies any claim
        about individuality, so it can be turned off: with temperature 0 a
        villager always takes its top-scoring candidate and every difference
        between two villagers traces to their instructions or their knowledge.
        """
        if self.config.choice_temperature <= 0:
            return max(pool, key=lambda s: (s.final_score, s.priority, s.id))
        best = max(s.final_score for s in pool)
        weights = [math.exp((s.final_score - best) / self.config.choice_temperature) for s in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Speech guidance
    # ------------------------------------------------------------------

    def speech_guidance(self, c: Character, listener: Character, topic: str,
                        characters: dict[str, Character]) -> tuple[str, list[str]]:
        """Compose how ``c`` speaks, from instructions gated on ``talking``.

        Returns the guidance text and the ids of the instructions used.
        """
        tags = self.context_tags(c, characters) + ["talking"]
        query = f"{c.name} talks with {listener.name} about {topic}."
        # Everything the gates admit, for the same reason as the lens in
        # diffusion.compose_lens: the filter comes after the cut, so a fixed
        # cut lets anything the corpus offers this villager crowd speech
        # instructions out before they are selected.
        scored = self.retriever.retrieve(query, Context(tags=tags),
                                         top_k=max(24, len(self.retriever.corpus)))
        speech = [s for s in scored
                  if "talking" in s.instruction.scope.required_tags and not parse_actions(s.content)]
        out = self.speech_composer.compose(speech)
        guidance = strip_actions(out.guidance)
        # What the composer kept, not what it was handed. The two differ
        # whenever max_instructions drops any, and the utterance event records
        # this as the instructions behind the line.
        #
        # The fallback is for bear f9b509c, whose ComposedOutput has no
        # `included`. The long run resumes on that version and a resume loads
        # whatever main is then, so this path must not fail on it. Remove the
        # fallback once the long run has moved off f9b509c.
        used = out.included if hasattr(out, "included") else [s.id for s in speech]
        return guidance, used
