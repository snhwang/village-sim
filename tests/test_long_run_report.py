"""experiments/long_run_report.py reads a 3 GB log by parsing only some events.
These check that the census it shares with experiments/population.py comes
out the same that way, and that the check's refusals are sorted by kind."""

from experiments.long_run_report import batch_means, cluster_share, refusal_kind
from experiments.population import CENSUS_TYPES, Census

DAY = 144


def _log():
    """Two years of eight days, with filler around everything that counts."""
    roster = {"t": 0, "type": "roster", "characters": [
        {"id": "ada", "stage": "adult", "partner": "wynn"},
        {"id": "wynn", "stage": "adult", "partner": "ada"},
        {"id": "sten", "stage": "adult"},
        {"id": "wystan", "stage": "adult", "visitor": True}]}
    events = [roster]
    for day in range(1, 17):
        t = day * DAY - 36
        events.append({"t": t, "type": "day_start", "day": day})
        events += [{"t": t + k, "type": "decision", "character": "ada"} for k in range(3)]
        events.append({"t": t + 5, "type": "food", "store": 100.0 + day})
        if day == 3:
            events.append({"t": t + 6, "type": "born", "character": "inga",
                           "mother": "ada", "father": "wynn"})
        if day == 9:
            events.append({"t": t + 6, "type": "married", "asker": "sten", "asked": "inga"})
            events.append({"t": t + 7, "type": "stage_change", "character": "inga",
                           "now": "child"})
        if day == 12:
            events.append({"t": t + 6, "type": "died", "character": "wynn", "age": 41.0})
        events.append({"t": t + 8, "type": "utterance", "character": "sten"})
    return events


def _census(events):
    c = Census(8)
    for e in events:
        c.see(e)
    return c.result("test", {"plan": {"days": 16}})


def test_the_census_is_the_same_from_its_own_events_alone():
    events = _log()
    full = _census(events)
    assert full == _census([e for e in events if e["type"] in CENSUS_TYPES])
    assert [r["born"] for r in full["rows"]] == [1, 0, 0]
    assert full["end"] == 3 and full["founders_alive"] == 2


def test_each_refusal_is_sorted_by_its_fault():
    assert refusal_kind("[!avoid] was given ['site'], which it does not read "
                        "(it reads ['place', 'ticks'])") == ("wrong argument name",
                                                             ["[!avoid(site=…)]"])
    assert refusal_kind("[!talk] has no target, so it cannot act") == (
        "required argument missing", ["[!talk] without target"])
    assert refusal_kind("[!warn] names 'elders', who is not anyone in this village") == (
        "names someone not in the village", ["elders"])
    assert refusal_kind("[!work] names 'flock', which is not a place in this village") == (
        "names a place not in the village", ["flock"])
    assert refusal_kind("[!hide] is not a marker this village implements")[0] == (
        "a marker the village does not have")
    assert refusal_kind("no action marker")[0] == "no action marker"
    assert refusal_kind("something new")[0] == "other"


def test_intervals_from_one_run():
    flat = batch_means([10.0] * 20)
    assert flat["mean"] == 10.0 and flat["low"] == flat["high"] == 10.0 and flat["batches"] == 4
    assert batch_means([1.0] * 9) is None
    s = cluster_share([(1, 5)] * 20)
    assert s["share"] == 0.2 and s["low"] == s["high"] == 0.2
