"""The simulation loop.

Order within a tick:
  1. end finished conversations
  2. idle characters decide (BEAR retrieval -> action markers)
  3. characters carry out their current activity
  4. physics: energy, aging, places visited
  5. frame logged; in lockstep mode, wait for pending speech
"""

from __future__ import annotations

import asyncio
import json
import logging
import random

from bear import MarkerAction

from hearthwick.brain import Brain
from hearthwick.character import SPEED, Activity, Character, load_founders
from hearthwick.config import SimConfig
from hearthwick.conversation import Conversations
from hearthwick.diffusion import Diffuser
from hearthwick.corpus import (build_corpus, build_retriever, corpus_composition,
                               harden_scopes, make_embedder,
                               persona_instruction, rain_for_the_easygoing,
                               teach_by_pupils)
from hearthwick import checkpoint
from hearthwick.consolidation import consolidate
from hearthwick.events import RunLog
from hearthwick.food import (FIELDS, NEW_FIELD, RICH_FIELDS, Food, field_places, field_tiles,
                             year_scale,
                             need_per_day)
from hearthwick.growth import check as growth_check
from hearthwick.llm import SpeechModel
from hearthwick.markers import WorldMarkerContext, build_registry, build_world_registry
from hearthwick.usage import UsageReport
from hearthwick.building import FOREST, FORGE, SMELT_UNIT, Building
from hearthwick.courtship import Courtship
from hearthwick.family import Family, persona_now
from hearthwick.economy import Economy
from hearthwick.goods import Goods
from hearthwick.land import Land
from hearthwick.mortality import Mortality
from hearthwick.player import Players
from hearthwick.school import School
from hearthwick.visitors import Visitors
from hearthwick import trades
from hearthwick.world_agent import WorldAgent
from hearthwick.world import Clock, Place, World, distance

logger = logging.getLogger(__name__)

WAKE_HOUR = 6
ENERGY_AWAKE = 0.0035
ENERGY_WORK = 0.006
ENERGY_REST = 0.02
# With the granary empty, a day's work tires a villager faster and a night's
# rest restores less.
HUNGER_DRAIN = 1.5
HUNGER_REST = 0.5


# Stints of work at a place for what the crafters build, or for oneself
# (hearthwick/building.py, hearthwick/economy.py), and fighting a blight.
CRAFT_WORK = ("fell", "build", "gather", "smelt", "fetch", "fight_blight")
NEW_FIELD_NAMES = ("the new fields", "the far fields", "the east fields", "the high fields")
# Worker-ticks that cut a blight out of the fields: three villagers for four
# hours, or one for a long day (section 2.9j).
BLIGHT_FIGHT_TICKS = 72

