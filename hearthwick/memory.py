"""Villagers' memories as BEAR items (config.bear_memory, SPECIFICATION-memory.md).

Each fact a villager holds is also a BEAR item it owns, in one memory
retriever the village shares. What drives behaviour (the ``knows_`` tags) and
what a villager brings to mind (recall) are asked of BEAR, which fades each
item by the half-life its kind sets, in ticks of the run's own year
(BEAR's design for agents' memory).

Hearthwick keeps its own record of every fact for what that design leaves to
the application: what counts as the same news, what a villager would bring up
in talk, and the provenance the log reports. The two are written together, so
they cannot hold different facts.

With ``news_fades`` on, an item's half-life is its kind's fading span, and
``min_salience`` 0.5 drops it exactly when ``news_fades`` would, since
``0.5 ** (age / half_life)`` reaches 0.5 at an age of one half-life. With it
off, nothing is asked to fade. Either way a run's knowledge tags are the same
as under Hearthwick's own store, and recall ranks by similarity alone, as
before, until significance is turned on.

Needs a BEAR with items and the importance floor (BEAR v0.3.0 or later).
It is imported only with the switch, so a run without it keeps working on an
older BEAR.
"""

from __future__ import annotations

import numpy as np
from bear import Context, Corpus, ScopeCondition
from bear.retriever import Embedder
from bear.items import ITEM_FACET, class_tag, item
from bear.ownership import owner_tag

from hearthwick.knowledge import (CAN_COME, ENDINGS, FADE_YEARS, Fact, KnowledgeStore,
                                  arrival_kinds, root_parts)

# How long, in in-game days, a kind drives behaviour with config.short_warnings:
# a danger or a sickness about a week, a season at 28-day years, a rumour three
# days. The memory stays, and only sinks in recall.
FADE_DAYS = {"hazard": 7, "sickness": 7, "rumor": 3}

# Facts are a class of item, so a question about facts never admits another
# kind of item a villager may come to own, such as a lesson.
FACT_CLASS = "fact"
# Descriptive tags for selecting a villager's news apart from its own life.
NEWS, LIFE = "news", "experience"
# A query that only selects needs some text. It is embedded once and cached.
SELECT_ONLY = "what this villager holds"


def half_life(kind: str, ticks_per_year: int) -> float | None:
    """How fast a kind fades, in ticks, or None for a kind that does not."""
    years = FADE_YEARS.get(kind)
    return years * ticks_per_year if years is not None else None


# Lessons as memories (config.fading_lessons, SPECIFICATION-warnings.md
# section 2). A lesson rests on the facts it was written from that its words
# are close to. Measured on the second long run's lessons with the embedding
# service: a lesson about news is 0.6 to 0.69 from its source and about 0.3
# from the rest, and a lesson about where to sleep is 0.4 or less from
# everything, so it rests on none and does not fade.
SOURCE_SIMILARITY = 0.5
# A lesson below half its strength drops out of decisions, as a fact below
# half its strength stops setting knowledge tags.
LESSON_FLOOR = 0.5
# A memory below this share of its strength leaves the live index
# (config.forget_faded): a danger about a month after it was last lived
# under short warnings, a rumour after about two weeks. Long before then it
# had stopped setting knowledge tags (0.5), so only recall loses it.
FORGET_BELOW = 0.05
# Years over which routine memories fade (config.routine_fades): talk, what
# a villager did or told, a chance that came up, and the news of the day.
# Without it they never fade, and with forget_faded the live index still
# grew with them, from 80 memories a villager to 148 by year 17 of the
# seventh long run.
ROUTINE_FADE_YEARS = {"met": 1.0, "did": 1.0, "told": 1.0, "opportunity": 1.0,
                      "news": 2.0}
