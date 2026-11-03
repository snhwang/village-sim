"""Time in the day (SPECIFICATION-warnings.md section 11): elders teach only
while the school has fewer teachers than its children need
(config.teachers_by_pupils), and a villager whose action ends partway through
a tick takes up its next one in that tick (config.decide_again)."""

import asyncio
import collections
import json

import pytest

from hearthwick.__main__ import ADDABLE, PROFILES
from hearthwick.character import Activity
from hearthwick.config import SimConfig
from hearthwick.corpus import PUPILS_WAITING
from hearthwick.sim import Simulation


def make_sim(tmp_path, **switches):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None, runs_dir=tmp_path,
                                embedder="bm25", retrieval_threshold=0.0, **switches))


def teach(c):
    c.activity = Activity(kind="work", data={"place": "schoolyard", "ticks": 12})


def test_off_unless_asked_for():
    config = SimConfig()
    assert config.teachers_by_pupils is False and config.decide_again is False
    assert config.pupils_per_teacher == 15
    for name in ("teachers_by_pupils", "decide_again"):
        assert PROFILES["paper"][name] is False
        assert name in ADDABLE


def test_teaching_waits_for_pupils(tmp_path):
    sim = make_sim(tmp_path, teachers_by_pupils=True)
    try:
        inst = sim.corpus.get("elder-teach")
        assert PUPILS_WAITING in inst.scope.required_tags
        living = [c for c in sim.characters.values() if c.alive and not c.visitor]
        children = [c for c in living if c.stage == "child"]
        elders = [c for c in living if c.stage == "elder"]
        assert children and elders
        assert sim.brain.pupils_waiting(sim.characters)          # nobody teaching yet
        teach(elders[0])
        assert not sim.brain.pupils_waiting(sim.characters)      # one is enough
        sim.config.pupils_per_teacher = 1                         # one each
        assert sim.brain.pupils_waiting(sim.characters) == (len(children) > 1)
        for c in children:
            c.stage = "adult"
        assert not sim.brain.pupils_waiting(sim.characters)      # no pupils, no teacher
    finally:
        sim.close()


def test_the_tag_is_an_elders_by_day(tmp_path):
    sim = make_sim(tmp_path, teachers_by_pupils=True)
    try:
        elder = next(c for c in sim.characters.values() if c.stage == "elder")
        adult = next(c for c in sim.characters.values() if c.stage == "adult")
        sim.clock.tick = 9 * 6                                    # 9 in the morning
        assert PUPILS_WAITING in sim.brain.context_tags(elder, sim.characters)
        assert PUPILS_WAITING not in sim.brain.context_tags(adult, sim.characters)
    finally:
        sim.close()


def test_without_the_switch_teaching_is_as_before(tmp_path):
    sim = make_sim(tmp_path)
    try:
        assert PUPILS_WAITING not in sim.corpus.get("elder-teach").scope.required_tags
        elder = next(c for c in sim.characters.values() if c.stage == "elder")
        sim.clock.tick = 9 * 6
        assert PUPILS_WAITING not in sim.brain.context_tags(elder, sim.characters)
    finally:
        sim.close()


def run(sim, ticks):
    async def go():
        for _ in range(ticks):
            await sim.step()
            await sim.conversations.wait_generating()
    asyncio.run(go())


def day_use(sim):
    """(decisions made a second time in a tick, grown villagers' idle frames
    from 6:00 to noon, all such frames)."""
    sim.log.flush()
    per_tick = collections.Counter()
    with open(sim.log.dir / "events.jsonl", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e["type"] == "decision":
                per_tick[(e["t"], e["character"])] += 1
    idle = total = 0
    with open(sim.log.dir / "frames.jsonl", encoding="utf-8") as f:
        for line in f:
            frame = json.loads(line)
            if not 6 <= frame["clock"]["hour"] < 12:
                continue
            for c in frame["c"]:
                if c[4] in ("adult", "apprentice", "elder"):
                    total += 1
                    idle += c[3] == "idle"
    return sum(1 for n in per_tick.values() if n > 1), idle, total


def test_a_villager_takes_up_its_next_action_in_the_same_tick(tmp_path):
    use = {}
    for on in (False, True):
        sim = make_sim(tmp_path / str(on), decide_again=on)
        try:
            run(sim, 72)
            use[on] = day_use(sim)
        finally:
            sim.close()
    (twice_off, idle_off, total_off), (twice_on, idle_on, total_on) = use[False], use[True]
    assert twice_off == 0                         # one decision a tick, as before
    assert twice_on > 0
    assert idle_on / total_on < idle_off / total_off / 2


def test_the_field_switches_are_off_unless_asked_for():
    config = SimConfig()
    assert config.elders_in_fields is False and config.work_in_rain is False
    for name in ("elders_in_fields", "work_in_rain"):
        assert PROFILES["paper"][name] is False
        assert name in ADDABLE


ELDER_WORK = ("elder-harvest-hands", "elder-harvest-hungry", "elder-help-tend")


def test_elders_get_food_work_only_with_the_switch(tmp_path):
    sim = make_sim(tmp_path / "on", elders_in_fields=True)
    try:
        for name in ELDER_WORK:
            inst = sim.corpus.get(name)
            assert inst is not None and "stage_elder" in inst.scope.required_tags
            assert "[!work(site=fields" in inst.content
    finally:
        sim.close()
    sim = make_sim(tmp_path / "off")
    try:
        assert all(sim.corpus.get(name) is None for name in ELDER_WORK)
    finally:
        sim.close()


def test_only_the_easygoing_stop_for_rain(tmp_path):
    sim = make_sim(tmp_path / "on", work_in_rain=True)
    try:
        rain = sim.corpus.get("weather-wait-out-rain")
        assert "temp_easygoing" in rain.scope.required_tags
        assert "temp_easygoing" not in rain.scope.tags
        storm = sim.corpus.get("weather-shelter-from-storm")
        assert storm.scope.required_tags == ["daytime", "weather_storm"]   # everyone, as before
    finally:
        sim.close()
    sim = make_sim(tmp_path / "off")
    try:
        rain = sim.corpus.get("weather-wait-out-rain")
        assert "temp_easygoing" not in rain.scope.required_tags
        assert "temp_easygoing" in rain.scope.tags
    finally:
        sim.close()
