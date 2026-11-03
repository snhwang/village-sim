"""What a villager becomes, out of what it has lived through.

When a character advances a life stage, the most reinforced things it knows and
the situations its instructions served it worst are turned into two or three new
instructions that it carries from then on. This is the only place in the system
where the corpus itself grows: everywhere else a villager's reach changes
because a tag made an authored instruction retrievable, and here a villager
gains an instruction nobody wrote.

Three things had to be got right, and two of them were found by the probe that
tested this step in isolation before the milestone was built around it
(``results/consolidation_probe.md``):

  scope      generated instructions come back with none. Added to a shared
             corpus ungated they are retrievable by the whole village, so one
             child's lesson becomes law. Every one is gated on its owner, and
             ``tests/test_isolation.py`` asserts that nobody else can reach it
  night      an authored action instruction is gated on ``daytime`` by
             convention, and the village sleeping at night is the one guarantee
             the design does not want an embedder deciding. A learned
             instruction that moves a villager inherits that gate
  priority   learned instructions sit below authored ones, so what a villager
             worked out for itself competes with the life-stage protocols
             rather than overruling them

Provenance is recorded per instruction: which facts and which weak moments it
came from, so "why does Bryn avoid the fields?" is answerable years later.
"""

from __future__ import annotations

import logging
import re
import time

from bear import Instruction, ScopeCondition, parse_actions, parse_kv_args
from bear.evolution import EvaluationResult, EvolutionConfig, Observation, generate_with_llm
from bear.ownership import own

logger = logging.getLogger(__name__)

# Only what the villagers' registry can execute. A marker outside this set is
# silently dropped at dispatch, so an instruction carrying one is an
# instruction that does nothing.
# The markers a villager may write into its own lessons, the same as an
# authored instruction may carry.
VILLAGER_MARKERS = ["go", "wander", "rest", "work", "clear", "talk", "avoid", "warn",
                    "follow", "play", "depart", "apprentice", "have_child", "propose",
                    "accept_proposal", "decline_proposal", "fell", "build",
                    "gather", "save", "smelt", "fetch", "sell", "buy", "fight_blight"]

# The markers of the mechanics this edition leaves out (config.LEFT_OUT), with
# the switches they belonged to. None is offered, and a lesson that carries
# one is refused as the paper's runs refused it, as belonging to a mechanic
# the run had switched off. The reports read the paper's runs by them
# (experiments/long_run_report.py).
LEFT_OUT_MARKERS = {"design": "designs", "want": "wants", "give_up": "wants",
                    "search": "search", "drive": "vehicles", "wear": ("placing", "designs"),
                    "take_off": ("placing", "designs"), "assess": "assessing",
                    "take_up": "assessing", "vacation": "time_off", "swim": "leisure",
                    "tell_tale": "leisure", "listen": "leisure", "fish": "fishing"}

# The argument each marker is resolved by. A generated instruction can carry a
# valid marker name with the wrong argument -- [!avoid(target=Mabel)] when
# avoid takes a place, [!work(place=fields)] when work takes a site -- and
# nothing complains: the handler finds nothing to resolve, returns no action,
# and the instruction is passed over every time it is retrieved. An instruction
# that can never fire is worse than none, because nothing reports it.
MARKER_ARGS = {
    "go": {"to"}, "wander": set(), "rest": {"ticks", "until"},
    "work": {"site", "ticks"}, "clear": {"place", "ticks"}, "talk": {"target", "topic"},
    "avoid": {"place", "ticks"}, "warn": {"target", "topic"},
    "follow": {"target", "ticks"}, "play": {"target", "ticks"},
    # Only a visitor can leave. A villager who wrote itself [!depart] would
    # have it refused, as anyone who lives here does.
    "depart": set(),
    # Only a graduate without a trade can take one up, so a learned
    # instruction carrying this is refused for anyone else.
    "apprentice": {"trade"},
    # Refused unless the couple can support a child, whoever wrote it.
    "have_child": set(),
    # Refused unless courting, or asked (hearthwick/courtship.py).
    "propose": set(), "accept_proposal": set(), "decline_proposal": set(),
    # Refused for anyone but a crafter, and while no house is needed.
    "fell": {"ticks"}, "build": {"ticks"},
    # Refused unless there is something to gather, smelt, fetch or sell
    # (hearthwick/building.py, hearthwick/economy.py). Paying for a wanted
    # thing, and saving toward one, is always refused (markers.BuyHandler).
    "gather": {"what", "for", "ticks"}, "save": {"ticks"}, "smelt": {"ticks"},
    "fetch": {"what", "ticks"}, "sell": set(), "buy": {"what"},
    # Refused unless the fields are blighted (section 2.9j).
    "fight_blight": {"ticks"},
}