# Word of a danger from beyond the village that has not come within this
# many days of being heard is a false alarm (config.false_alarms).
DEADLINE_DAYS = 7
# A lesson whose every action is one of these has a goal that is met once it
# is carried out (config.lessons_satisfied): telling, warning, going, following,
# keeping away. Work, rest, gathering and clearing are habits and never rest.
ONE_SHOT = frozenset({"talk", "warn", "go", "follow", "avoid", "wander", "play"})
# What a lesson declares as it is written (config.declared_lessons,
# SPECIFICATION-memory.md section 12): how often it acts again once carried
# out, and how long it stays. The writer is shown each name with its meaning
# (BEAR's EvolutionConfig.recurrences and .lifetimes). A lesson that declares
# none, or was written without the switch, recurs as its actions suggest
# (``MemoryIndex.recurs_of``) and lasts as its news does.
RECURRENCES = {
    "each_time": "once each time the event it answers happens: after carrying it "
                 "out, not again until that kind of event happens again at the "
                 "same place",
    "each_day": "at most once a day, as a daily routine",
    "always": "whenever it applies, as often as it applies, as work and rest do",
}
LIFETIMES = {
    "news": "as long as the news it answers stays fresh",
    "season": "about a season",
    "year": "about a year",
    "life": "for the rest of the villager's life",
}
# The share of a year each lifetime stands for, as the lesson's half-life,
# since a lesson below half its strength leaves decisions (LESSON_FLOOR).
# None never fades. "news" follows the news it answers.
LIFETIME_YEARS = {"season": 0.25, "year": 1.0, "life": None}


def lesson_sources(sim, content: str, facts: list[Fact]) -> list[Fact]:
    """The facts a lesson rests on, among those it was written from. None
    without the embedding service, which is the only judge of closeness."""
    embedder = sim.embedder
    if embedder is None:
        return []
    try:
        vector = np.asarray(embedder.embed_single(content, is_query=False), dtype=float)
    except Exception:  # noqa: BLE001 - a lesson without sources simply does not fade
        return []
    found = []
    for fact in facts:
        if fact.vector is None:
            continue
        v = np.asarray(fact.vector, dtype=float)
        similarity = float(v @ vector / (np.linalg.norm(v) * np.linalg.norm(vector) + 1e-12))
        if similarity >= SOURCE_SIMILARITY:
            found.append(fact)
    return found


def as_lesson(memory: "MemoryIndex", instruction, owner: str, sources: list[Fact],
              now: int):
    """A learned instruction as a BEAR item whose significance follows its
    sources: the shortest fading span among them, or none if none fades.

    Made with ``item`` and its sources as parents rather than with
    ``respond``, which would make the lesson demand its parents' class
    ``fact`` and so keep it out of decisions. The instruction's own gates
    (daytime, the night, a place it is set in) stay hard gates beside BEAR's
    item facet and owner tag.
    """
    meta = instruction.metadata or {}
    declared = memory.sim.config.declared_lessons
    # What it declared as it was written (config.declared_lessons): how it
    # recurs, read by MemoryIndex.recurs_of, and how long it lasts.
    lasts = meta.get("lasts") if declared and meta.get("lasts") in LIFETIMES else None
    recurs = meta.get("recurs") if declared and meta.get("recurs") in RECURRENCES else None
    made = item(instruction.content, owner, id=instruction.id, kind="lesson",
                parents=[f.id for f in sources], root=sources[0].root if sources else None,
                created=float(now), half_life=memory.lifetime_of(lasts, sources, owner),
                priority=instruction.priority,
                **({"recurs": recurs, "lasts": lasts} if declared else {}))
    required = sorted(set(made.scope.required_tags) | set(instruction.scope.required_tags or []))
    return made.model_copy(update={
        "scope": ScopeCondition(required_tags=required, tags=list(instruction.scope.tags or [])),
        "metadata": {**(instruction.metadata or {}), **made.metadata}})