class Simulation:
    def __init__(self, config: SimConfig, speech: SpeechModel | None = None):
        self.config = config
        self.speech = speech
        data = config.data_dir
        village = data / "villages" / config.village if config.village else None
        world_file = (village / "village.yaml") if village else data / "world" / "village.yaml"
        founders_file = (village / "founders.yaml") if village else data / "characters" / "founders.yaml"
        self.world = World.from_yaml(world_file)
        self.founding_places = set(self.world.places)   # the rest were built during the run
        self.clock = Clock(minutes_per_tick=config.minutes_per_tick, days_per_year=config.days_per_year,
                           start_hour=WAKE_HOUR)
        founders = load_founders(founders_file)
        self.characters: dict[str, Character] = {c.id: c for c in sorted(founders, key=lambda c: c.id)}
        self.founder_ids = set(self.characters)     # everyone else joined during the run
        self.corpus = build_corpus(data, founders, temperament=config.temperament,
                                   switches=config)
        self._composition = corpus_composition(data, config)
        if config.work_in_rain:
            rain_for_the_easygoing(self.corpus)
        if config.teachers_by_pupils:
            teach_by_pupils(self.corpus)
        if config.gating == "hard":
            harden_scopes(self.corpus)
        self.embedder = make_embedder(config.embedder, config.embed_url, config.embed_api_key,
                                      wait_seconds=config.server_wait_minutes * 60,
                                      model=config.embed_model,
                                      strict=config.embedder_strict)
        # A memory index that drops items is rebuilt from the vectors its
        # memories were first given (embedder.keep_documents).
        if self.embedder is not None and (config.forget_the_dead or config.forget_faded):
            self.embedder.keep_documents = True
        self.retriever = build_retriever(self.corpus, self.embedder,
                                         config.retrieval_threshold,
                                         config.restore_below_threshold)
        self.registry = build_registry()
        self.brain = Brain(self.world, self.clock, self.retriever, self.registry, config)
        self.conversations = Conversations(self)
        self.world_agent = WorldAgent(self.retriever, build_world_registry(),
                                      self.clock, config.seed,
                                      config.world_choice_temperature,
                                      population=len(self.characters))
        self.brain.world_state = self.world_agent.state
        self.world_agent.state.food = Food.founding(self.characters.values(),
                                                    config.days_per_year)
        self.world_agent.state.food.rich = RICH_FIELDS if config.richer_fields else 1.0
        self.world_agent.state.food.scale = year_scale(config.days_per_year)
        self._pending_events: list[tuple[int, MarkerAction]] = []
        if config.fading_lessons and not config.bear_memory:
            raise ValueError("fading_lessons needs bear_memory: a lesson's sources are BEAR items")
        if config.lasting_lessons and not config.fading_lessons:
            raise ValueError("lasting_lessons needs fading_lessons: it sets how long a "
                             "fading lesson lasts")
        for name in ("forget_the_dead", "forget_faded"):
            if getattr(config, name) and not config.bear_memory:
                raise ValueError(f"{name} needs bear_memory: it takes BEAR items out of "
                                 "the live index")
        for name in ("news_ends", "false_alarms"):
            if getattr(config, name) and not config.bear_memory:
                raise ValueError(f"{name} needs bear_memory: it marks BEAR items down")
        if config.false_alarms and not config.short_warnings:
            raise ValueError("false_alarms needs short_warnings, which marks the far-off "
                             "news that can come here")
        if config.novel_telling and not config.told_memory:
            raise ValueError("novel_telling needs told_memory: it asks what the teller "
                             "remembers sharing")
        if config.short_warnings and not config.bear_memory:
            raise ValueError("short_warnings needs bear_memory: its spans are BEAR items' half-lives")
        if config.fresh_warnings and not (config.told_memory and config.quick_warnings
                                          and config.bear_memory):
            raise ValueError("fresh_warnings needs told_memory, quick_warnings and "
                             "bear_memory: a warning is a word in passing about news "
                             "BEAR still holds fresh, to someone the warner has not told")
        if config.lessons_satisfied and not config.fading_lessons:
            raise ValueError("lessons_satisfied needs fading_lessons: a lesson's urge is "
                             "its strength as a BEAR item")
        if config.lessons_satisfied:
            from bear.retriever import Retriever
            if not hasattr(Retriever, "rest"):
                raise ValueError("lessons_satisfied needs a BEAR whose items rest and "
                                 "wake (design/declared-instructions.md)")
        if config.declared_lessons and not config.lessons_satisfied:
            raise ValueError("declared_lessons needs lessons_satisfied: a lesson rests "
                             "and wakes as it declares")
        if config.routine_fades and not config.bear_memory:
            raise ValueError("routine_fades needs bear_memory: its spans are BEAR items' "
                             "half-lives")
        self.diffuser = Diffuser(self)
        self.visitors = Visitors(self)
        self.family = Family(self)
        self.courtship = Courtship(self)
        self.mortality = Mortality(self)
        # What things are made of and what they fetch (hearthwick/goods.py).
        self.goods = (Goods.load(config.data_dir)
                      if config.materials or config.money else None)
        self.land = Land(self)
        self.building = Building(self)
        self.economy = Economy(self)
        self.players = Players(self)
        self.brain.courtship = self.courtship
        self.brain.building = self.building
        self.brain.economy = self.economy
        self.brain.knowledge = self.diffuser.stores
        self.brain.known_to = self.diffuser.known_to
        self.brain.talked_today = self.conversations.talked_today
        self.school = School(self)
        self.brain.embedder = self.embedder
        self.decisions: dict[str, dict] = {}
        self.usage = UsageReport()
        self.last_frame: dict | None = None
        self.stopping = False
        # Calls the server never answered before the checkpoint this run was
        # resumed from, so a resumed run still counts them (speech_errors).
        # None when that checkpoint predates the count: the run was not
        # measured, which is not the same as clean.
        self.errors_before: int | None = 0
        # The calls, failures and seconds before that checkpoint, so a resumed
        # run's record counts the whole run. None when the checkpoint predates
        # them, and the record then says its counts are from the resume on.
        self.counts_before: dict | None = {"calls": 0, "failures": 0, "seconds": 0.0}
        # Villagers who advanced this tick and have yet to consolidate. The
        # gate check runs inside the synchronous physics step; authoring an
        # instruction is a model call, so it happens back in the async loop.
        self._advanced: list = []

        rng = random.Random(f"{config.seed}:placement")
        for c in self.characters.values():
            c.pos = self.world.random_tile_in(c.home, rng)
        # Founders arrive with their lives behind them: an adult's trade is its
        # role, an apprentice's is its master's, and each has the practice its
        # years would have given it (hearthwick/trades.py).
        for c in self.characters.values():
            if c.stage in ("adult", "elder"):
                c.trade = c.trade or c.role
            elif c.stage == "apprentice" and c.mentor in self.characters:
                c.trade = c.trade or self.characters[c.mentor].role
        for c in self.characters.values():
            for site, ticks in trades.founding_practice(c, self.world, self.characters).items():
                c.growth.practice.setdefault(site, ticks)

        self.log = RunLog(config.runs_dir, config.seed, {
            "config": config.to_dict(),
            "speech_model": speech.info() if speech and speech.available else None,
            "embedder": self.embedder.info() if self.embedder else {"kind": "bm25"},
            "gating": config.gating,
            "temperament": config.temperament,
            "choice_temperature": config.choice_temperature,
            "world": self.world_agent.state.to_dict(),
            "corpus_size": len(self.corpus),
            # The authored instructions this run loaded, by directory, which
            # the paper's description of the corpus is checked against.
            "corpus": self._composition,
            "village": config.village or "hearthwick",
            "villagers": len(self.characters),
        })
        self.log.event(0, "roster", characters=[c.profile() for c in self.characters.values()])
        self._last_day = self.clock.day

    def join(self, c: Character, extra=(), index: bool = True) -> None:
        """Someone new in the village mid-run: a visitor, or a child born here.

        Its persona and anything else it owns go into the shared corpus,
        gated to it, and the index is rebuilt once. A checkpoint restoring
        many at once passes ``index=False`` and rebuilds once at the end.
        """
        self.characters[c.id] = c
        self.corpus.add(persona_instruction(c))
        for instruction in extra:
            self.corpus.add(instruction)
        if index:
            self.retriever.build_index()

    def regrow_persona(self, c: Character, index: bool = True) -> bool:
        """A villager born here, described as it is now (config.grown_personas,
        family.persona_now): its persona instruction replaced, and the change
        logged so a viewer's panel shows it. Founders keep the personas they
        were written with, and visitors theirs."""
        if (not self.config.grown_personas or c.visitor or not c.alive
                or c.id in self.founder_ids):
            return False
        now = persona_now(c, self.characters)
        if now == c.persona:
            return False
        c.persona = now
        self.corpus.add(persona_instruction(c))
        self.log.event(self.clock.tick, "persona", character=c.id, persona=now,
                       stage=c.stage, role=c.role, trade=c.trade)
        if index:
            self.retriever.build_index()
        return True

    def refresh_personas(self) -> int:
        """Every villager born here described as it is now, the index rebuilt
        once, as when a run takes grown personas up."""
        changed = sum(self.regrow_persona(c, index=False) for c in list(self.characters.values()))
        if changed:
            self.retriever.build_index()
        return changed

    def rng_for(self, purpose: str, key: str) -> random.Random:
        return random.Random(f"{self.config.seed}:{self.clock.tick}:{purpose}:{key}")

    # ------------------------------------------------------------------

    async def step(self) -> dict:
        tick = self.clock.tick
        # Purses and the places materials need, when a run begins or takes
        # them up (hearthwick/economy.py).
        self.economy.ensure(tick)
        self.conversations.update()
        if tick and self.clock.hour == WAKE_HOUR:
            self._world_turn()
        self._fire_due_events()

        # A snapshot, since a child can be born mid-step. It takes its first
        # decision on the next tick.
        present = list(self.characters.values())
        empty = set()                 # who decided this tick and got no action
        for c in present:
            if c.alive and c.idle:
                if not self._decide(c, tick):
                    empty.add(c.id)

        for c in list(self.characters.values()):
            if c.alive:
                self._advance(c)

        # A villager whose action ended in this tick takes up its next one in
        # it too, the next it had queued or a fresh decision, rather than
        # standing idle until the next tick (config.decide_again,
        # SPECIFICATION-warnings.md section 11). Once a tick, so actions that
        # each end at once cannot loop, and not for a villager whose decision
        # this tick gave nothing to do.
        if self.config.decide_again:
            for c in present:
                if not c.alive or c.conversation_id or c.activity is not None:
                    continue
                if not c.queue and (c.id in empty or not self._decide(c, tick)):
                    continue
                self._advance(c)

        self._physics()
        self.school.teach()
        await self.school.settle()
        if self._advanced:
            await self._consolidate_advanced()
        frame = self.log.frame(tick, self.clock.to_dict(),
                               [c.frame() for c in self.characters.values() if c.alive],
                               self.building.status(),
                               # Purses each in-game hour, which is often enough to watch
                               # them by and keeps the frames small.
                               self.economy.summary() if self.economy.money and tick % 6 == 0
                               else None)
        self.last_frame = frame

        if self.config.lockstep:
            await self.conversations.wait_generating()
        self.log.flush()
        self.clock.tick += 1
        return frame

    async def run(self, ticks: int, checkpoint_every: int = 0,
                  until_tick: int | None = None) -> None:
        """Step the village, saving its state periodically if asked.

        ``until_tick`` is for resumed runs: a checkpoint remembers how far the
        run had got, and the caller wants to reach a total rather than take
        another ``ticks`` steps on top.
        """
        target = until_tick if until_tick is not None else self.clock.tick + ticks
        while self.clock.tick < target:
            if self.stopping:
                logger.info("stopping at tick %d", self.clock.tick)
                break
            await self.step()
            if checkpoint_every and self.clock.tick % checkpoint_every == 0:
                await self.save()
        if checkpoint_every:
            await self.save()

    async def _consolidate_advanced(self) -> None:
        pending, self._advanced = self._advanced, []
        for character, became in pending:
            # An infant turning two has lived through nothing to write down.
            if self.config.consolidate and became != "child":
                await consolidate(self, character, became)

    async def settle(self) -> None:
        """Let what the village has in flight finish: conversations ended and
        their exchanges stored. A conversation ending spawns its diffusion
        exchange as a task, so anything that reads or closes the village's
        state before those are done loses the knowledge they were about to
        store, or has them write to a closed log."""
        for conv in list(self.conversations.active.values()):
            self.conversations.end(conv)
        await self.conversations.wait_generating()

    async def save(self):
        """Settle the village, then write its state so it can be resumed.

        Settling first is not tidiness: a snapshot taken while exchanges are
        in flight silently loses what they were about to store (``settle``).
        """
        await self.settle()
        path = checkpoint.save(self)
        logger.info("checkpoint at tick %d -> %s", self.clock.tick, path)
        return path

    def resume_from(self, path) -> int:
        tick = checkpoint.restore(self, path)
        # How much the fields yield is the run's setting, not the saved state.
        self.world_agent.state.food.rich = RICH_FIELDS if self.config.richer_fields else 1.0
        self.world_agent.state.food.scale = year_scale(self.config.days_per_year)
        # A run that has just taken grown personas up has villagers still
        # described as they were born.
        self.refresh_personas()
        return tick

    @property
    def speech_errors(self) -> int | None:
        """The calls the server never answered in this run so far, resumes
        included (SpeechModel.errors). None if part of the run went unmeasured."""
        if self.errors_before is None:
            return None
        return self.errors_before + (getattr(self.speech, "errors", 0) if self.speech else 0)

    @property
    def speech_counts(self) -> dict:
        """Model calls, failures and seconds waited in this run so far,
        resumes included, or only since the last resume if the checkpoint it
        came from predates the count (``partial``)."""
        s = self.speech

        def number(value) -> float:
            # Some tests' stand-ins keep their calls as a list of requests.
            return value if isinstance(value, (int, float)) else len(value or ())

        here = {"calls": number(getattr(s, "calls", 0)) if s else 0,
                "failures": number(getattr(s, "failures", 0)) if s else 0,
                # Not every speech model keeps time (the tests' stand-ins do not).
                "seconds": getattr(s, "seconds", 0.0) if s else 0.0,
                # Times the server stopped answering and was waited out
                # (SimConfig.server_wait_minutes), and for how long.
                "outages": getattr(s, "outages", 0) if s else 0,
                "outage_seconds": getattr(s, "outage_seconds", 0.0) if s else 0.0}
        before = self.counts_before
        if before is None:
            return {**here, "partial": True}
        return {k: before.get(k, 0) + v for k, v in here.items()}

    def request_stop(self) -> None:
        """Finish the tick in progress, checkpoint, and come back cleanly."""
        self.stopping = True

    def close(self) -> None:
        for conv in list(self.conversations.active.values()):
            self.conversations.end(conv)
        if self.embedder is not None:
            self.log.meta["embedder"] = self.embedder.info()
        from bear import parse_actions

        actionable = [i.id for i in self.corpus if parse_actions(i.content)]
        summary = self.usage.write(self.log.dir / "usage.json", actionable)
        knowledge = {cid: store.to_dicts() for cid, store in self.diffuser.stores.items()}
        (self.log.dir / "knowledge.json").write_text(
            json.dumps(knowledge, indent=2), encoding="utf-8")
        self.log.meta["knowledge"] = {cid: len(f) for cid, f in knowledge.items() if f}
        self.log.meta["usage"] = {k: v for k, v in summary.items()
                                  if k not in ("chosen_counts", "per_character")}
        logger.info("corpus usage: %s", UsageReport.describe(summary))
        self.log.close(
            ticks=self.clock.tick,
            speech_calls=self.speech_counts["calls"],
            speech_failures=self.speech_counts["failures"],
            # The calls the server never answered, which a paper run must not
            # have (SpeechModel.errors).
            speech_errors=self.speech_errors,
            speech_seconds=round(self.speech_counts["seconds"], 1),
            # Times the model server stopped answering and was waited out
            # (SimConfig.server_wait_minutes).
            speech_outages=self.speech_counts["outages"],
            speech_outage_seconds=round(self.speech_counts["outage_seconds"], 1),
            # Counted only since the last resume, from a checkpoint made
            # before the counts were kept in it.
            **({"speech_counts_partial": True} if self.counts_before is None else {}),
        )

    # ------------------------------------------------------------------
    # The world's turn
    # ------------------------------------------------------------------

    # Weather settles over the whole day, so it starts at dawn. Something that
    # happens to someone - raiders, a trader, the well turning - happens at an
    # hour when there is someone to see it, or nobody witnesses anything and
    # there is no ground truth to trace.
    IMMEDIATE = {"weather"}
    EVENT_HOURS = {"festival": (18, 21), "traveler": (9, 17),
                   "raid": (7, 19), "sicken": (8, 18),
                   # the harvest is reckoned in the morning after it ends
                   "harvest": (9, 12),
                   # a visitor comes up the road while there is light to travel
                   "visitor": (9, 16)}

    def _world_turn(self) -> None:
        # The village can change size, and every threshold the world
        # perceives with is a share of it.
        self.world_agent.population = max(
            1, sum(1 for c in self.characters.values() if c.alive))
        """The sky, then whatever happens. Physics carries it out, some of it later."""
        state = self.world_agent.state
        ended = state.roll_day(self.clock.day, self.clock.ticks_per_day)
        # What wore off is news, told by whoever is near (config.news_ends).
        if self.config.news_ends:
            for ending, place in ended or ():
                self.diffuser.witness(ending, place, self._nearest_witnesses(place),
                                      {"place": place}, self.clock.tick)
        rng = self.rng_for("world", "schedule")
        self._food_dawn(rng)
        # Who is fond of whom, and where the house for a waiting couple has
        # got to, for the record.
        fondest = self.courtship.fondest()
        if fondest:
            self.log.event(self.clock.tick, "courtship", fondest=fondest)
        if self.courtship.waiting or self.building.site is not None:
            self.log.event(self.clock.tick, "building", **self.building.to_dict(),
                           waiting=[list(c) for c in self.courtship.waiting])
        # Both decisions read the same dawn, and only then does either take
        # effect. Applying the sky first let the rain that ends a dry spell
        # erase it before the day's event was decided, so nothing that needs a
        # dry spell could happen at all. The well never sickened.
        context = WorldMarkerContext(self.world, self.clock, state)
        decided = []
        for focus in ("sky", "happening"):
            decision, actions = self.world_agent.decide(context, focus)
            record = decision.to_dict()
            self.decisions["world"] = {"t": self.clock.tick, **record}
            self.usage.record(record)
            self.log.event(self.clock.tick, "decision", **record)
            decided.append(actions)

        for actions in decided:
            for action in actions:
                if action.kind in self.IMMEDIATE:
                    self._apply_world_action(action)
                    continue
                low, high = self.EVENT_HOURS.get(action.kind, (9, 18))
                at = self.clock.tick + self.clock.ticks_until_hour(rng.uniform(low, high))
                self._pending_events.append((at, action))

    def _food_dawn(self, rng: random.Random) -> None:
        """The village eats, and when autumn has just ended, the harvest is in.

        How good the harvest was is what the villagers brought in, not a
        decision the world makes. It becomes a world event all the same, so it
        is witnessed and told like any other news.
        """
        state, clock = self.world_agent.state, self.clock
        need = need_per_day(self.characters.values())
        brought_in = state.food.dawn(clock.season, clock.season_of_day(clock.day - 1),
                                     need, FIELDS in state.sick_places)
        tiles = field_tiles(self.world)
        self.log.event(clock.tick, "food", need=round(need, 2), tiles=tiles,
                       capacity=state.food.capacity(tiles), season=clock.season,
                       worked_fields=state.yesterday["fields"], **state.food.to_dict())
        if brought_in is not None:
            yield_ = state.food.verdict(brought_in, need, clock.days_per_year)
            action = MarkerAction("harvest", {"yield": yield_, "brought_in": brought_in}, None)
            low, high = self.EVENT_HOURS["harvest"]
            at = clock.tick + clock.ticks_until_hour(rng.uniform(low, high))
            self._pending_events.append((at, action))

    def _fire_due_events(self) -> None:
        due = [(t, a) for t, a in self._pending_events if t <= self.clock.tick]
        self._pending_events = [(t, a) for t, a in self._pending_events
                                if t > self.clock.tick]
        for _, action in due:
            self._apply_world_action(action)

    # Where an event happens when its marker does not say. Weather has no
    # place because it is everywhere.
    WORLD_EVENT_PLACE = {"harvest": "fields"}

    # Genuinely shared experience: nobody has to be told it snowed. These
    # produce a fact for everyone at once, which means they never diffuse --
    # correctly, because an event everyone saw is not news.
    VILLAGE_WIDE = ("weather", "festival")

    # Everything else is witnessed by the few nearest people who are awake.
    #
    # This sits between two failures. Strictly place-bound within six tiles, a
    # harvest nobody stands in produced no fact at all and a stranger entering
    # the village went unnoticed: one seed passed six days and four events
    # without learning anything. Village-wide, the opposite -- a traveler was
    # witnessed by 23.6 of 30, every offer was already known, and lens calls
    # fell from 635 to 144. If everyone witnesses everything there is nothing
    # left to tell, and telling is the thing being studied.
    #
    # The people closest to where it happened know first, and the rest of the
    # village finds out from them.
    WITNESS_CAP = 5

    def _apply_world_action(self, action: MarkerAction) -> None:
        state, tick = self.world_agent.state, self.clock.tick
        place = action.data.get("place") or self.WORLD_EVENT_PLACE.get(action.kind)
        if action.kind in self.VILLAGE_WIDE:
            witnesses = sorted(c.id for c in self.characters.values()
                               if c.alive and not c.resting and c.stage != "infant")
        else:
            witnesses = self._nearest_witnesses(place) if place else []

        if action.kind == "weather":
            state.weather = action.data["kind"]
            state.weather_until = tick + self.clock.ticks_per_day
            if state.weather in ("rain", "storm"):
                state.days_since_rain = 0
            elif state.weather == "frost":
                state.food.frost()
        elif action.kind == "harvest":
            state.last_harvest = action.data["yield"]
            # the harvest of the year that has just ended its autumn
            state.last_harvest_year = self.clock.year
        elif action.kind == "sicken":
            state.sick_places[place] = self.clock.day
        elif action.kind == "raid":
            state.hazards[place] = tick
        elif action.kind == "traveler":
            # Not a hazard. A trader set one here, which made villagers avoid
            # the road and -- because RaidHandler refuses a raid while a hazard
            # stands -- meant one passing merchant blocked raiders for ever.
            state.last_traveler_day = self.clock.day
        elif action.kind == "festival":
            state.festival_day = self.clock.day
        elif action.kind == "visitor":
            # A stranger with news is fresh news, as a traveler is.
            state.last_traveler_day = self.clock.day
            self.visitors.arrive(tick)

        # Ground truth for the knowledge work: what happened, where, and who
        # was close enough to see it.
        self.log.event(tick, "world_event", event=action.kind, place=place,
                       data={k: v for k, v in action.data.items() if k != "place"},
                       witnesses=witnesses, weather=state.weather,
                       season=self.world_agent.context_tags()[1].removeprefix("season_"))
        # Whoever saw it holds it first-hand. This is the root of every chain
        # the knowledge work traces.
        if witnesses:
            self.diffuser.witness(action.kind, place, witnesses, action.data, tick)

    def _nearest_witnesses(self, place_id: str, cap: int | None = None) -> list[str]:
        """The few awake villagers closest to where it happened.

        Distance decides who was there; the cap decides how many that can be,
        so an event always has a witness and never has the whole village.
        """
        place = self.world.places.get(place_id)
        if place is None:
            return []
        rx, ry, rw, rh = place.rect
        return self._nearest_to((rx + rw // 2, ry + rh // 2), cap)

    def _nearest_to(self, tile, cap: int | None = None) -> list[str]:
        # A baby sees the raiders too, but cannot tell anyone, so it would only
        # take the place of a witness who can.
        awake = [c for c in self.characters.values()
                 if c.alive and not c.resting and c.stage != "infant"]
        awake.sort(key=lambda c: (distance(c.pos, tile), c.id))
        return sorted(c.id for c in awake[:cap or self.WITNESS_CAP])

    def _grow(self) -> None:
        """Advance anyone who has met every requirement; record who has not.

        Advancement is a tag swap. A villager that becomes an apprentice gains
        no ability: a different part of the corpus becomes retrievable for it,
        and it behaves differently because different instructions are in reach.
        """
        for c in self.characters.values():
            if not c.alive:
                continue
            nxt, missing = growth_check(c.stage, c.growth, c.age,
                                        trades.site_of(c.trade, self.world))
            if nxt is None:
                if missing:
                    # Staying stuck must be explainable, so the reason is
                    # recorded rather than a villager silently never growing up.
                    self.log.event(self.clock.tick, "growth_held_back",
                                   character=c.id, stage=c.stage,
                                   age=round(c.age, 2), missing=missing)
                continue
            was = c.stage
            c.stage = nxt
            if nxt == "adult" and c.trade:
                # Qualified: the trade it learned is now its role.
                c.role = c.trade
                self.log.event(self.clock.tick, "took_up_trade", character=c.id,
                               trade=c.trade, master=c.mentor)
            self._advanced.append((c, nxt))
            c.growth.advanced.append({"from": was, "to": nxt,
                                      "day": self.clock.day, "age": round(c.age, 2)})
            self.log.event(self.clock.tick, "stage_change", character=c.id,
                           was=was, now=nxt, age=round(c.age, 2),
                           tracks=c.growth.to_dict())
            self.regrow_persona(c)

    def _witnesses(self, place_id: str, radius: int = 6) -> list[str]:
        place = self.world.places.get(place_id)
        if place is None:
            return []
        rx, ry, rw, rh = place.rect
        center = (rx + rw // 2, ry + rh // 2)
        return sorted(c.id for c in self.characters.values()
                      if c.alive and not c.resting and distance(c.pos, center) <= radius)

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    @staticmethod
    def _activity(action: MarkerAction, instruction_id: str | None) -> Activity:
        return Activity(kind=action.kind, data=dict(action.data), instruction_id=instruction_id)

    def _begin(self, c: Character) -> None:
        act = c.activity
        rng = self.rng_for("begin", c.id)
        c.path = []
        if act.kind == "build":
            # The first crafter to build lays out the plot. Checked again, as
            # the house may have been finished, or the timber used, since.
            ok = self.building.can_build(c)
            act.data["place"] = self.building.start(c, self.clock.tick) if ok else None
        # Every stint of craft work is at a place, fighting a blight included,
        # which was left out of a list here once and paused the live village.
        if act.kind in ("go", "work", "clear", "sell") or act.kind in CRAFT_WORK:
            # None, or a building site finished and gone since it was chosen.
            if act.data["place"] not in self.world.places:
                act.ticks_left = 0
                return
            place = self.world.places[act.data["place"]]
            if not place.contains(*c.pos):
                c.path = self.world.path(c.pos, self.world.random_tile_in(place.id, rng))
            if act.kind in CRAFT_WORK or act.kind in ("work", "clear"):
                act.ticks_left = act.data["ticks"]
        elif act.kind == "wander":
            for _ in range(20):
                x = c.pos[0] + rng.randint(-8, 8)
                y = c.pos[1] + rng.randint(-8, 8)
                if self.world.walkable((x, y)):
                    c.path = self.world.path(c.pos, (x, y))
                    break
        elif act.kind == "rest":
            if act.data.get("until") == "morning":
                act.ticks_left = self.clock.ticks_until_hour(WAKE_HOUR)
            else:
                act.ticks_left = act.data["ticks"]
        elif act.kind == "talk":
            act.ticks_left = self.config.talk_approach_ticks
        elif act.kind in ("follow", "play"):
            act.ticks_left = act.data["ticks"]
        elif act.kind == "warn":
            act.ticks_left = 1 if self.config.quick_warnings else self.config.talk_approach_ticks
        elif act.kind == "depart":
            act.ticks_left = 0
        elif act.kind == "have_child":
            partner = self.characters.get(act.data["partner"])
            if partner is not None:
                food_low = "food_low" in self.brain.context_tags(c, self.characters)
                self.family.attempt(c, partner, self.clock.tick, food_low)
        elif act.kind == "propose":
            self.courtship.propose(c, act.data["target"], self.clock.tick)
        elif act.kind == "accept_proposal":
            self.courtship.accept(c, self.clock.tick)
        elif act.kind == "decline_proposal":
            self.courtship.decline(c, self.clock.tick)
        elif act.kind == "apprentice":
            c.trade, c.mentor = act.data["trade"], act.data["master"]
            self.log.event(self.clock.tick, "apprenticed", character=c.id,
                           trade=c.trade, master=c.mentor,
                           fondness=round(self.courtship.of(c.id, c.mentor), 2))
            self.regrow_persona(c)
        elif act.kind == "avoid":
            place = act.data["place"]
            if place not in self.world.places:
                return
            c.avoiding[place] = self.clock.tick + self.config.avoid_ticks
            self.log.event(self.clock.tick, "avoid", character=c.id, place=place)
            # Standing in the place you have just decided to avoid: leave.
            if self.world.places[place].contains(*c.pos):
                rng = self.rng_for("avoid", c.id)
                c.path = self.world.path(c.pos, self.world.random_tile_in(c.home, rng))

    def _finish(self, c: Character) -> None:
        # A lesson carried out to its end has met its goal
        # (config.lessons_satisfied), once nothing more of it is queued.
        act = c.activity
        if (self.config.lessons_satisfied and act is not None and act.instruction_id
                and self.diffuser.memory is not None
                and not any(q.instruction_id == act.instruction_id for q in c.queue)):
            self.diffuser.memory.satisfied(c.id, act.instruction_id, self.clock.tick)
        c.activity = None
        c.path = []

    def _move(self, c: Character) -> None:
        for _ in range(SPEED[c.stage]):
            if not c.path:
                return
            c.pos = c.path.pop(0)

    def _decide(self, c: Character, tick: int) -> int:
        """One decision for an idle villager, logged, with its actions
        queued. Returns how many it queued."""
        decision, actions = self.brain.decide(c, self.characters)
        record = decision.to_dict()
        self.decisions[c.id] = {"t": tick, **record}
        self.usage.record(record)
        self.log.event(tick, "decision", **record)
        for a in actions:
            c.queue.append(self._activity(a, decision.chosen))
        return len(actions)

    def _advance(self, c: Character) -> None:
        if c.conversation_id:
            return
        if c.activity is None:
            if not c.queue:
                return
            c.activity = c.queue.popleft()
            self._begin(c)
        act = c.activity

        if act.kind in ("go", "wander"):
            if c.path:
                self._move(c)
                return
            # Arrived. Stay a little while unless something else is queued.
            if act.ticks_left is None:
                act.ticks_left = 0 if c.queue else self.config.linger_ticks
            act.ticks_left -= 1
            if act.ticks_left <= 0:
                self._finish(c)
            return

        if act.kind == "avoid":
            # Deciding to keep away is instantaneous; _begin recorded it and
            # started the villager moving if it was standing there.
            self._finish(c)
            return

        if act.kind == "sell":
            # A walk to the market, and the sale when it gets there
            # (hearthwick/economy.py).
            if c.path:
                self._move(c)
                return
            self.economy.sell(c, self.clock.tick)
            self._finish(c)
            return

        if act.kind == "depart":
            self.visitors.depart(c, self.clock.tick)
            return

        if act.kind in ("apprentice", "have_child", "propose", "accept_proposal",
                        "decline_proposal"):
            # Done in _begin: choosing a master, welcoming a child, asking and
            # answering, is a moment, not a task.
            self._finish(c)
            return

        if act.kind in CRAFT_WORK or act.kind in ("work", "clear", "rest"):
            if c.path:
                self._move(c)
                return
            if act.ticks_left is None:
                # Begun without its ticks, and carried so by a checkpoint: the
                # blight fighting that paused the live village was saved that
                # way, and failed again on every resume.
                act.ticks_left = act.data.get("ticks") or 0
            act.ticks_left -= 1
            if act.ticks_left <= 0:
                self._finish(c)
            return

        target = self.characters.get(act.data.get("target", ""))
        act.ticks_left -= 1
        if target is None or not target.alive:
            self._finish(c)
            return

        if act.kind == "warn" and self.config.quick_warnings:
            # A word to someone within reach: the news passes in this tick,
            # with no conversation, and the listener goes on with what it was
            # doing (SPECIFICATION-warnings.md section 8).
            if not target.resting and distance(c.pos, target.pos) <= self.config.near_radius:
                # With fresh_warnings what is told is remembered as told now,
                # before a decision later in this tick (config.decide_again).
                tell = self.diffuser.warning if self.config.fresh_warnings else self.diffuser.tell
                self.conversations.exchanges.append(asyncio.get_running_loop().create_task(
                    tell(c, target, act.data["topic"], act.instruction_id, act.data.get("news"))))
            self._finish(c)
            return

        if act.kind == "warn":
            # Deliberately telling someone, so what a villager knows reaches
            # somebody instead of sitting in its own head.
            if target.resting or act.ticks_left <= 0:
                self._finish(c)
            elif distance(c.pos, target.pos) <= 1:
                if target.conversation_id is None:
                    self.conversations.start(c, target, act.data["topic"], act.instruction_id)
                self._finish(c)
            else:
                self._approach(c, target, 1)
            return

        if act.kind == "talk":
            if target.resting:
                self._finish(c)
            elif distance(c.pos, target.pos) <= 1:
                if target.conversation_id is None:
                    self.conversations.start(c, target, act.data["topic"], act.instruction_id)
                    self._finish(c)
                elif act.ticks_left <= 0:
                    self._finish(c)
            else:
                self._approach(c, target, 1)
                if act.ticks_left <= 0:
                    self._finish(c)
            return

        if act.kind == "follow":
            if distance(c.pos, target.pos) > 2:
                self._approach(c, target, 2)
        elif act.kind == "play":
            if distance(c.pos, target.pos) > 1:
                self._approach(c, target, 1)
            else:
                rng = self.rng_for("play", c.id)
                step = (c.pos[0] + rng.randint(-1, 1), c.pos[1] + rng.randint(-1, 1))
                if self.world.walkable(step):
                    c.pos = step
        if act.ticks_left <= 0:
            self._finish(c)

    def _approach(self, c: Character, target: Character, within: int) -> None:
        path = self.world.path(c.pos, target.pos)
        c.path = path[:-within] if len(path) > within else []
        self._move(c)

    # ------------------------------------------------------------------
    # Physics (non-behavioral)
    # ------------------------------------------------------------------

    def _physics(self) -> None:
        new_day = self.clock.day != self._last_day
        if new_day:
            self._last_day = self.clock.day
            self.log.event(self.clock.tick, "day_start", day=self.clock.day, year=self.clock.year)
            # Once a day, what no question needs leaves the live index
            # (config.forget_the_dead, config.forget_faded).
            memory = self.diffuser.memory
            if memory is not None and (self.config.forget_the_dead or self.config.forget_faded):
                gone = memory.prune(self.clock.tick)
                if gone:
                    self.log.event(self.clock.tick, "memories_left_index", count=gone,
                                   live=len(memory.retriever.corpus))
            # Lessons resting on no news wake with the day
            # (config.lessons_satisfied).
            if memory is not None:
                memory.new_day(self.clock.tick)
            # Word of far-off danger that never came (config.false_alarms).
            if memory is not None and self.config.false_alarms:
                false = memory.false_alarms(self.clock.tick)
                if false:
                    self.log.event(self.clock.tick, "false_alarms", count=false)
            # BEAR records every change to its items for its audit to write
            # out, and only the audit takes them. Nothing here audits, so they
            # piled up for the whole run: 12 GB by year 17 of the seventh long
            # run, most of it the whole index restated at each daily trim.
            # Taken once a day and let go.
            for retriever in (self.retriever,
                              self.diffuser.memory.retriever if self.diffuser.memory else None):
                take = getattr(retriever, "take_item_deltas", None)
                if take is not None:
                    take()
            self.mortality.new_day()
            if self.config.growth:
                self._grow()
        years = self.clock.years_per_tick()
        # A visitor still here a day after it meant to leave goes anyway, so
        # nothing (a long conversation, a night's rest) keeps one for ever.
        for c in self.visitors.present():
            if self.clock.tick >= c.leaves_at + self.clock.ticks_per_day:
                self.visitors.depart(c, self.clock.tick)
        food = self.world_agent.state.food
        season = self.clock.season
        hungry = food.store <= 0
        for c in self.characters.values():
            if not c.alive:
                continue
            c.age += years
            if new_day:
                c.visited_today.clear()
            for place, until in list(c.avoiding.items()):
                if self.clock.tick >= until:
                    del c.avoiding[place]
            place = self.world.place_at(c.pos)
            if place:
                c.visited_today.add(place.id)
                state = self.world_agent.state
                if place.id == "east_road":
                    state.road_walkers.add(c.id)
                elif place.id == "well":
                    state.well_drawers.add(c.id)
                elif place.kind == "fields" and c.activity and c.activity.kind == "work":
                    state.field_workers.add(c.id)
            if not c.resting and c.conversation_id is None:
                c.social = max(0.0, c.social - self.config.social_decay)
            drain = HUNGER_DRAIN if hungry else 1.0
            working = (c.activity is not None and not c.path
                       and (c.activity.kind in CRAFT_WORK or c.activity.kind in ("work", "clear")))
            if c.resting:
                c.energy = min(1.0, c.energy + ENERGY_REST * (HUNGER_REST if hungry else 1.0))
            elif working:
                c.energy = max(0.0, c.energy - ENERGY_WORK * drain)
                # Skill is earned by having chosen to work somewhere, which is
                # why it is counted here rather than awarded at birth.
                if place:
                    c.growth.practised(self._practised_at(c, place.id),
                                       self._practice_ticks(c, place.id))
                if c.activity.kind == "work" and place:
                    # What its trade makes, to sell (hearthwick/economy.py).
                    self.economy.worked(c, place.id, trades.output_factor(
                        trades.level_at(c, place.id)))
                if c.activity.kind in CRAFT_WORK:
                    self._craft_work(c, place)
                elif place and place.kind == "fields":
                    self._field_work(c, food, season, place)
            else:
                c.energy = max(0.0, c.energy - ENERGY_AWAKE * drain)
        if new_day:
            self.courtship.new_day()
        if self.clock.total_minutes % 60 == 0:
            self.courtship.hour_together()

    def _practised_at(self, c: Character, place_id: str) -> str:
        """Where a tick of work counts as practice. Felling and building are
        a crafter's craft, so they count at its trade's site, wherever done."""
        act = c.activity
        if act.kind in ("fell", "build", "smelt", "fetch") or (
                act.kind == "gather" and act.data.get("for") == "building"):
            return trades.site_of(c.trade, self.world) or place_id
        place = self.world.places.get(place_id)
        # Every field is farming practice, the first's and any broken since.
        return FIELDS if place is not None and place.kind == "fields" else place_id

    def _craft_work(self, c: Character, place) -> None:
        """One tick of felling, gathering, smelting, fetching or building."""
        act = c.activity
        factor = trades.output_factor(trades.level_at(c, trades.site_of(c.trade, self.world)))
        here = place.id if place is not None else None
        # Work that would change nothing ends there (section 3, rule 2). Five
        # crafters felling at once took the store to 44 timber for a house
        # that needs 30, because each finished the stint it had started.
        if act.kind == "fell":
            if not self.building.can_fell(c):
                act.ticks_left = 0                 # timber enough
            elif here == FOREST:
                self.building.fell(c, factor)
        elif act.kind == "gather":
            good = act.data["what"]
            spec = self.goods.goods.get(good, {}) if self.goods else {}
            if act.data.get("for") == "building":
                if not self.building.can_gather(c, good):
                    act.ticks_left = 0             # enough of it
                elif here == spec.get("from"):
                    self.building.gather(good, spec.get("gather", 0.0) * factor)
            elif here == spec.get("from"):
                self.economy.gathered(c, good)
        elif act.kind == "smelt":
            if not self.building.can_smelt(c):
                act.ticks_left = 0
            elif here == FORGE:
                self.building.smelt(SMELT_UNIT * factor)
        elif act.kind == "fetch":
            good = act.data["what"]
            if not self.building.can_fetch(c, good):
                act.ticks_left = 0
            elif here == act.data["place"]:
                self.building.gather(good, self.goods.goods.get(good, {}).get("fetch", 0.0))
        elif act.kind == "fight_blight":
            self._fight_blight(c, place)
        elif self.building.site is None or not self.building.ready:
            act.ticks_left = 0                     # the house is up, or the goods gone
        else:
            self.building.work(c, factor, self.clock.tick)

    def _fight_blight(self, c: Character, place) -> None:
        """A tick of cutting the rot out of a blighted field. Enough of them,
        from however many hands, end the blight (section 2.9j)."""
        state = self.world_agent.state
        if FIELDS not in state.sick_places:
            c.activity.ticks_left = 0              # gone, or cut out already
            return
        if place is None or place.kind != "fields":
            return
        state.fought[FIELDS] = state.fought.get(FIELDS, 0.0) + 1.0
        if state.fought[FIELDS] < BLIGHT_FIGHT_TICKS:
            return
        tick = self.clock.tick
        del state.sick_places[FIELDS]
        state.fought.pop(FIELDS, None)
        fighters = sorted(o.id for o in self.characters.values()
                          if o.alive and o.activity is not None and o.activity.kind == "fight_blight")
        self.log.event(tick, "blight_ended", place=FIELDS, by=fighters)
        self.diffuser.witness("blight_cleared", FIELDS, self._nearest_witnesses(FIELDS), {}, tick)
        for fid in fighters:
            self.diffuser.remember(fid, "We cut the blight out of the fields together.", "did", tick)

    def _practice_ticks(self, c: Character, site: str) -> int:
        """An apprentice working beside its master learns twice as fast."""
        if c.stage != "apprentice" or not c.mentor:
            return 1
        master = self.characters.get(c.mentor)
        beside = (master is not None and master.alive and not master.path
                  and master.activity is not None
                  and master.activity.kind in ("work", "fell", "build")
                  and self.world.places[site].contains(*master.pos))
        return trades.MASTER_SPEEDUP if beside else 1

    def _field_work(self, c: Character, food: Food, season: str, place=None) -> None:
        """One tick of a villager's labour in the fields: tending, gathering,
        or clearing new ground at their edge. A skilled hand does more."""
        if c.activity.kind == "work":
            food.work(season, field_tiles(self.world),
                      trades.output_factor(trades.level_at(c, FIELDS)))
        elif food.clear():
            self._clear_fields(c, place.id if place is not None else FIELDS)

    def _clear_fields(self, c: Character, here: str) -> None:
        """A strip's worth of ground cleared: the field grows where it is
        worked, or else another field that can, or else, where no field has
        room and the land may grow, a new field is broken on free ground
        (section 2.9j)."""
        tick = self.clock.tick
        fields = field_places(self.world)
        for place_id in [here] + [p.id for p in reversed(fields) if p.id != here]:
            rect = self.world.grow(place_id)
            if rect is not None:
                self.log.event(tick, "place_grown", place=place_id, rect=list(rect), by=c.id,
                               tiles=field_tiles(self.world))
                return
        if not self.land.able:
            return
        rect = self.land.plot(NEW_FIELD, tick, near_kind="fields")
        if rect is None:
            return
        n = 1 + len(fields)
        name = NEW_FIELD_NAMES[(n - 2) % len(NEW_FIELD_NAMES)] + (
            "" if n - 2 < len(NEW_FIELD_NAMES) else f" {n}")
        new = Place(f"fields_{n}", name, "fields", rect)
        self.world.add_place(new)
        self.log.event(tick, "place_added", place=new.to_dict(), by=c.id)