# Offered to the model only in a run that has them, so a run without the
# switch is asked exactly as before. The v0.2 mechanics' markers were offered
# to every run until 2026-10-09, so a villager in the paper profile could
# write itself [!want] or [!search], which no handler there would carry out.
# A marker can need more than one switch.
SWITCHED_MARKERS = {"gather": "materials", "smelt": "materials", "fetch": "materials",
                    "save": "money", "sell": "money", "buy": "money",
                    "fight_blight": "blight_fighting", **LEFT_OUT_MARKERS}


def offered_markers(config) -> list[str]:
    """The markers a villager in this run may write into its own lessons."""
    def on(needed):
        names = (needed,) if isinstance(needed, str) else needed
        return all(getattr(config, name, False) for name in names)
    return [m for m in VILLAGER_MARKERS + [m for m in SWITCHED_MARKERS if m not in VILLAGER_MARKERS]
            if m not in SWITCHED_MARKERS or on(SWITCHED_MARKERS[m])]

# The order a handler reads positional arguments in, so [!avoid(well)] is
# checked as place=well. It mirrors markers._arg, which falls back to position.
POSITIONS = {
    "go": ("to",), "rest": ("until", "ticks"), "work": ("site", "ticks"),
    "clear": ("place", "ticks"), "talk": ("target", "topic"), "avoid": ("place",), "warn": ("target", "topic"),
    "follow": ("target", "ticks"), "play": ("target", "ticks"), "apprentice": ("trade",),
    "gather": ("what",), "fetch": ("what",), "buy": ("what",),
}

# What a handler cannot act without. The live consolidation test wrote
# "Go to the mill and inspect the stock. [!go(to=mill)] [!work(ticks=2)]",
# and a work marker with no site resolves to nothing.
REQUIRED = {"go": "to", "work": "site", "clear": "place", "apprentice": "trade", "talk": "target", "avoid": "place",
            "warn": "target", "follow": "target", "play": "target", "gather": "what", "fetch": "what"}

# Arguments whose value must be a place, and the names the resolver accepts in
# place of a place id. Anything else resolves to nothing. The long rehearsal
# produced avoid(place=outside), go(to=house_3) and go(to=village_center),
# none of which is a place here, so those markers never fired.
PLACE_ARGS = {("go", "to"), ("avoid", "place"), ("work", "site"), ("clear", "place")}
PLACE_ALIASES = {"home", "own", "mentor", "usual_place", "quiet_place",
                 "unvisited_place", "random_home", "site"}

# The same for arguments that name a villager. It wrote talk(target=Edek),
# which never fired because ids are lowercase, and talk(target=traveler),
# which names nobody.
TARGET_ARGS = {("talk", "target"), ("warn", "target"), ("follow", "target"),
               ("play", "target")}
TARGET_ALIASES = {"nearby", "nearby_child", "nearby_adult", "parent", "partner", "stranger",
                  "listener", "sweetheart"}

# What each kind of argument is written as, in the signatures the model is
# shown. Until 2026-10-09 the model was shown bare marker names and told not
# to add arguments to a marker shown without one, so it guessed (avoid(site=
# mill)) or left them out (talk with no target). In the long run the check
# refused more than four lessons in five, nine in ten of those on an argument
# (results/long_run/long_run_report.md).
_ARG_FORMS = {"ticks": "<number of ten-minute ticks>", "until": "morning",
              "trade": "<a trade>", "topic": "<what about>",
              "what": "<what>", "for": "<what for>"}