class MemoryIndex:
    """The village's memories in one BEAR retriever, each owned by one villager."""

    def __init__(self, sim) -> None:
        from hearthwick.corpus import build_retriever

        self.sim = sim
        self.ticks_per_year = sim.clock.ticks_per_day * sim.clock.days_per_year
        # Every fact is a candidate however unlike the question it is, as in
        # KnowledgeStore.recall, so no similarity threshold.
        # BEAR fades items only in a dense index, so without the embedding
        # service the index uses BEAR's hash vectors. Recall then falls back
        # to recency, as Hearthwick's own store does (BearKnowledgeStore).
        embedder = sim.embedder if sim.embedder is not None else Embedder(model_name="hash")
        self.retriever = build_retriever(Corpus(), embedder=embedder, threshold=-1.0)
        self._pending: dict[str, float] = {}      # reinforcements waiting for the next question
        self._loading: list | None = None
        # Facts taken out of the live index (config.forget_faded,
        # config.forget_the_dead). Hearthwick's own record of each stays.
        self.dropped: set[str] = set()
        # Facts marked down because the danger ended or never came
        # (config.news_ends, config.false_alarms), and the far-off dangers
        # already judged, whether they came or not.
        self.marked_down: set[str] = set()
        self.judged: set[str] = set()

    def half_life_of(self, kind: str, holder: str, tags=()) -> float | None:
        """How fast this villager's memory of a kind fades, in ticks: the kind's
        span.

        With config.short_warnings the spans are days, not years, since a
        warning should not outlast its news by years, and anything that can
        come here fades as a danger does, whatever kind it was given.

        With config.routine_fades, routine memories fade over the years of
        ROUTINE_FADE_YEARS, short warnings or not."""
        if (self.sim.config.routine_fades and kind in ROUTINE_FADE_YEARS
                and CAN_COME not in tags):
            return ROUTINE_FADE_YEARS[kind] * self.ticks_per_year
        if self.sim.config.short_warnings:
            days = FADE_DAYS["hazard"] if CAN_COME in tags else FADE_DAYS.get(kind)
            span = days * self.sim.clock.ticks_per_day if days is not None else None
        else:
            span = half_life(kind, self.ticks_per_year)
        return span

    def lesson_half_life_of(self, fact: Fact, holder: str) -> float | None:
        """How fast a lesson resting on ``fact`` fades, in ticks. As the fact
        does, or with config.lasting_lessons over the years a fact of its kind
        took before short warnings (one for a rumor or a sickness, two for a
        danger), however short the fact's own span. A lesson is what someone
        made of the news, and outlasts the news itself. It still strengthens
        when its news recurs (_lessons_by_source)."""
        if not self.sim.config.lasting_lessons:
            return self.half_life_of(fact.kind, holder, fact.tags)
        kind = "hazard" if CAN_COME in fact.tags else fact.kind
        return half_life(kind, self.ticks_per_year)

    # -- writing ------------------------------------------------------------

    def dated(self, fact: Fact) -> int:
        """When a memory's clock starts: when it was learned, or last lived
        again. With config.far_danger_dated, word of a danger abroad that can
        come here starts from when it reached the village, its root's tick,
        unless it was renewed since: lived again by its holder, or, for a
        copy told on, renewed in the telling it came from (Diffuser.offer).
        Counted from the hearing, a tale first told on day 46 was fresh again
        for each villager who heard it, and on day 177 of a ten-year run it
        still went out as a warning (SPECIFICATION-warnings.md section 14)."""
        if fact.refreshed is not None:
            return fact.refreshed
        if self.sim.config.far_danger_dated and CAN_COME in fact.tags:
            return min(fact.tick, root_parts(fact.root, fact.tick)[2])
        return fact.tick

    def _item(self, fact: Fact):
        tags = [NEWS if not fact.is_experience else LIFE, f"kind:{fact.kind}", *fact.tags]
        return item(fact.text, fact.holder, id=fact.id, classes=[FACT_CLASS],
                    tags=tags, kind=fact.kind,
                    parents=[fact.parent] if fact.parent else [], root=fact.root,
                    created=float(self.dated(fact)),
                    half_life=self.half_life_of(fact.kind, fact.holder, fact.tags))

    def add(self, fact: Fact) -> None:
        if self._loading is not None:
            self._loading.append(self._item(fact))
            return
        self.retriever.add(self._item(fact))

    def reinforce(self, fact_id: str, now: int) -> None:
        """Witnessed again at ``now``: its clock restarts at the next question,
        so a tick's reinforcements reach BEAR together."""
        self._pending[fact_id] = float(now)

    def _flush(self) -> None:
        if not self._pending:
            return
        by_time: dict[float, list[str]] = {}
        for fact_id, now in self._pending.items():
            by_time.setdefault(now, []).append(fact_id)
        self._pending = {}
        lessons = self._lessons_by_source() if self.sim.config.fading_lessons else {}
        for now, ids in sorted(by_time.items()):
            self.retriever.reinforce(ids, now)
            # A lesson's news witnessed again brings the lesson back with it,
            # and wakes it if it rested (config.lessons_satisfied).
            renewed = sorted({lesson for i in ids for lesson in lessons.get(i, ())})
            if renewed:
                self.sim.retriever.reinforce(renewed, now)
                self.rekindle(renewed, int(now))

    def _lessons_by_source(self) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for inst in self.sim.corpus.instructions:
            if (inst.metadata or {}).get("kind") == "lesson":
                for parent in inst.metadata.get("parents") or []:
                    found.setdefault(parent, set()).add(inst.id)
        return found

    # -- the live index ---------------------------------------------------

    def prune(self, now: int) -> int:
        """Take out of the live index what no question needs any more: the
        memories of the dead (config.forget_the_dead), whom nobody asks, and
        memories faded below FORGET_BELOW of their strength
        (config.forget_faded). Nothing is deleted. Each villager's own record
        of a fact stays, and a fact lived again comes back (``readd``).
        Returns how many left. BEAR rebuilds the index from what is left,
        reading the vectors back from the embedder's documents."""
        cfg = self.sim.config
        out: list[str] = []
        for holder, store in self.sim.diffuser.stores.items():
            facts = getattr(store, "_by_id", None)
            if not facts:
                continue
            c = self.sim.characters.get(holder)
            dead = cfg.forget_the_dead and c is not None and not c.alive
            for fact in facts.values():
                if fact.id in self.dropped:
                    continue
                if dead or (cfg.forget_faded and (fact.id in self.marked_down
                                                  or self.faded(fact, now))):
                    out.append(fact.id)
        if out:
            self.retriever.remove(out)
            self.dropped.update(out)
        return len(out)

    def faded(self, fact: Fact, now: int) -> bool:
        """Below FORGET_BELOW of its strength at ``now``, counting from when it
        was learned or last lived again. A fact of a kind that never fades
        never is."""
        span = self.half_life_of(fact.kind, fact.holder, fact.tags)
        if not span:
            return False
        return 0.5 ** ((now - self.dated(fact)) / span) < FORGET_BELOW

    def readd(self, fact: Fact) -> None:
        """A fact out of the live index, lived again: back in, its clock
        started again from ``fact.refreshed``."""
        self.dropped.discard(fact.id)
        self.retriever.add(self._item(fact))
        if fact.id in self.marked_down:
            self.retriever.adjust([fact.id], scale=0.0)

    # -- news that ended, or never came -------------------------------------

    def mark_down(self, ids) -> None:
        """Take these facts' strength away (BEAR's ``adjust``), and with
        fading lessons every lesson resting only on facts so marked. BEAR's
        ``supersedes`` acts only when the old and the new item come up in one
        retrieval, which a lesson and its sources never do, so the
        application names what it ends (design/agent-memory.md section 5.3)."""
        new = [i for i in ids if i not in self.marked_down]
        if not new:
            return
        self.marked_down.update(new)
        live = [i for i in new if i not in self.dropped]
        if live:
            self.retriever.adjust(live, scale=0.0)
        if not self.sim.config.fading_lessons:
            return
        lessons = self._lessons_by_source()
        down = []
        for lesson_id in sorted({l for i in new for l in lessons.get(i, ())}):
            inst = self.sim.corpus.get(lesson_id)
            parents = (inst.metadata or {}).get("parents") or [] if inst is not None else []
            if parents and all(p in self.marked_down for p in parents):
                down.append(lesson_id)
        if down:
            if self.sim.config.lessons_satisfied:
                # At rest, so the same kind of event at the same place wakes it.
                self.sim.retriever.rest(down, float(self.sim.clock.tick))
            else:
                self.sim.retriever.adjust(down, scale=0.0)

    # -- a lesson's urge: met, and rekindled (config.lessons_satisfied) ------
    # A lesson at rest carries BEAR's resting mark (bear.items.rest), which a
    # checkpoint keeps with the rest of its metadata.

    def recurs_of(self, inst) -> str:
        """How a lesson acts again once carried out, a name of RECURRENCES.

        As it declared (config.declared_lessons), or else as its actions
        suggest: one whose every action is one-shot (ONE_SHOT) recurs each
        time its event happens, and any other is a habit. Either way a lesson
        answering no news cannot wait for its event, so it recurs each day."""
        meta = inst.metadata or {}
        recurs = meta.get("recurs")
        if recurs not in RECURRENCES:
            from bear import parse_actions
            kinds = {a.name for a in parse_actions(inst.content)}
            recurs = "each_time" if kinds and kinds <= ONE_SHOT else "always"
        if recurs == "each_time" and not meta.get("parents"):
            recurs = "each_day"
        return recurs

    def satisfied(self, who: str, instruction_id: str | None, now: int) -> bool:
        """``who`` has carried out ``instruction_id``. A lesson of its own
        that does not recur always has met its goal, and rests: its strength
        goes to nothing, so it leaves decisions, until something wakes it. In a
        trial run without this an apprentice warned the neighbours 114 times
        in a day by one lesson, and an elder followed whoever sat at the inn
        all afternoon. Returns whether it rests."""
        if not (self.sim.config.lessons_satisfied and instruction_id):
            return False
        inst = self.sim.corpus.get(instruction_id)
        meta = (inst.metadata or {}) if inst is not None else {}
        if meta.get("layer") != "learned" or meta.get("character") != who:
            return False
        if self.recurs_of(inst) == "always":
            return False
        self.sim.retriever.rest([instruction_id], float(now))
        return True

    def resting(self) -> list[str]:
        """The lessons at rest."""
        if not self.sim.config.lessons_satisfied:
            return []
        return self.sim.retriever.resting()

    def rekindle(self, ids, now: int) -> int:
        """Wake these lessons, if they rest, as an event does: not one that
        recurs each day, which only the day wakes. Returns how many woke."""
        wanted = [i for i in sorted(set(ids)) if self.sim.corpus.get(i) is not None
                  and self.recurs_of(self.sim.corpus.get(i)) != "each_day"]
        return self.sim.retriever.wake(wanted, float(now)) if wanted else 0

    def rekindled_by(self, fact: Fact) -> list[str]:
        """The resting lessons of ``fact``'s holder that it rekindles: those
        resting on news of the same kind of event at the same place, from
        before it. A new raid on the east road wakes a lesson about raiders
        there."""
        resting = self.resting()
        if not resting:
            return []
        kind, place, tick = root_parts(fact.root, fact.tick)
        facts = self._facts_of(fact.holder)
        found = []
        for lesson_id in resting:
            inst = self.sim.corpus.get(lesson_id)
            meta = (inst.metadata or {}) if inst is not None else {}
            if meta.get("character") != fact.holder:
                continue
            for parent in meta.get("parents") or []:
                source = facts.get(parent)
                if source is None or source.id == fact.id:
                    continue
                k, p, t = root_parts(source.root, source.tick)
                if (k, p) == (kind, place) and tick > t:
                    found.append(lesson_id)
                    break
        return found

    def new_day(self, now: int) -> int:
        """Wake the lessons that recur each day and rested on an earlier day,
        except one whose news all ended, which only its event wakes. Returns
        how many woke."""
        resting = self.resting()
        if not resting:
            return 0
        from bear.items import due
        wake = []
        for lesson_id in resting:
            inst = self.sim.corpus.get(lesson_id)
            if inst is None or self.recurs_of(inst) != "each_day":
                continue
            parents = (inst.metadata or {}).get("parents") or []
            if parents and all(p in self.marked_down for p in parents):
                continue
            if due(inst, float(now), float(self.sim.clock.ticks_per_day)):
                wake.append(lesson_id)
        return self.sim.retriever.wake(wake, float(now)) if wake else 0

    def lifetime_of(self, lasts: str | None, sources: list[Fact], holder: str) -> float | None:
        """A lesson's half-life in ticks, from what it declared it lasts
        (config.declared_lessons). "news", or nothing declared, follows the
        news it answers: the shortest span among its sources, or none if none
        fades. A lesson declared to last as its news does but answering none
        lasts a season."""
        if lasts in LIFETIME_YEARS:
            years = LIFETIME_YEARS[lasts]
            return None if years is None else years * self.ticks_per_year
        halves = [h for h in (self.lesson_half_life_of(f, holder) for f in sources)
                  if h is not None]
        if halves:
            return min(halves)
        if lasts == "news":
            return LIFETIME_YEARS["season"] * self.ticks_per_year
        return None

    def _facts_of(self, holder: str) -> dict:
        store = self.sim.diffuser.stores.get(holder)
        return getattr(store, "_by_id", None) or {}

    @staticmethod
    def _ends(ending: str, place: str, tick: int, fact: Fact) -> bool:
        kind, where, when = root_parts(fact.root, fact.tick)
        return kind in ENDINGS[ending] and where == place and when <= tick

    def on_stored(self, fact: Fact) -> None:
        """With config.news_ends, an ending marks down what its holder knew of
        the danger it ended, at that place and from before it. Old news of a
        danger its holder already knows has ended is marked down as it comes."""
        if not self.sim.config.news_ends:
            return
        kind, place, tick = root_parts(fact.root, fact.tick)
        facts = self._facts_of(fact.holder)
        if kind in ENDINGS:
            self.mark_down([f.id for f in facts.values()
                            if f.id != fact.id and self._ends(kind, place, tick, f)])
            return
        for other in facts.values():
            k, p, t = root_parts(other.root, other.tick)
            if k in ENDINGS and self._ends(k, p, t, fact):
                self.mark_down([fact.id])
                return

    def false_alarms(self, now: int) -> int:
        """With config.false_alarms, word of a danger from beyond the village
        that has not come within DEADLINE_DAYS of being heard, by all its
        holder has seen or heard of since, is marked down. Each is judged
        once. Returns how many were false."""
        if not self.sim.config.false_alarms:
            return 0
        deadline = DEADLINE_DAYS * self.sim.clock.ticks_per_day
        # With config.far_danger_dated, the week runs from when the word
        # reached the village, and only an arrival within it bears the word
        # out. Without it, any arrival after the word began did, however much
        # later, so one raid kept every older tale of fighting alive
        # (SPECIFICATION-warnings.md section 14).
        dated = self.sim.config.far_danger_dated
        false = []
        for holder, store in self.sim.diffuser.stores.items():
            c = self.sim.characters.get(holder)
            facts = getattr(store, "_by_id", None) or {}
            if c is None or not c.alive or not facts:
                continue
            due = [f for f in facts.values() if CAN_COME in f.tags and f.id not in self.judged
                   and now - (self.dated(f) if dated else f.tick) >= deadline]
            if not due:
                continue
            latest: dict[str, int] = {}
            seen: dict[str, list[int]] = {}
            for f in facts.values():
                k, _, t = root_parts(f.root, f.tick)
                if t > latest.get(k, -1):
                    latest[k] = t
                seen.setdefault(k, []).append(t)
            for f in due:
                self.judged.add(f.id)
                _, _, born = root_parts(f.root, f.tick)
                if dated:
                    came = any(born <= t <= born + deadline
                               for k in arrival_kinds(f.text) for t in seen.get(k, ()))
                else:
                    came = any(latest.get(k, -1) >= born for k in arrival_kinds(f.text))
                if not came:
                    false.append(f.id)
        self.mark_down(false)
        return len(false)

    def recompute(self, now: int) -> None:
        """After a checkpoint is restored: mark down again what ended or never
        came, by the same rules, since restored items start at full strength."""
        for store in self.sim.diffuser.stores.values():
            for fact in list((getattr(store, "_by_id", None) or {}).values()):
                self.on_stored(fact)
        self.false_alarms(now)

    def begin_load(self) -> None:
        """Facts restored from a checkpoint come next. They are indexed in one
        build at ``end_load``, not one append each."""
        self._pending = {}
        self._loading = []
        self.dropped = set()
        self.marked_down = set()
        self.judged = set()

    def end_load(self) -> None:
        items, self._loading = self._loading or [], None
        corpus = Corpus()
        corpus.add_many(items)
        self.retriever.corpus = corpus
        self.retriever.build_index()

    # -- asking -------------------------------------------------------------

    def _context(self, holder: str, select: list[str], now: int | None,
                 floor: float | None) -> Context:
        owner = owner_tag(holder)
        return Context(gate_tags=[ITEM_FACET, owner, class_tag(FACT_CLASS)],
                       select_all=[owner, *select],
                       now=None if now is None else float(now), min_salience=floor)

    def salient(self, holder: str, now: int | None) -> list[str]:
        """The ids of a villager's news that still drive behaviour: those above
        half their strength at ``now``, or all of them when ``now`` is None."""
        self._flush()
        floor = None if now is None else 0.5
        found = self.retriever.retrieve(SELECT_ONLY, self._context(holder, [NEWS], now, floor),
                                        top_k=self.retriever.ALL)
        return [s.instruction.id for s in found]

    def recall(self, holder: str, text: str, limit: int) -> list[str]:
        """The ids of what a villager brings to mind about ``text``: news first,
        its own life filling what is left. Ranked by similarity, since nothing
        here asks to fade."""
        self._flush()
        if limit <= 0:
            return []

        def ask(select: list[str], want: int) -> list[str]:
            if want <= 0:
                return []
            found = self.retriever.retrieve(text, self._context(holder, select, None, None),
                                            top_k=want)
            return [s.instruction.id for s in found]

        news = ask([NEWS], limit)
        return news + ask([LIFE], limit - len(news))


