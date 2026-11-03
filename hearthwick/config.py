"""Run configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"

# The switches of SPECIFICATION-talk.md this edition keeps, off in a run
# recorded before them and in the paper profile, and addable with --with.
NEW_IN_TALK = ("afar_news", "news_fades")
# Mechanics the paper's runs had switched off, which this edition leaves out
# (README). Their switches stay, so that an archived run's configuration still
# loads, and each must be off.
LEFT_OUT = ("assessing", "bynames", "designs", "fishing", "impersonal_query", "leisure",
            "living_memory", "looking", "memory_gene", "natural_talk", "placing",
            "practices", "search", "time_off", "vehicles", "wants")
CLIENT_DIR = ROOT / "client"


@dataclass
class SimConfig:
    seed: int = 0
    minutes_per_tick: int = 10
    days_per_year: int = 8

    # Retrieval. Situational tags are soft (scope.tags), so the query decides
    # among what a character could do; identity, stage, role and the absolutes
    # (night, speech) stay hard. That only works with dense vectors: measured
    # on one in-game day, BM25 under soft tags picks on lexical overlap and
    # villagers spend the morning talking instead of working.
    gating: str = "soft"          # soft | hard (ablation: see DESIGN.md §14)
    temperament: bool = True      # False strips the temperament instructions, so
                                  # peers of the same stage and role share every
                                  # instruction (the individuality control)
    embedder: str = "service"     # service | bear | bm25 (development, degraded)
    embed_url: str = "http://localhost:8360"
    embed_api_key: str | None = None
    # The model BEAR's own Embedder loads when ``embedder`` is "bear":
    # "openai:<name>" for OpenAI's API (or any server that speaks it, named by
    # OPENAI_BASE_URL), a sentence-transformers name such as
    # BAAI/bge-base-en-v1.5 for a local model, or an MLX model on a Mac. Another
    # embedder makes another village: the threshold below was set for the
    # service's model.
    embed_model: str = ""
    # Stop when the chosen embedder does not answer, rather than fall back to
    # BM25, which the retrieval ablation shows breaks the village. The command
    # line sets it. Library use and the tests keep the fallback.
    embedder_strict: bool = False
    retrieval_threshold: float = 0.15  # dense cosine; BM25 needs 0
    # BEAR's threshold behavior before 226c659 in its development repository.
    # An instruction whose gates pass but which the threshold set aside is put
    # back at a score of priority alone, so the threshold never filters a gated instruction. Off
    # by default. A bear older than the switch always restores, whatever this
    # says, and a run recorded before the switch existed resumes with it on.
    restore_below_threshold: bool = False

    # Brain
    near_radius: int = 4          # tiles within which others count as nearby
    choice_temperature: float = 0.02  # softmax over final scores; 0 = always the
                                      # best-scoring candidate, no sampling
    choice_pool: int = 4          # marker-bearing candidates considered per decision
    world_choice_temperature: float = 0.03  # the world samples among its own best
                                  # candidates the way a villager does. At 0 it
                                  # takes the top-scoring one every time, which
                                  # made its whole ten-day sequence identical
                                  # across seeds and put the evaluation on rails.

    # Growth. Villagers advance a life stage only by meeting every
    # requirement; one that reaches the age without the rest stays where it is
    # and can die there. On by default since children graduate from school into
    # trades (hearthwick/trades.py): without it, nobody in a run grows up.
    growth: bool = True
    consolidate: bool = True      # on advancing, turn what a villager lived
                                  # through into instructions it then carries.
                                  # Needs the speech model; without one a
                                  # villager still grows up, just unchanged.
    consolidate_count: int = 3
    mortality: bool = True        # villagers die of old age (hearthwick/mortality.py)
    land: bool = True            # the map gains open land when no plot is left
                                  # (hearthwick/land.py)
    materials: bool = True        # things are built of timber, stone, clay, iron,
                                  # glass and cloth, not timber alone
                                  # (hearthwick/goods.py)
    money: bool = True            # coins, and the market where goods are sold
                                  # (hearthwick/economy.py)
    fertility: bool = True        # children may be had from 11 to 40, elders
                                  # included, not 11 to 20 (hearthwick/family.py)
    blight_fighting: bool = True  # villagers may cut a blight out of the fields
                                  # together (SPECIFICATION.md section 2.9j)
    richer_fields: bool = True    # the fields yield half as much again
                                  # (hearthwick/food.py, RICH_FIELDS)
    grown_personas: bool = True   # a villager born here is described as it is now,
                                  # its persona rewritten as it grows (hearthwick/family.py)
    chat_turns: bool = True       # a conversation reaches the model as turns, one
                                  # message a line, not as a transcript in one message
    # SPECIFICATION-talk.md. Off here, so code and tests that build a
    # SimConfig keep the behaviour they were written for, and on for a new
    # run from the command line (__main__, each with a --no- flag). A run
    # recorded before these resumes with them off (from_saved), and the paper
    # profile turns them off.
    afar_news: bool = False       # tales and travellers' news are held as from afar,
                                  # and never make a local hazard
    news_fades: bool = False      # a hazard nobody reinforces stops unlocking warnings
                                  # and avoidance, though it is still remembered
    # SPECIFICATION-warnings.md section 3. Off here, in the paper profile and
    # from the command line (--told-memory), unlike the talk switches, so a
    # run gets it only when asked.
    told_memory: bool = False     # villagers remember which news they have shared
                                  # with whom, and pass on only what the listener
                                  # has not had from them
    # SPECIFICATION-warnings.md section 8. Off in the same way (--quick-warnings).
    quick_warnings: bool = False  # a warning is a word to someone within reach,
                                  # passed on in one tick, with no walk and no
                                  # conversation, and nobody stops working
    # SPECIFICATION-memory.md, stage 2. Off in the same way (--bear-memory).
    # Needs a BEAR with items and the importance floor (BEAR v0.3.0).
    bear_memory: bool = False     # villagers' memories are BEAR items, and what
                                  # drives behaviour and what is recalled are
                                  # asked of BEAR
    # SPECIFICATION-warnings.md section 2, stage 3. Needs bear_memory, which
    # --fading-lessons turns on with it.
    fading_lessons: bool = False  # a lesson is a BEAR item that fades with the
                                  # news it came from, and drops out of
                                  # decisions below half its strength
    # SPECIFICATION-memory.md, lessons that last. Needs fading_lessons, which
    # --lasting-lessons turns on with it.
    lasting_lessons: bool = False  # a lesson fades over the years its news
                                   # once took (one for a rumor or a sickness,
                                   # two for a danger), however short the news
                                   # itself now is, unless its news recurs
    # SPECIFICATION-memory.md section 7. Each needs bear_memory, which its
    # flag turns on. Off in the paper profile.
    forget_the_dead: bool = False  # the dead's own memories leave the live
                                   # index, since nobody asks them anything
    forget_faded: bool = False     # a memory faded below a twentieth of its
                                   # strength leaves the live index, and comes
                                   # back if it is lived again
    # SPECIFICATION-memory.md section 8. Needs told_memory, which its flag
    # turns on. Off in the paper profile.
    novel_telling: bool = False   # telling someone of news a topic names only
                                  # when they have not had it from the teller
    # SPECIFICATION-memory.md section 9. Each needs bear_memory, which its flag
    # turns on, and false_alarms needs short_warnings. Off in the paper profile.
    news_ends: bool = False       # a danger that wears off or is cut out is
                                  # news, and marks down what was known of it
    false_alarms: bool = False    # word of far-off danger that has not come
                                  # within a week is marked down
    # SPECIFICATION-memory.md section 10. routine_fades needs bear_memory,
    # which its flag turns on. Off in the paper profile.
    routine_fades: bool = False   # memories of talk and of what one did fade
                                  # over a year, routine news over two
    talk_once_a_day: bool = False  # the same two villagers talk about the same
                                   # thing at most once a day
    # SPECIFICATION-memory.md section 11. Needs fading_lessons. Off in the
    # paper profile.
    lessons_satisfied: bool = False  # a one-shot lesson rests once carried out,
                                     # until its kind of event recurs where its
                                     # news came from, or, resting on no news,
                                     # until the next day
    # SPECIFICATION-memory.md section 12. Needs lessons_satisfied. Off in the
    # paper profile.
    declared_lessons: bool = False  # a lesson declares as it is written which
                                    # news it answers, how often it acts again
                                    # and how long it lasts
    # SPECIFICATION-warnings.md sections 11 and 12. All off in the paper
    # profile.
    teachers_by_pupils: bool = False  # an elder goes to teach only while the
                                      # school has fewer teachers than its
                                      # children need, and otherwise does
                                      # something else
    pupils_per_teacher: int = 15      # children one teacher can take (Scott:
                                      # ten to twenty)
    elders_in_fields: bool = False  # elders help tend and harvest, in
                                    # lighter spells than adults
    work_in_rain: bool = False    # only the easygoing stop work for rain; a
                                  # storm still sends everyone in
    decide_again: bool = False    # a villager whose action ends partway
                                  # through a tick takes up its next one in
                                  # that tick, rather than standing idle until
                                  # the next
    # SPECIFICATION-warnings.md section 10. Needs bear_memory, which
    # --short-warnings turns on. Far-off news is far off only with afar_news.
    short_warnings: bool = False  # what news makes a villager do fades in days,
                                  # and far-off news warns only of a danger that
                                  # can come here
    # SPECIFICATION-warnings.md section 13. Needs told_memory, quick_warnings
    # and bear_memory, which --fresh-warnings turns on. Off in the paper
    # profile.
    fresh_warnings: bool = False  # a warning is about the fresh news that
                                  # unlocked it, passes on only that, and goes
                                  # only to someone the warner has not told it

    # Knowledge
    memory_recall: int = 2        # entries from a villager's own store put into
                                  # its situation. Chosen by relevance to the
                                  # moment when an embedder is available, which
                                  # costs one extra embedding per decision; set
                                  # 0 to fall back to the two most recent, which
                                  # is what this did before and is the control
                                  # arm for whether relevance is worth it.
    memory_by_relevance: bool = True
    remember_conversations: bool = True  # a villager holds only news without it
    duplicate_above: float = 0.85   # cosine at which a fact is the same news
    facts_per_conversation: int = 2
    avoid_ticks: int = 72           # how long a villager steers clear of a place

    # Conversations
    talk_turns: tuple[int, int] = (2, 4)
    talk_max_ticks: int = 9       # conversations end after this many ticks
    talk_approach_ticks: int = 18  # give up walking to a partner after this long
    talk_social_gain: float = 0.5  # social meter filled by one conversation
    social_decay: float = 0.01     # per waking tick
    wants_company_below: float = 0.5
    linger_ticks: int = 3          # time spent at a destination with nothing queued

    # LLM (OpenAI-compatible endpoint). None disables speech generation.
    llm_base_url: str | None = "http://localhost:8355/v1"
    llm_model: str | None = None  # None: first model the server lists
    llm_api_key: str | None = None  # set when the server was started with --api-key
    # A hosted model instead of a server: "anthropic", "openai" or "gemini",
    # through BEAR's backend for it, with its key from the environment or .env
    # (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY) and llm_model naming
    # the model. None: the OpenAI-compatible server at llm_base_url.
    llm_provider: str | None = None
    llm_concurrency: int = 4
    llm_max_tokens: int = 80
    llm_temperature: float = 0.8
    # Sampling beyond the temperature. The paper's September runs sent none,
    # and the model server filled them from the model card (Qwen3.8's
    # generation_config.json: top-p 0.95, top-k 20). The server stopped doing
    # that on 2026-10-12, so they are sent with every
    # request now, and a run samples the same whatever the server's defaults.
    # None sends nothing, which is how a run recorded before them resumes.
    llm_top_p: float | None = 0.95
    llm_top_k: int | None = 20
    # How long a call waits for the model server or the embedding service to
    # answer again after it stops, before the model's call counts as failed
    # or the run stops for want of the embedder (SPECIFICATION.md, "When a
    # server goes down"). A lockstep run waits with the call, so waiting
    # changes nothing in its outcome. Zero waits not at all, as runs before
    # 2026-10-18 did.
    server_wait_minutes: float = 30.0

    # Lockstep: each tick waits for pending LLM calls. Reproducible ordering,
    # use for paper runs. Live viewing runs without it.
    lockstep: bool = False

    village: str | None = None    # data/villages/<name>/, else the hand-written one
    data_dir: Path = field(default=DATA_DIR)
    runs_dir: Path = field(default=RUNS_DIR)

    # The switches of mechanics left out of this edition (LEFT_OUT), and the
    # settings only they read. An archived run records them, so they are
    # accepted, and they do nothing. A switch among them must be off.
    impersonal_query: bool = False
    practices: bool = False
    practice_reinforcement: float = 0.0
    designs: bool = False
    wants: bool = False
    search: bool = False
    search_budget: int = 100
    vehicles: bool = False
    assessing: bool = False
    looking: bool = False
    placing: bool = False
    natural_talk: bool = False
    talk_turns_natural: tuple[int, int] = (4, 6)
    talk_tokens_natural: int = 120
    living_memory: bool = False
    bynames: bool = False
    time_off: bool = False
    farm_time_off: str = "harvest"
    leisure: bool = False
    fishing: bool = False
    memory_gene: bool = False

    def __post_init__(self) -> None:
        on = [name for name in LEFT_OUT if getattr(self, name)]
        if on:
            raise ValueError(
                f"{', '.join(on)} {'is' if len(on) == 1 else 'are'} not in this edition, "
                "which keeps only the mechanics the paper's runs used (README)")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["data_dir"] = str(self.data_dir)
        d["runs_dir"] = str(self.runs_dir)
        # This is the run's record, which is published with its logs, so it
        # says whether a key was set and never what it is. A resume takes keys
        # from the command line anyway (CONNECTION).
        for name in self.SECRETS:
            if d.get(name):
                d[name] = "(set)"
        return d

    SECRETS = ("llm_api_key", "embed_api_key")

    # Where a run reaches its services. These belong to the machine rather than
    # to the run, so a resume takes them from the command line.
    CONNECTION = ("llm_base_url", "llm_model", "llm_api_key", "llm_provider",
                  "llm_concurrency", "embed_url", "embed_api_key", "embedder_strict")

    @classmethod
    def from_saved(cls, saved: dict, current: "SimConfig") -> "SimConfig":
        """The configuration a run was started with, as recorded in its meta.json.

        Everything that shapes the village comes from the record, so a resumed
        run is the run it was. Paths and service connections come from
        ``current``, because the machine may have changed since.
        """
        names = {f.name for f in fields(cls)}
        kept = {k: v for k, v in saved.items()
                if k in names and k not in cls.CONNECTION and k not in ("data_dir", "runs_dir")}
        # A mechanic added since a run was recorded stays off when it resumes,
        # so it stays the run it was: nobody dies, the map keeps its size, and
        # everything is built of timber, for nothing. ``--with`` turns one on
        # for a run on purpose.
        kept.setdefault("mortality", False)
        kept.setdefault("land", False)
        kept.setdefault("materials", False)
        kept.setdefault("money", False)
        kept.setdefault("fertility", False)
        kept.setdefault("blight_fighting", False)
        kept.setdefault("richer_fields", False)
        kept.setdefault("grown_personas", False)
        kept.setdefault("chat_turns", False)
        # A run recorded before BEAR's threshold fix was retrieved with what
        # the threshold set aside put back, so it resumes that way.
        kept.setdefault("restore_below_threshold", True)
        # A run recorded before its sampling values were sent sends none.
        kept.setdefault("llm_top_p", None)
        kept.setdefault("llm_top_k", None)
        for name in NEW_IN_TALK:
            kept.setdefault(name, False)
        for name in ("talk_turns", "talk_turns_natural"):
            if name in kept:
                kept[name] = tuple(kept[name])
        return cls(**kept, **{k: getattr(current, k) for k in cls.CONNECTION},
                   data_dir=current.data_dir, runs_dir=current.runs_dir)