def signature(name: str, places: list[str] | None = None) -> str:
    """How a marker is written, with the arguments its handler reads.

    ``places`` are the place ids a place argument may name, shown beside the
    names the resolver accepts in place of one (``home``, and ``own`` for a
    villager's own workplace).
    """
    order = list(POSITIONS.get(name, ()))
    args = order + sorted(MARKER_ARGS.get(name, set()) - set(order))
    if not args:
        return f"[!{name}]"
    shown = []
    for arg in args:
        if (name, arg) in PLACE_ARGS:
            where = ", ".join(["home", "own"] + list(places or []))
            form = f"<a place: {where}>"
        elif (name, arg) in TARGET_ARGS:
            form = "<a villager's name, or nearby, parent, partner or sweetheart>"
        else:
            form = _ARG_FORMS.get(arg, f"<{arg}>")
        shown.append(f"{arg}={form}")
    needed = REQUIRED.get(name)
    return f"[!{name}({', '.join(shown)})]" + (f" ({needed} is required)" if needed else "")


_TARGET = re.compile(r"(target\s*=\s*)([A-Za-z][\w]*)")
_PLACE_VALUE = re.compile(r"\b(to|place|site)(\s*=\s*)([^,)\]]+)")
_MARKER = re.compile(r"\[![^\]]*\]")

# A sentence that puts the villager somewhere is a premise, and by the first
# design rule a premise is a hard gate. The long rehearsal's "You are at the
# Wick & Kettle inn with Peder, Dunn, Gorm, and Ilsa. Listen to their
# accounts..." carried no place at all, and was used 24 times of 25 at home.
_PREMISE = re.compile(
    r"^\s*(?:(?:while|when|whenever|if)\s+)?(?:you are|you're|you stand|you find yourself)"
    r"\s+(?:at|in|inside|by|near)\b|^\s*(?:while|when|whenever)\s+(?:at|in)\b",
    re.IGNORECASE)

# Markers that take a villager somewhere or occupy it. Night is for sleeping.
MOVES = {"go", "wander", "work", "clear", "follow", "play", "talk", "fell", "build",
         "gather", "save", "smelt", "fetch", "sell", "buy", "fight_blight"}

# Words that say an instruction is about the night. Gating such an instruction
# on `daytime` because it happens to carry a movement marker produces something
# that can never fire -- a villager told to go home and sleep, admitted only
# while the sun is up. Better to gate it on the time it is actually about.
NIGHT_WORDS = ("night", "dark", "sleep", "until morning", "until the light")

# Where a learned instruction sits among the authored ones. Measured bands:
# knowledge-gated 67-78, role 58-65, temperament 48-60, stage 20-90.
#
# A learned instruction is closest in kind to temperament -- a disposition this
# villager acquired -- so it belongs in that band. At 40 they were retrieved
# 28 to 33 times each and reached the candidate pool 0 to 5 times, losing on
# priority before relevance had a say: consolidation was writing character
# nobody ever acted on. Below the knowledge-gated band on purpose, so what a
# villager worked out for itself never outranks what it urgently knows.
MAX_PRIORITY = 58
MIN_PRIORITY = 46       # the foot of the temperament band
PRIORITY_LIFT = 25      # generation returns 10-35; this puts it in range
FACTS_CONSIDERED = 8
GAPS_CONSIDERED = 6


def formative(sim, character) -> tuple[dict[str, int], list[Observation]]:
    """What this villager could not stop being told, and where it was at a loss.

    Facts are ordered by how often the villager heard them again, because the
    probe showed selection does not follow reinforcement on its own: the
    raiders were heard eleven times, as often as the blight, and produced
    nothing. Handing them over already ranked is the cheapest way to steer it.
    """
    store = sim.diffuser.stores.get(character.id)
    held = list(store.facts) if store else []
    # News before experience, and for the same reason recall does it: a villager
    # accumulates far more afternoons than news, so ranking everything together
    # means the most reinforced things it holds are always who it chatted to.
    # Consolidating those produced "return to house 3 and speak with Osric
    # again" instead of "keep away from the blighted fields" -- a villager
    # becoming its address book rather than what it learned.
    news = sorted((f for f in held if not f.is_experience), key=lambda f: -f.reinforced)
    lived = sorted((f for f in held if f.is_experience), key=lambda f: -f.reinforced)
    facts = (news + lived)[:FACTS_CONSIDERED]
    terms = {f.text: f.reinforced for f in facts}

    decision = sim.decisions.get(character.id)
    observations = []
    if decision and decision.get("retrieved"):
        best = max((r["similarity"] for r in decision["retrieved"]), default=0.0)
        observations.append(Observation(
            query=decision["query"], top_similarity=best,
            instruction_ids=[r["id"] for r in decision["retrieved"][:3]],
            response=decision.get("chosen") or "", timestamp=time.time()))
    return terms, observations[:GAPS_CONSIDERED]


