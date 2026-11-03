"""A call the model server never answers is counted apart from a reply with
nothing usable in it (SpeechModel.errors), wherever the call is made, and a
run records the count. A server that goes down mid-run leaves a run that
looks complete, so experiments/reproduce.sh redoes any run with one."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from experiments.unanswered import main as check
from hearthwick.config import SimConfig
from hearthwick.llm import SpeechModel
from hearthwick.sim import Simulation


class Server:
    """A BEAR LLM stand-in that is down, or answers with ``content``."""

    def __init__(self, down=False, content="Good morning."):
        self.down, self.content = down, content

    async def generate(self, **kw):
        if self.down:
            raise ConnectionError("Connection refused")
        return SimpleNamespace(content=self.content, usage={})


def model(server):
    speech = SpeechModel("http://localhost:8355/v1", top_p=0.95, top_k=20)
    speech._llm = server
    return speech


def test_a_server_that_is_down_is_an_error():
    speech = model(Server(down=True))
    assert asyncio.run(speech.say("sys", "hello", seed=1)) is None
    assert (speech.failures, speech.errors) == (1, 1)


def test_an_empty_reply_is_a_failure_but_not_an_error():
    speech = model(Server(content=""))
    assert asyncio.run(speech.say("sys", "hello", seed=1)) is None
    assert (speech.failures, speech.errors) == (1, 0)


def test_bears_generators_count_theirs_and_still_see_the_failure():
    speech = model(Server(down=True))
    with pytest.raises(ConnectionError):
        asyncio.run(speech.llm_for_generation().generate(system="s", user="u",
                                                         temperature=0.4))
    assert speech.errors == 1


def test_a_run_records_them(tmp_path):
    sim = make_sim(tmp_path)
    sim.speech = model(Server(down=True))
    asyncio.run(sim.speech.say("sys", "hello", seed=1))
    sim.close()
    assert sim.log.meta["speech_errors"] == 1 and sim.log.meta["speech_failures"] == 1


def make_sim(tmp_path):
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                                runs_dir=tmp_path, embedder="bm25"))


def test_a_resumed_run_keeps_the_count_from_before_its_checkpoint(tmp_path):
    sim = make_sim(tmp_path / "first")
    sim.speech = model(Server(down=True))
    asyncio.run(sim.speech.say("sys", "hello", seed=1))
    path = asyncio.run(sim.save())
    sim.close()
    resumed = make_sim(tmp_path / "again")
    resumed.speech = model(Server(down=True))
    resumed.resume_from(path)
    asyncio.run(resumed.speech.say("sys", "hello", seed=2))
    resumed.close()
    assert resumed.log.meta["speech_errors"] == 2


def test_a_checkpoint_from_before_the_count_leaves_the_run_unmeasured(tmp_path):
    sim = make_sim(tmp_path / "first")
    path = asyncio.run(sim.save())
    sim.close()
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["speech_errors"]
    path.write_text(json.dumps(data), encoding="utf-8")
    resumed = make_sim(tmp_path / "again")
    resumed.resume_from(path)
    resumed.close()
    assert resumed.log.meta["speech_errors"] is None


def test_the_check_refuses_lost_calls_and_unmeasured_runs(tmp_path):
    def record(name, data):
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    clean = record("clean.json", {"speech_errors": 0, "config": {"seed": 1}})
    lost = record("lost.json", {"speech_errors": 3, "config": {"seed": 2}})
    old = record("old.json", {"speech_failures": 5, "config": {"seed": 3}})
    unmeasured = record("resumed.json", {"speech_errors": None})
    step = record("step.json", {"meta": {"errors": 0, "failures": 4}})
    step_lost = record("step_lost.json", {"meta": {"errors": 1}})
    assert check([clean, step]) == 0
    for bad in (lost, old, unmeasured, step_lost):
        assert check([clean, bad]) == 1
    assert check(["--allow-unmeasured", clean, old, unmeasured]) == 0
    assert check(["--allow-unmeasured", lost]) == 1


def test_a_resumed_run_counts_its_calls_from_the_start(tmp_path):
    sim = make_sim(tmp_path / "first")
    sim.speech = model(Server())
    asyncio.run(sim.speech.say("sys", "hello", seed=1))
    asyncio.run(sim.speech.say("sys", "again", seed=2))
    path = asyncio.run(sim.save())
    sim.close()
    resumed = make_sim(tmp_path / "again")
    resumed.speech = model(Server(down=True))
    resumed.resume_from(path)
    asyncio.run(resumed.speech.say("sys", "hello", seed=3))
    resumed.close()
    meta = resumed.log.meta
    assert (meta["speech_calls"], meta["speech_failures"], meta["speech_errors"]) == (3, 1, 1)
    assert "speech_counts_partial" not in meta


def test_a_checkpoint_from_before_the_counts_says_so(tmp_path):
    sim = make_sim(tmp_path / "first")
    path = asyncio.run(sim.save())
    sim.close()
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["speech_counts"]
    path.write_text(json.dumps(data), encoding="utf-8")
    resumed = make_sim(tmp_path / "again")
    resumed.resume_from(path)
    resumed.close()
    assert resumed.log.meta["speech_counts_partial"] is True
