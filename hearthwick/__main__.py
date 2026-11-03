"""Command line.

    python -m hearthwick serve                 # live village + map viewer
    python -m hearthwick serve --no-llm        # no speech model
    python -m hearthwick run --days 2          # headless run, lockstep
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import replace

from hearthwick.config import NEW_IN_TALK, SimConfig


# What the case study describes: every mechanic added since switched off.
# Exact reproduction of its results uses the tags paper-runs and
# paper-development, which pin the builds that made them.
PROFILES = {"paper": {"mortality": False, "land": False,
                       "materials": False, "money": False, "fertility": False,
                       "blight_fighting": False, "richer_fields": False,
                       "grown_personas": False, "chat_turns": False,
                       "told_memory": False, "bear_memory": False, "quick_warnings": False,
                       "fading_lessons": False, "short_warnings": False,
                       "lasting_lessons": False, "teachers_by_pupils": False,
                       "decide_again": False, "elders_in_fields": False,
                       "work_in_rain": False, "forget_the_dead": False,
                       "forget_faded": False, "novel_telling": False,
                       "news_ends": False, "false_alarms": False,
                       "routine_fades": False, "talk_once_a_day": False,
                       "lessons_satisfied": False, "declared_lessons": False,
                       "fresh_warnings": False, "far_danger_dated": False,
                       **{name: False for name in NEW_IN_TALK}}}

# The village as the paper's runs made it (2026-10-17): the seventh long
# run's rules, which grew a village from 30 to 87 in 17 years without its
# granary running dry after year 12, with ended and unfounded news marked
# down. Every switch is set here, so a run with it does not depend on the
# command line's defaults. Settled with Scott on 2026-10-17 as the set the
# paper describes. What it had off (creation, leisure, the memory gene and
# the rest of config.LEFT_OUT) is not in this edition.
PROFILES["illustrative"] = {
    "days_per_year": 28, "pupils_per_teacher": 15,
    # on
    "temperament": True, "growth": True, "consolidate": True, "mortality": True,
    "land": True, "materials": True, "money": True, "fertility": True,
    "blight_fighting": True, "richer_fields": True, "grown_personas": True,
    "chat_turns": True, "afar_news": True, "news_fades": True, "told_memory": True,
    "quick_warnings": True, "bear_memory": True, "fading_lessons": True,
    "lasting_lessons": True, "short_warnings": True, "teachers_by_pupils": True,
    "elders_in_fields": True, "work_in_rain": True, "decide_again": True,
    "forget_the_dead": True, "forget_faded": True, "novel_telling": True,
    "news_ends": True, "false_alarms": True, "routine_fades": True,
    "talk_once_a_day": True, "lessons_satisfied": True, "declared_lessons": True,
    "fresh_warnings": True, "far_danger_dated": True, "memory_by_relevance": True,
    "remember_conversations": True,
    # off
    "restore_below_threshold": False,
}

# Mechanics a resumed run can take up with --with. A run resumes as it was
# recorded, so one added since stays off unless it is asked for, and once
# taken up it is part of the run's record.
ADDABLE = ("mortality", "land", "materials", "money", "fertility",
           "blight_fighting", "richer_fields", "grown_personas", "chat_turns",
           "told_memory", "bear_memory", "quick_warnings", "fading_lessons",
           "short_warnings", "lasting_lessons", "teachers_by_pupils", "decide_again",
           "elders_in_fields", "work_in_rain", "forget_the_dead", "forget_faded",
           "novel_telling", "news_ends", "false_alarms", "routine_fades",
           "talk_once_a_day", "lessons_satisfied", "declared_lessons", "fresh_warnings",
           "far_danger_dated", *NEW_IN_TALK)


def _config(args: argparse.Namespace, lockstep: bool) -> SimConfig:
    config = _config_from(args, lockstep)
    profile = PROFILES.get(getattr(args, "profile", None) or "", {})
    return replace(config, **profile) if profile else config


def _llm_key(args: argparse.Namespace) -> str | None:
    """The model server's key: named by --llm-key-env and read from the
    environment or .env, or given directly with --llm-api-key. A run records
    only that a key was set (SimConfig.to_dict)."""
    name = getattr(args, "llm_key_env", None)
    if not name:
        return args.llm_api_key
    from hearthwick.llm import env_value
    key = env_value(name)
    if not key:
        raise SystemExit(f"--llm-key-env {name}: no such variable in the environment or .env")
    return key


def _config_from(args: argparse.Namespace, lockstep: bool) -> SimConfig:
    return SimConfig(
        seed=args.seed,
        llm_base_url=None if args.no_llm else args.llm_url,
        llm_model=args.model,
        llm_provider=args.llm_provider,
        llm_concurrency=args.llm_concurrency,
        llm_api_key=_llm_key(args),
        village=args.village,
        days_per_year=getattr(args, "days_per_year", None) or SimConfig.days_per_year,
        growth=not args.no_growth,
        consolidate=not args.no_consolidate,
        mortality=not args.no_mortality,
        land=not args.no_land_growth,
        materials=not args.no_materials,
        money=not args.no_money,
        fertility=not args.narrow_fertility,
        blight_fighting=not args.no_blight_fighting,
        richer_fields=not args.plain_fields,
        grown_personas=not args.no_grown_personas,
        chat_turns=not args.no_chat_turns,
        afar_news=not args.no_afar_news,
        news_fades=not args.no_news_fades,
        told_memory=args.told_memory or args.novel_telling or args.fresh_warnings,
        bear_memory=(args.bear_memory or args.fading_lessons
                     or args.short_warnings or args.lasting_lessons
                     or args.forget_the_dead or args.forget_faded
                     or args.news_ends or args.false_alarms or args.routine_fades
                     or args.fresh_warnings or args.far_danger_dated),
        short_warnings=args.short_warnings or args.far_danger_dated,
        quick_warnings=args.quick_warnings or args.fresh_warnings,
        fresh_warnings=args.fresh_warnings,
        far_danger_dated=args.far_danger_dated,
        fading_lessons=args.fading_lessons or args.lasting_lessons,
        lasting_lessons=args.lasting_lessons,
        teachers_by_pupils=args.teachers_by_pupils,
        pupils_per_teacher=args.pupils_per_teacher,
        decide_again=args.decide_again,
        elders_in_fields=args.elders_in_fields,
        work_in_rain=args.work_in_rain,
        forget_the_dead=args.forget_the_dead,
        forget_faded=args.forget_faded,
        novel_telling=args.novel_telling,
        news_ends=args.news_ends,
        false_alarms=args.false_alarms,
        routine_fades=args.routine_fades,
        talk_once_a_day=args.talk_once_a_day,
        lessons_satisfied=args.lessons_satisfied,
        declared_lessons=args.declared_lessons,
        memory_by_relevance=not args.memory_recency,
        gating=args.gating,
        temperament=not args.no_temperament,
        choice_temperature=args.choice_temperature,
        embedder=args.embedder,
        embed_url=args.embed_url,
        embed_model=args.embed_model,
        embedder_strict=args.embedder != "bm25",
        retrieval_threshold=args.threshold,
        lockstep=lockstep,
    )


def _saved(config: SimConfig, run_id: str,
           turn_on: list[str] | None = None) -> tuple[SimConfig, dict]:
    """A run's own configuration and plan, from its record.

    A resumed run is the run it was: its village, growth and every other
    setting come from its own record, so a reboot can be answered with the run
    id alone. Only paths and service connections, which belong to the
    machine, come from this command line. ``turn_on`` names mechanics added
    since that this run is to take up (``--with``).
    """
    record = config.runs_dir / run_id / "meta.json"
    if not record.exists():
        raise SystemExit(f"no run {run_id} in {config.runs_dir}")
    meta = json.loads(record.read_text(encoding="utf-8"))
    saved = SimConfig.from_saved(meta.get("config", {}), config)
    if turn_on:
        saved = replace(saved, **{m: True for m in turn_on})
    return saved, meta.get("plan", {})


async def _speech(config: SimConfig):
    from hearthwick.llm import SpeechModel

    if not config.llm_base_url:
        return None
    speech = SpeechModel(config.llm_base_url, config.llm_model, config.llm_concurrency,
                         config.llm_max_tokens, config.llm_temperature,
                         api_key=config.llm_api_key, provider=config.llm_provider,
                         top_p=config.llm_top_p, top_k=config.llm_top_k)
    speech.wait_seconds = config.server_wait_minutes * 60
    if not await speech.connect():
        logging.warning("Continuing without speech. Conversations will have no lines.")
    return speech


async def _run_to(sim, target: int, every: int, save_at_end: bool) -> None:
    """Step ``sim`` to ``target``, checkpointing every ``every`` ticks, and
    close it. A run that ends, or is stopped between ticks, is saved where it
    is when ``save_at_end`` or a stop asks for it. A run that fails is not: the
    tick it failed in is half done, and saving it would put that half-done
    tick over the last checkpoint taken between ticks, so a resume would repeat
    part of a tick. The last clean checkpoint stays, and a resume starts from
    it."""
    failed = False
    try:
        await sim.run(0, checkpoint_every=every, until_tick=target)
    except BaseException:
        failed = True
        logging.error("the run failed in tick %d; its checkpoint is left as it was, "
                      "taken between ticks", sim.clock.tick)
        raise
    finally:
        if not failed and (save_at_end or sim.stopping):
            await sim.save()
        elif failed:
            # Settled without saving, so nothing in flight writes to the log
            # after it closes. What failed may fail again here.
            try:
                await sim.settle()
            except Exception:  # noqa: BLE001 - the first failure is the one to report
                logging.exception("could not settle the village after the failure")
        sim.close()


async def _run(args: argparse.Namespace) -> None:
    import signal

    from hearthwick import checkpoint
    from hearthwick.sim import Simulation

    config = _config(args, lockstep=True)
    days, every_days = args.days, args.checkpoint_every
    if args.resume:
        config, plan = _saved(config, args.resume, args.turn_on)
        days = days if days is not None else plan.get("days")
        every_days = every_days if every_days is not None else plan.get("checkpoint_every")
        if days is None:
            raise SystemExit(f"{args.resume} did not record how long it runs; add --days")
    days = 1.0 if days is None else days
    every_days = every_days or 0
    speech = await _speech(config)
    sim = Simulation(config, speech)
    if not args.resume:
        sim.log.meta["plan"] = {"days": days, "checkpoint_every": every_days}
        sim.log.write_meta()

    target = int(days * sim.clock.ticks_per_day)
    if args.resume:
        # Continue in the run that was interrupted, so the log is one record
        # rather than one per interruption.
        path = checkpoint.find(config.runs_dir, args.resume)
        sim.log.adopt(config.runs_dir / args.resume, args.turn_on)
        done = sim.resume_from(path)
        print(f"resumed {args.resume} at tick {done} of {target}")

    # Ctrl-C, a shutdown, or wanting the machine back: finish the tick in
    # progress, write the state, and exit. Losing hours because a run could
    # only be killed is the failure this exists to prevent.
    def stop(signum, frame):
        print("stopping after this tick; the run will be resumable", flush=True)
        sim.request_stop()

    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stop)
            except (ValueError, OSError):
                pass        # not the main thread, or not supported here

    every = int(every_days * sim.clock.ticks_per_day) if every_days else 0
    started = time.perf_counter()
    await _run_to(sim, target, every, save_at_end=bool(every or args.resume))
    elapsed = time.perf_counter() - started
    reached = sim.clock.tick
    how = "stopped at" if reached < target else "finished"
    print(f"run {sim.log.run_id}: {how} tick {reached} of {target} "
          f"in {elapsed:.1f}s -> {sim.log.dir}")
    if reached < target:
        print(f"  resume with: python -m hearthwick run --resume {sim.log.run_id}")


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from hearthwick.server import create_app

    config = _config(args, lockstep=args.lockstep)
    every = args.checkpoint_every
    if args.resume:
        config, plan = _saved(config, args.resume, args.turn_on)
        every = every if every is not None else plan.get("checkpoint_every")
    app = create_app(config, live=not args.no_live, speed=args.speed, make_speech=_speech,
                     idle_speed=args.idle_speed, checkpoint_every=every or 0.0,
                     resume=args.resume, turn_on=args.turn_on)
    print(f"Hearthwick viewer: http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def _view(args: argparse.Namespace) -> None:
    """Watch runs without running one. The viewer only reads their log files."""
    import uvicorn

    from hearthwick.server import create_app

    app = create_app(SimConfig(), live=False, speed=2.0, make_speech=_speech)
    print(f"Hearthwick 3D viewer: http://localhost:{args.port}/3d  "
          f"(2D map at http://localhost:{args.port}/)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hearthwick")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--no-llm", action="store_true", help="run without a speech model")
        p.add_argument("--llm-url", default="http://localhost:8355/v1",
                       help="an OpenAI-compatible server: your own, Ollama, LM Studio, "
                            "or a cloud provider's endpoint")
        p.add_argument("--llm-provider", choices=("anthropic", "openai", "gemini"),
                       default=None,
                       help="a hosted model instead of --llm-url, named by --model, with "
                            "its key in ANTHROPIC_API_KEY, OPENAI_API_KEY or GOOGLE_API_KEY "
                            "(the environment or .env)")
        p.add_argument("--model", default=None, help="model name (default: first one served)")
        p.add_argument("--llm-concurrency", type=int, default=4)
        p.add_argument("--llm-api-key", default=None,
                       help="only if the model server was started with one. "
                            "Prefer --llm-key-env, which keeps the key off the command line")
        p.add_argument("--llm-key-env", default=None, metavar="NAME",
                       help="read the model server's key from this variable, in the "
                            "environment or the repository's .env (such as "
                            "LLM_API_KEY). Pass it again on a resume")
        p.add_argument("--days-per-year", type=int, default=None, metavar="N",
                       help="in-game days in a year, which sets ageing, lifespans and the "
                            "seasons (default 8, the paper's). A resumed run keeps the "
                            "length it was recorded with")
        p.add_argument("--village", default=None,
                       help="a generated village in data/villages/ (see "
                            "experiments/make_village.py)")
        p.add_argument("--no-growth", action="store_true",
                       help="nobody advances a life stage. By default villagers do, "
                            "when they meet every requirement: children graduate from "
                            "school and choose a trade, apprentices qualify, and each "
                            "consolidates what it lived through into instructions")
        p.add_argument("--growth", action="store_true",
                       help="accepted for older commands. Growth is on by default")
        p.add_argument("--no-mortality", action="store_true",
                       help="nobody dies of old age, as in runs before it existed")
        p.add_argument("--no-land-growth", action="store_true",
                       help="the map keeps its size when the village fills it, as in "
                            "runs before the land grew")
        p.add_argument("--no-materials", action="store_true",
                       help="everything is built of timber alone, as in runs before "
                            "materials existed")
        p.add_argument("--no-money", action="store_true",
                       help="no coins or market, as in runs before money existed")
        p.add_argument("--narrow-fertility", action="store_true",
                       help="children only between 11 and 20, as in runs before the "
                            "window widened")
        p.add_argument("--no-blight-fighting", action="store_true",
                       help="nobody can fight a blight: it runs its course")
        p.add_argument("--plain-fields", action="store_true",
                       help="the fields yield what they did before richer fields")
        p.add_argument("--no-grown-personas", action="store_true",
                       help="a villager born here keeps the persona it was born with")
        p.add_argument("--no-afar-news", action="store_true",
                       help="tales and travellers' news held as local, as before")
        p.add_argument("--no-news-fades", action="store_true",
                       help="hazards drive behaviour however old they are")
        p.add_argument("--told-memory", action="store_true",
                       help="villagers remember which news they have shared with whom, and "
                            "pass on only what the listener has not had from them "
                            "(SPECIFICATION-warnings.md section 3)")
        p.add_argument("--quick-warnings", action="store_true",
                       help="a warning is a word to someone within reach, passed on in one "
                            "tick, with no walk and no conversation, and nobody stops "
                            "working (SPECIFICATION-warnings.md section 8)")
        p.add_argument("--short-warnings", action="store_true",
                       help="what news makes a villager do fades in days, not years, and "
                            "far-off news warns only of a danger that can come here "
                            "(SPECIFICATION-warnings.md section 10). Turns on --bear-memory")
        p.add_argument("--fading-lessons", action="store_true",
                       help="a lesson a villager writes is a BEAR item that fades with the "
                            "news it came from, and drops out of decisions below half its "
                            "strength (SPECIFICATION-warnings.md section 2). Turns on "
                            "--bear-memory with it")
        p.add_argument("--lasting-lessons", action="store_true",
                       help="a lesson fades over the years its news once took, one for a "
                            "rumor or a sickness and two for a danger, however short the "
                            "news itself, unless its news recurs (SPECIFICATION-memory.md). "
                            "Turns on --fading-lessons and --bear-memory with it")
        p.add_argument("--teachers-by-pupils", action="store_true",
                       help="an elder goes to teach only while the school has fewer "
                            "teachers than its children need, one for each "
                            "--pupils-per-teacher, and otherwise does something else "
                            "(SPECIFICATION-warnings.md section 11)")
        p.add_argument("--pupils-per-teacher", type=int, default=15,
                       help="children one teacher can take, with --teachers-by-pupils")
        p.add_argument("--forget-the-dead", action="store_true",
                       help="the dead's own memories leave the live index, since nobody "
                            "asks them anything (SPECIFICATION-memory.md section 7). "
                            "Turns on --bear-memory")
        p.add_argument("--forget-faded", action="store_true",
                       help="a memory faded below a twentieth of its strength leaves the "
                            "live index, and comes back if it is lived again "
                            "(SPECIFICATION-memory.md section 7). Turns on --bear-memory")
        p.add_argument("--novel-telling", action="store_true",
                       help="tell someone of news a topic names only when they have not "
                            "had it from the teller (SPECIFICATION-memory.md section 8). "
                            "Turns on --told-memory")
        p.add_argument("--fresh-warnings", action="store_true",
                       help="a warning is about the fresh news that unlocked it, passes "
                            "on only that, and goes only to someone the warner has not "
                            "told it (SPECIFICATION-warnings.md section 13). Turns on "
                            "--told-memory, --quick-warnings and --bear-memory")
        p.add_argument("--far-danger-dated", action="store_true",
                       help="word of danger abroad fades from when it reached the "
                            "village, not from when each villager heard it, and is a "
                            "false alarm unless the danger came within the week "
                            "(SPECIFICATION-warnings.md section 14). Turns on "
                            "--short-warnings and --bear-memory")
        p.add_argument("--news-ends", action="store_true",
                       help="a danger that wears off or is cut out is news, and marks "
                            "down what was known of it (SPECIFICATION-memory.md section "
                            "9). Turns on --bear-memory")
        p.add_argument("--false-alarms", action="store_true",
                       help="word of far-off danger that has not come within a week is "
                            "marked down (SPECIFICATION-memory.md section 9). Turns on "
                            "--bear-memory, and needs --short-warnings")
        p.add_argument("--routine-fades", action="store_true",
                       help="memories of talk and of what one did fade over a year, "
                            "routine news over two (SPECIFICATION-memory.md section "
                            "10). Turns on --bear-memory")
        p.add_argument("--talk-once-a-day", action="store_true",
                       help="the same two villagers talk about the same thing at most "
                            "once a day (SPECIFICATION-memory.md section 10)")
        p.add_argument("--lessons-satisfied", action="store_true",
                       help="a one-shot lesson rests once carried out, until its kind of "
                            "event recurs where its news came from, or the next day if "
                            "it rests on no news (SPECIFICATION-memory.md section 11). "
                            "Needs --fading-lessons")
        p.add_argument("--declared-lessons", action="store_true",
                       help="a lesson declares as it is written which news it answers, "
                            "how often it acts again and how long it lasts "
                            "(SPECIFICATION-memory.md section 12). Needs "
                            "--lessons-satisfied")
        p.add_argument("--elders-in-fields", action="store_true",
                       help="elders help tend and harvest when the crop needs it, in "
                            "lighter spells than adults (SPECIFICATION-warnings.md "
                            "section 12)")
        p.add_argument("--work-in-rain", action="store_true",
                       help="only the easygoing stop work for rain, and a storm still "
                            "sends everyone in (SPECIFICATION-warnings.md section 12)")
        p.add_argument("--decide-again", action="store_true",
                       help="a villager whose action ends partway through a tick takes "
                            "up its next one in that tick, rather than standing idle "
                            "until the next (SPECIFICATION-warnings.md section 11)")
        p.add_argument("--bear-memory", action="store_true",
                       help="villagers' memories are BEAR items, faded by kind, and their "
                            "knowledge tags and recall are asked of BEAR "
                            "(SPECIFICATION-memory.md). Needs BEAR v0.3.0 or later")
        p.add_argument("--no-chat-turns", action="store_true",
                       help="a conversation reaches the model as a transcript in one message")
        p.add_argument("--with", dest="turn_on", action="append", choices=ADDABLE,
                       default=None, metavar="MECHANIC",
                       help="with --resume: take up a mechanic added since the run "
                            f"was recorded ({', '.join(ADDABLE)}). Repeatable")
        p.add_argument("--profile", choices=sorted(PROFILES), default=None,
                       help="paper: every mechanic added since the case study off")
        p.add_argument("--no-consolidate", action="store_true",
                       help="grow up without authoring instructions (needs no model)")
        p.add_argument("--memory-recency", action="store_true",
                       help="recall a villager's last memories instead of the ones "
                            "that bear on its situation (the control arm)")
        p.add_argument("--gating", choices=("soft", "hard"), default="soft",
                       help="hard re-gates every situational tag (ablation)")
        p.add_argument("--no-temperament", action="store_true",
                       help="strip temperament instructions (individuality control)")
        p.add_argument("--choice-temperature", type=float, default=0.02,
                       help="0 always takes the best-scoring candidate")
        p.add_argument("--embedder", choices=("service", "bear", "bm25"), default="service",
                       help="the embedding service (default, serving/), bear for BEAR's own "
                            "embedder with --embed-model, or bm25 for development without "
                            "one (degrades behavior). A run stops if the one chosen does "
                            "not answer")
        p.add_argument("--embed-url", default="http://localhost:8360")
        p.add_argument("--embed-model", default="",
                       help="with --embedder bear: openai:<name> for OpenAI's API (or a "
                            "server named by OPENAI_BASE_URL), or a local "
                            "sentence-transformers model such as BAAI/bge-base-en-v1.5")
        p.add_argument("--threshold", type=float, default=0.15,
                       help="minimum similarity; 0.15 suits the service, BM25 needs 0")

    p_run = sub.add_parser("run", help="headless run")
    common(p_run)
    p_run.add_argument("--days", type=float, default=None,
                       help="in-game days to run (default 1, or what a resumed run recorded)")
    p_run.add_argument("--checkpoint-every", type=float, default=None,
                       help="save state every N in-game days, so the run "
                            "survives a reboot or can give the machine back "
                            "(a resumed run keeps the interval it recorded)")
    p_run.add_argument("--resume", default=None, metavar="RUN_ID",
                       help="continue an interrupted run, appending to its log. "
                            "Its settings come from its own record, so the id "
                            "is all it needs")

    p_serve = sub.add_parser("serve", help="live village and map viewer")
    common(p_serve)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8010)
    p_serve.add_argument("--speed", type=float, default=2.0,
                         help="ticks per second while anyone watches")
    p_serve.add_argument("--idle-speed", type=float, default=0.0,
                         help="ticks per second while nobody watches (0: as fast as "
                              "it can). A village left running for good wants one, "
                              "to leave the machine and the model to other work")
    p_serve.add_argument("--checkpoint-every", type=float, default=None,
                         help="save the village every N in-game days, and when "
                              "stopped, so --resume can pick it up again")
    p_serve.add_argument("--resume", default=None, metavar="RUN_ID",
                         help="carry on a village that was saved, in its own log")
    p_serve.add_argument("--lockstep", action="store_true", help="wait for speech each tick")
    p_serve.add_argument("--no-live", action="store_true", help="replay viewer only")

    p_view = sub.add_parser("view", help="watch runs in the browser, live or replayed, "
                                         "without running a village")
    p_view.add_argument("--host", default="127.0.0.1")
    p_view.add_argument("--port", type=int, default=8010)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.cmd == "run":
        asyncio.run(_run(args))
    elif args.cmd == "view":
        _view(args)
    else:
        _serve(args)


if __name__ == "__main__":
    main()