def executable(instruction: Instruction, places: set[str] | None = None,
               people: set[str] | None = None,
               offered: set[str] | None = None) -> tuple[bool, str]:
    """Whether every marker in this instruction could actually resolve.

    Checks the names against what the registry implements and the arguments
    against what each handler reads, because a marker whose argument is wrong
    is silently inert rather than an error. Given the village's places and
    people, it also checks that the values name something that exists. Given
    the markers this run offers (``offered_markers``), it refuses one of a
    mechanic the run has switched off, whose handler would never act.
    """
    markers = parse_actions(instruction.content)
    if not markers:
        return False, "no action marker"
    for marker in markers:
        if marker.name in LEFT_OUT_MARKERS:
            return False, f"[!{marker.name}] belongs to a mechanic this run has switched off"
        allowed = MARKER_ARGS.get(marker.name)
        if allowed is None:
            return False, f"[!{marker.name}] is not a marker this village implements"
        if offered is not None and marker.name not in offered:
            return False, f"[!{marker.name}] belongs to a mechanic this run has switched off"
        args = {}
        for key, value in parse_kv_args(marker.args_raw or "").items():
            if key.startswith("_pos_"):
                order = POSITIONS.get(marker.name, ())
                i = int(key[len("_pos_"):])
                key = order[i] if i < len(order) else key
            args[key] = value
        unknown = {k for k in args if k not in allowed}
        if unknown and allowed:
            return False, (f"[!{marker.name}] was given {sorted(unknown)}, "
                           f"which it does not read (it reads {sorted(allowed)})")
        needed = REQUIRED.get(marker.name)
        if needed and not args.get(needed):
            return False, f"[!{marker.name}] has no {needed}, so it cannot act"
        if places is not None:
            for key, value in args.items():
                if ((marker.name, key) in PLACE_ARGS and value not in PLACE_ALIASES
                        and value not in places):
                    return False, (f"[!{marker.name}] names {value!r}, "
                                   "which is not a place in this village")
        if people is not None:
            for key, value in args.items():
                if ((marker.name, key) in TARGET_ARGS and value not in TARGET_ALIASES
                        and value not in people):
                    return False, (f"[!{marker.name}] names {value!r}, "
                                   "who is not anyone in this village")
    return True, ""


def _place_forms(places: dict[str, str]) -> dict[str, str]:
    """Every way a place is written, lowercased, mapped to its id.

    A place is its id with spaces ("east road", "home 8") and its display name
    without the article ("wick & kettle inn", "house 8").
    """
    forms = {}
    for pid, name in places.items():
        forms[pid.replace("_", " ").lower()] = pid
        forms[re.sub(r"^the\s+", "", (name or "").strip(), flags=re.I).lower()] = pid
    forms.pop("", None)
    return forms


def named_as_ids(instruction: Instruction, people: set[str],
                 places: dict[str, str] | None = None) -> Instruction:
    """Write names the way the resolvers look them up.

    The model writes a villager as a name ("Edek") and a place as it is called
    ("house_13" for the place called house 13, whose id is home_13). A lesson
    about something real should not be lost to how it was spelled, so a value
    changes only when the result is someone or somewhere that exists.
    """
    def lower(match: re.Match) -> str:
        name = match.group(2)
        return match.group(1) + (name.lower() if name.lower() in people else name)
    instruction.content = _TARGET.sub(lower, instruction.content)

    if places:
        forms = _place_forms(places)

        def place(match: re.Match) -> str:
            value = match.group(3).strip()
            if value in places or value in PLACE_ALIASES:
                return match.group(0)
            key = re.sub(r"^the\s+", "", value.replace("_", " "), flags=re.I).lower()
            pid = forms.get(key)
            return match.group(1) + match.group(2) + pid if pid else match.group(0)
        instruction.content = _PLACE_VALUE.sub(place, instruction.content)
    return instruction


