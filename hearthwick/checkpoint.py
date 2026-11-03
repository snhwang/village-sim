"""Stopping a run and picking it up again.

A twenty-five-year run is hours of wall clock. Machines reboot, power fails,
and somebody wants the GPU back. A run that cannot be interrupted is a run that
will be lost, so stopping has to be ordinary rather than survivable.

What is written is every piece of state the simulation mutates: the clock, each
villager, what the world remembers, what everybody knows, and the events the
world has scheduled but not yet fired. What is *not* written is anything
derivable -- the map, the corpus as authored, the retrieval index -- because
rebuilding those is cheap and storing them invites them to disagree with the
files they came from.

Fact vectors are recomputed on load rather than stored. They are 2048 floats
each and would dominate the file, and the embedder that produced them is needed
to resume anyway. The model that made them is recorded, and a resume against a
different one is refused: vectors from two models share a space only by
coincidence, and the deduplication threshold would quietly stop meaning
anything.

A resumed run appends to the same log, so a run interrupted six times is one
continuous record rather than seven.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hearthwick.character import Activity, Character, from_profile
from hearthwick.food import Food
from hearthwick.growth import Growth
from hearthwick.knowledge import Fact

FORMAT = 2


def _activity(a: Activity | None) -> dict | None:
    return a.to_dict() if a else None


def _revive_activity(d: dict | None) -> Activity | None:
    return Activity(kind=d["kind"], data=d["data"], ticks_left=d["ticks_left"],
                    instruction_id=d["instruction_id"]) if d else None


def state_of(sim) -> dict:
    """Everything the simulation has changed since it started."""
    world = sim.world_agent.state
    return {
        "format": FORMAT,
        "run_id": sim.log.run_id,
        "tick": sim.clock.tick,
        "seed": sim.config.seed,
        "village": sim.config.village,
        "embedder": (sim.embedder.info() if sim.embedder else {"kind": "bm25"}),
        "characters": [
            {
                "id": c.id, "pos": list(c.pos), "energy": c.energy, "social": c.social,
                # Anyone who joined during the run, a visitor or a child born
                # here, is in no founders file, so it travels with its profile.
                "profile": c.profile() if c.id not in sim.founder_ids else None,
                "alive": c.alive, "age": c.age, "stage": c.stage, "role": c.role,
                "trade": c.trade, "mentor": c.mentor, "tried_for_child": c.tried_for_child,
                # Couples form during a run, and move house.
                "partner": c.partner, "home": c.home,
                "path": [list(t) for t in c.path],
                "activity": _activity(c.activity),
                "queue": [_activity(a) for a in c.queue],
                "conversation_id": None,   # conversations are closed before saving
                "visited_today": sorted(c.visited_today),
                "avoiding": dict(c.avoiding),
                "growth": {"roots": sorted(c.growth.roots), "lived": dict(c.growth.lived),
                           "practice": dict(c.growth.practice),
                           "advanced": list(c.growth.advanced)},
            }
            for c in sim.characters.values()
        ],
        "world": {
            "weather": world.weather, "weather_until": world.weather_until,
            "days_since_rain": world.days_since_rain,
            "last_harvest": world.last_harvest,
            "last_harvest_year": world.last_harvest_year,
            "festival_day": world.festival_day,
            "last_traveler_day": world.last_traveler_day,
            "sick_places": dict(world.sick_places),
            "fought": dict(world.fought),
            "hazards": dict(world.hazards),
            "road_walkers": sorted(world.road_walkers),
            "well_drawers": sorted(world.well_drawers),
            "field_workers": sorted(world.field_workers),
            "yesterday": dict(world.yesterday),
            "fields_recent": list(world.fields_recent),
            "food": world.food.to_dict(),
            # Fields grow when villagers clear new ground, so the map is state.
            "fields_rect": list(sim.world.places["fields"].rect),
            "visitors_here": list(world.visitors_here),
            "last_visitor_day": world.last_visitor_day,
            # Houses the crafters built, and the one going up.
            "built_places": [p.to_dict() for pid, p in sim.world.places.items()
                             if pid not in sim.founding_places],
        },
        "courtship": sim.courtship.to_dict(),
        "building": sim.building.to_dict(),
        "land": sim.land.to_dict(),
        "economy": sim.economy.to_dict(),
        "knowledge": {holder: [f.to_dict() for f in store.facts]
                      for holder, store in sim.diffuser.stores.items()},
        # What each villager remembers sharing with whom. Only with the
        # switch, so a checkpoint without it reads as before.
        **({"told": {holder: {other: sorted(roots) for other, roots in sorted(others.items())}
                     for holder, others in sorted(sim.diffuser.told.items())}}
           if sim.config.told_memory else {}),
        "counters": {"facts": sim.diffuser._count,
                     "conversations": sim.conversations._count,
                     "visitors": sim.visitors.arrived,
                     "births": sim.family.born,
                     "deaths": sim.mortality.died},
        # Markers the world fired that are waiting for their hour to arrive.
        # Dropping these would quietly delete events the world had decided on.
        "pending": [{"tick": t, "kind": a.kind, "data": a.data}
                    for t, a in sim._pending_events],
        "last_day": sim._last_day,
        # The calls the server never answered so far (Simulation.speech_errors),
        # so a resumed run still counts the ones before its checkpoint.
        "speech_errors": sim.speech_errors,
        # The calls, failures and seconds so far, for the same reason.
        "speech_counts": {k: v for k, v in sim.speech_counts.items() if k != "partial"}
                         if "partial" not in sim.speech_counts else None,
        # Instructions villagers authored for themselves by growing up. These
        # exist nowhere on disk, so a resume without them would quietly undo
        # everyone's character.
        "learned": [
            {"id": i.id, "type": str(getattr(i.type, "value", i.type)),
             "priority": i.priority, "content": i.content,
             "required_tags": list(i.scope.required_tags or []),
             "tags": list(i.scope.tags or []), "metadata": dict(i.metadata or {})}
            for i in sim.corpus.instructions
            if (i.metadata or {}).get("layer") == "learned"
        ],
    }


def save(sim, path: Path | None = None) -> Path:
    """Write the run's state beside its logs, atomically.

    The caller must have quiesced the simulation first (Simulation.save does).
    Ending a conversation spawns the diffusion exchange as a task, so a
    snapshot taken without awaiting those loses whatever knowledge was in
    flight -- measured at 159 facts saved against 134 restored.

    Atomically because the likeliest moment to be interrupted is while writing
    the file that exists to survive interruption. The new state lands in a
    temporary file and replaces the old one in a single operation, so a
    checkpoint is either the previous one or the current one and never a
    half-written mixture of both.
    """
    target = Path(path) if path else sim.log.dir / "checkpoint.json"
    payload = state_of(sim)
    sim.log.event(sim.clock.tick, "checkpoint",
                  characters=len(payload["characters"]),
                  facts=sum(len(v) for v in payload["knowledge"].values()))
    # How far the logs had got, so a resume after a hard stop can cut back
    # whatever was logged after this (RunLog.truncate_to).
    payload["log"] = sim.log.sizes()
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    temporary.replace(target)
    return target


def restore(sim, path: Path) -> int:
    """Put a saved state back into a freshly built simulation.

    The simulation must already have been constructed from the same village and
    config; this only replaces what changes during a run. Returns the tick the
    run had reached.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise SystemExit(f"checkpoint format {data.get('format')} is not {FORMAT}")

    was = (data.get("embedder") or {}).get("model_id")
    now = (sim.embedder.info() if sim.embedder else {"kind": "bm25"}).get("model_id")
    if was != now:
        raise SystemExit(
            f"this run used the embedder {was!r} and you are resuming with {now!r}. "
            "Vectors from two models share a space only by coincidence, so the "
            "duplicate threshold would stop meaning anything. Resume with the "
            "same embedder.")

    sim.clock.tick = data["tick"]
    sim._last_day = data["last_day"]
    # A checkpoint from before the count leaves the run unmeasured (None).
    sim.errors_before = data.get("speech_errors")
    sim.counts_before = data.get("speech_counts")

    # Everyone who joined since the run began comes back, and the index is
    # rebuilt once at the end. Rebuilt after each, the live village took six
    # minutes to restore 132 villagers through the embedding service.
    rebuild = False
    for saved in data["characters"]:
        c: Character | None = sim.characters.get(saved["id"])
        if c is None and saved.get("profile"):
            c = from_profile(saved["profile"])
            sim.join(c, index=False)
            rebuild = True
        if c is None:
            continue
        c.pos = tuple(saved["pos"])
        c.energy, c.social, c.alive = saved["energy"], saved["social"], saved["alive"]
        c.age, c.stage, c.role = saved["age"], saved["stage"], saved["role"]
        c.trade = saved.get("trade", c.trade)
        c.tried_for_child = saved.get("tried_for_child")
        c.mentor = saved.get("mentor", c.mentor)
        c.partner = saved.get("partner", c.partner)
        c.home = saved.get("home", c.home)
        c.path = [tuple(t) for t in saved["path"]]
        c.activity = _revive_activity(saved["activity"])
        c.queue.clear()
        for entry in saved["queue"]:
            revived = _revive_activity(entry)
            if revived:
                c.queue.append(revived)
        c.conversation_id = None
        c.visited_today = set(saved["visited_today"])
        c.avoiding = dict(saved["avoiding"])
        g = saved["growth"]
        c.growth = Growth(roots=set(g["roots"]), lived=dict(g["lived"]),
                          practice=dict(g["practice"]), advanced=list(g["advanced"]))

    world = sim.world_agent.state
    w = data["world"]
    world.weather, world.weather_until = w["weather"], w["weather_until"]
    world.days_since_rain = w["days_since_rain"]
    world.last_harvest, world.last_harvest_year = w["last_harvest"], w["last_harvest_year"]
    world.festival_day, world.last_traveler_day = w["festival_day"], w["last_traveler_day"]
    world.sick_places = dict(w["sick_places"])
    world.fought = dict(w.get("fought") or {})
    world.hazards = dict(w["hazards"])
    world.road_walkers = set(w["road_walkers"])
    world.well_drawers = set(w["well_drawers"])
    world.field_workers = set(w["field_workers"])
    world.yesterday = dict(w["yesterday"])
    world.fields_recent = list(w.get("fields_recent", [world.yesterday.get("fields", 0)]))
    if "food" in w:
        world.food = Food.from_dict(w["food"])
    if "fields_rect" in w:
        sim.world.set_rect("fields", w["fields_rect"])
    world.visitors_here = list(w.get("visitors_here", []))
    world.last_visitor_day = w.get("last_visitor_day")
    # The land first, since what was built may stand on ground it added.
    sim.land.load(data.get("land", {}))
    from hearthwick.world import Place
    for p in w.get("built_places", []):
        sim.world.add_place(Place.from_dict(p))
    sim.courtship.load(data.get("courtship", {}))
    sim.economy.load(data.get("economy", {}))
    sim.building.load(data.get("building", {}))

    # Facts come back without their vectors, which are recomputed here so the
    # store can go on recognising news it already holds, each distinct text
    # once and in batches.
    vectors = sim.diffuser.vectors([entry["text"] for facts in data["knowledge"].values()
                                    for entry in facts])
    # With memories as BEAR items, every restored fact is indexed in one build
    # at the end rather than one append each (config.bear_memory).
    memory = sim.diffuser.memory
    if memory is not None:
        memory.begin_load()
    for holder, facts in data["knowledge"].items():
        store = sim.diffuser.store_for(holder)
        store.clear()
        for entry in facts:
            fact = Fact(id=entry["id"], holder=entry["holder"], text=entry["text"],
                        kind=entry["kind"], place=entry["place"], root=entry["root"],
                        parent=entry["parent"], teller=entry["teller"],
                        hop=entry["hop"], tick=entry["tick"],
                        reinforced=entry["reinforced"],
                        tags=tuple(entry.get("tags", ())),
                        from_afar=entry.get("from_afar", False),
                        refreshed=entry.get("refreshed"))
            fact.vector = vectors.get(fact.text)
            store.add(fact)
    if memory is not None:
        memory.end_load()
        # What had left the live index leaves it again, by the same rule
        # (config.forget_the_dead, config.forget_faded).
        # What ended or never came is marked down again (config.news_ends,
        # config.false_alarms), before the trim, which drops what was marked.
        if sim.config.news_ends or sim.config.false_alarms:
            memory.recompute(sim.clock.tick)
        if sim.config.forget_the_dead or sim.config.forget_faded:
            memory.prune(sim.clock.tick)

    sim.diffuser.told ={holder: {other: set(roots) for other, roots in others.items()}
                         for holder, others in data.get("told", {}).items()}
    sim.diffuser._count = data["counters"]["facts"]
    sim.conversations._count = data["counters"]["conversations"]
    sim.visitors.arrived = data["counters"].get("visitors", 0)
    sim.family.born = data["counters"].get("births", 0)
    sim.mortality.died = data["counters"].get("deaths", 0)

    from bear import MarkerAction
    sim._pending_events = [
        (entry["tick"], MarkerAction(entry["kind"], entry["data"], None))
        for entry in data["pending"]
    ]
    # Put back what villagers learned. Rebuilding the index once at the end,
    # with everyone who joined, is cheaper than once per instruction, and the
    # corpus is not consulted in between.
    learned = data.get("learned") or []
    if learned:
        from bear import Instruction, InstructionType, ScopeCondition
        for entry in learned:
            if sim.corpus.get(entry["id"]) is not None:
                continue
            sim.corpus.add(Instruction(
                id=entry["id"],
                type=InstructionType(entry["type"]) if entry["type"] in
                    {t.value for t in InstructionType} else InstructionType.DIRECTIVE,
                priority=entry["priority"], content=entry["content"],
                scope=ScopeCondition(required_tags=entry["required_tags"],
                                     tags=entry["tags"]),
                metadata=entry["metadata"]))
        rebuild = True
    if rebuild:
        # A lesson at rest comes back with BEAR's resting mark in its
        # metadata (config.lessons_satisfied).
        sim.retriever.build_index()

    # Only into the run's own log: a checkpoint restored into a fresh run
    # must not cut that run's files to another run's lengths.
    if data.get("log") and Path(path).resolve().parent == sim.log.dir.resolve():
        sim.log.truncate_to(data["log"])
    sim.log.event(sim.clock.tick, "resumed",
                  facts=sum(len(v) for v in data["knowledge"].values()),
                  learned=len(learned))
    return data["tick"]


def find(runs_dir: Path, run_id: str) -> Path:
    path = Path(runs_dir) / run_id / "checkpoint.json"
    if not path.exists():
        raise SystemExit(f"no checkpoint in {path.parent} -- that run cannot be resumed")
    return path