class BearKnowledgeStore(KnowledgeStore):
    """A villager's facts, with its knowledge tags and its recall asked of BEAR."""

    def __init__(self, holder: str, duplicate_above: float, memory: MemoryIndex):
        super().__init__(holder, duplicate_above)
        self.memory = memory
        self._by_id: dict[str, Fact] = {}

    def add(self, fact: Fact) -> None:
        super().add(fact)
        self._by_id[fact.id] = fact
        self.memory.add(fact)
        if self.memory._loading is None:
            self.memory.on_stored(fact)
            if self.memory.sim.config.lessons_satisfied:
                self.memory.rekindle(self.memory.rekindled_by(fact), fact.tick)

    def clear(self) -> None:
        super().clear()
        self._by_id.clear()

    def reinforce(self, fact: Fact, refreshed: int | None = None) -> None:
        super().reinforce(fact, refreshed)
        if refreshed is not None:
            if fact.id in self.memory.dropped:
                self.memory.readd(fact)
            self.memory.reinforce(fact.id, refreshed)

    def fresh(self, now: int | None) -> list[Fact]:
        """The news that still drives behaviour at ``now``: what BEAR holds
        above half its strength, or all of it when ``now`` is None."""
        return [self._by_id[i] for i in self.memory.salient(self.holder, now)
                if i in self._by_id]

    def tags(self, now: int | None = None, fade: dict[str, int] | None = None) -> list[str]:
        return sorted({t for t in (f.tag for f in self.fresh(now if fade else None)) if t})

    def recall(self, vector, limit: int = 2, text: str | None = None) -> list[Fact]:
        # Without the words or an embedder, recall is by recency, as before.
        if text is None or vector is None or self.memory.sim.embedder is None:
            return super().recall(vector, limit)
        ids = self.memory.recall(self.holder, text, limit)
        return [self._by_id[i] for i in ids if i in self._by_id]