def where(instruction: Instruction, places: dict[str, str]) -> tuple[set[str], set[str]]:
    """The places a lesson is set in, as (premises, mentions).

    A premise is a place a sentence puts the villager in ("You are at the
    inn"). A mention is any other place the prose names. A place a marker
    sends the villager to or away from is neither, because "keep away from the
    fields" must apply wherever the villager is.
    """
    forms = _place_forms(places)
    destinations = set()
    for marker in parse_actions(instruction.content):
        for key, value in parse_kv_args(marker.args_raw or "").items():
            if (marker.name, key) in PLACE_ARGS:
                destinations.add(value)

    def named(text: str) -> set[str]:
        found, low = set(), text.lower()
        for form, pid in forms.items():
            if re.search(r"(?<!\w)" + re.escape(form) + r"(?!\w)", low):
                found.add(pid)
        return found

    prose = _MARKER.sub(" ", instruction.content)
    premises, mentions = set(), set()
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        places_here = named(sentence)
        if _PREMISE.search(sentence):
            premises |= places_here
        else:
            mentions |= places_here
    return premises, mentions - premises - destinations


def _own(instruction: Instruction, character, stage: str,
         places: dict[str, str] | None = None) -> Instruction:
    """Gate a generated instruction so it belongs to one villager.

    The owner is bear.ownership's hard gate, which strips any owner the model
    wrote and raises rather than let an instruction come out unowned. That is
    the failure this guards: generation returns an empty scope, and one
    child's lesson would become law for the whole village.
    """
    instruction = own(instruction, character.id)
    required = list(instruction.scope.required_tags or [])
    markers = {m.name for m in parse_actions(instruction.content)}
    about_night = any(word in instruction.content.lower() for word in NIGHT_WORDS)
    if about_night:
        # Let it say what it means. The corpus gates night behaviour on the
        # time, and an instruction about going home to sleep belongs there.
        required = [t for t in required if t != "daytime"]
        if "time_night" not in required:
            required.append("time_night")
    elif markers & MOVES and "daytime" not in required:
        # Villagers sleeping at night is the one guarantee the design does not
        # want an embedder deciding, so anything that would move a villager
        # inherits the gate every authored instruction of its kind carries.
        required.append("daytime")
    soft = list(instruction.scope.tags or [])
    if places:
        # A lesson set somewhere applies there. The premise is a hard gate. A
        # place only mentioned is a preference, so it can still apply elsewhere.
        premises, mentions = where(instruction, places)
        required += [f"at_{p}" for p in sorted(premises)]
        soft += [f"at_{p}" for p in sorted(mentions)]
    instruction.scope = ScopeCondition(required_tags=sorted(set(required)),
                                       tags=sorted(set(soft)))
    # Generation returns 10 to 35 of its own accord, which is below every
    # authored band. Keep the ordering it chose among its own instructions, but
    # lift the set into the band where it can actually compete.
    given = getattr(instruction, "priority", None) or MIN_PRIORITY
    instruction.priority = max(MIN_PRIORITY, min(MAX_PRIORITY, given + PRIORITY_LIFT))
    instruction.metadata = {**(instruction.metadata or {}),
                            "layer": "learned", "character": character.id,
                            "learned_at_stage": stage}
    return instruction


async def consolidate(sim, character, became: str) -> list[Instruction]:
    """Turn a villager's experience into instructions it now carries.

    Returns what was added, which is empty when there is no speech model or
    nothing worth consolidating -- both of which are ordinary, not failures.
    """
    speech = sim.speech
    if speech is None or not speech.available:
        logger.debug("no speech model; %s grows up without consolidating", character.id)
        return []

    terms, gaps = formative(sim, character)
    if not terms:
        return []

    offered = offered_markers(sim.config)
    public = sorted(pid for pid in sim.world.places if not pid.startswith("home_"))
    declared = sim.config.declared_lessons
    # With config.declared_lessons each lesson declares which of these facts it
    # answers, how often it acts again and how long it lasts
    # (SPECIFICATION-memory.md section 12). The same facts as the terms, in
    # the same order, by id.
    held: dict[str, object] = {}
    store = sim.diffuser.stores.get(character.id)
    for f in (store.facts if store else []):
        held.setdefault(f.text, f)
    offered_facts = [held[t] for t in terms if t in held]
    from hearthwick.memory import LIFETIMES, RECURRENCES
    config = EvolutionConfig(allowed_markers=[signature(m, public) for m in offered],
                             batch_size=sim.config.consolidate_count,
                             max_evolved_priority=MAX_PRIORITY,
                             id_prefix=f"learned-{character.id}",
                             **({"recurrences": RECURRENCES, "lifetimes": LIFETIMES}
                                if declared else {}))
    evaluation = EvaluationResult(
        should_evolve=True,
        reason=f"{character.name} has become {became} and carries what it lived through",
        coverage_gaps=gaps, recurring_terms=terms, low_similarity_ratio=1.0)

    existing = [i.id for i in sim.corpus.instructions]
    style = [i.content.strip() for i in sim.corpus.instructions
             if parse_actions(i.content)][:6]
    try:
        generated = await generate_with_llm(
            speech.llm_for_generation(), evaluation, existing, config, style_examples=style,
            **({"sources": [(f.id, f.text) for f in offered_facts]} if declared else {}))
    except Exception as exc:  # noqa: BLE001 - growing up must not stop the run
        logger.warning("consolidation failed for %s: %s", character.id, exc)
        return []

    names = {pid: place.name for pid, place in sim.world.places.items()}
    places, people = set(names), set(sim.characters)
    added, refused = [], []
    as_memory: dict[str, dict] = {}       # each lesson's sources (config.fading_lessons)
    for instruction in generated:
        named_as_ids(instruction, people, names)
        ok, why = executable(instruction, places=places, people=people,
                             offered=set(offered))
        if not ok:
            refused.append({"id": instruction.id, "why": why,
                            "content": instruction.content})
            logger.debug("dropping %s: %s", instruction.id, why)
            continue
        if sim.corpus.get(instruction.id) is not None:
            continue
        owned = _own(instruction, character, became, names)
        if sim.config.fading_lessons:
            # A lesson as a memory that fades with the news it came from
            # (SPECIFICATION-warnings.md section 2).
            from hearthwick.memory import as_lesson, lesson_sources
            written_from = [f for f in (store.facts if store else []) if f.text in terms]
            about = (owned.metadata or {}).get("about") if declared else None
            if about is not None:
                # The facts it declared it answers, an empty list for a
                # general rule.
                cited = {f.id: f for f in offered_facts}
                sources = [cited[i] for i in about if i in cited]
            else:
                # Nothing declared: the facts its words are close to.
                sources = lesson_sources(sim, owned.content, written_from)
            lesson = as_lesson(sim.diffuser.memory, owned, character.id, sources, sim.clock.tick)
            as_memory[instruction.id] = {"sources": [f.id for f in sources],
                                         "half_life": lesson.metadata.get("half_life")}
            if declared:
                as_memory[instruction.id].update(
                    about=about, recurs=lesson.metadata.get("recurs"),
                    lasts=lesson.metadata.get("lasts"),
                    declared_recurs=(owned.metadata or {}).get("recurs"),
                    declared_lasts=(owned.metadata or {}).get("lasts"))
            owned = lesson
        sim.corpus.add(owned)
        added.append(instruction)

    if added:
        sim.retriever.build_index()
        sim.log.event(sim.clock.tick, "consolidated", character=character.id,
                      became=became,
                      instructions=[{"id": i.id, "content": i.content,
                                     "scope": list(i.scope.required_tags),
                                     "soft": list(i.scope.tags or []),
                                     "priority": i.priority,
                                     **as_memory.get(i.id, {})} for i in added],
                      # Why this villager now behaves this way, answerable later.
                      from_facts=list(terms), from_gaps=[o.query for o in gaps],
                      refused=refused)
    elif refused:
        # Everything it tried to become was unusable. Worth a record: silence
        # here would look identical to a villager with nothing to consolidate.
        sim.log.event(sim.clock.tick, "consolidation_refused",
                      character=character.id, became=became, refused=refused)
    return added
