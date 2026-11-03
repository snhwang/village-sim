"""A server that stops answering is waited out, and a run that fails keeps
its last clean checkpoint (SimConfig.server_wait_minutes, SPECIFICATION.md,
"When a server goes down")."""

import asyncio
import io
import json
import urllib.error
import urllib.request

import pytest

from hearthwick import embedder as emb
from hearthwick import llm as llm_mod
from hearthwick.config import SimConfig
from hearthwick.embedder import ServiceEmbedder
from hearthwick.llm import SpeechModel


class Reply(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def service(monkeypatch, fail_first: int):
    """urlopen for the embedding service, refusing the first ``fail_first``
    requests."""
    sent = {"n": 0}

    def urlopen(request, timeout=None):
        sent["n"] += 1
        if sent["n"] <= fail_first:
            raise urllib.error.URLError("connection refused")
        return Reply(json.dumps({"vectors": [[0.6, 0.8]], "dim": 2}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return sent


def probes(monkeypatch, target, answers):
    seq = iter(answers)
    monkeypatch.setattr(target, "_probe", lambda: next(seq))


def test_the_default_is_to_wait_half_an_hour():
    assert SimConfig().server_wait_minutes == 30.0


# -- the embedding service ----------------------------------------------------

def test_the_embedder_waits_out_an_outage(monkeypatch):
    monkeypatch.setattr(emb, "POLL_SECONDS", 0.0)
    e = ServiceEmbedder("http://x", wait_seconds=60)
    service(monkeypatch, fail_first=1)
    probes(monkeypatch, e, [False, False, True])    # cannot embed, still not, back
    vector = e.embed_single("the well ran dry")
    assert vector.tolist() == pytest.approx([0.6, 0.8])
    assert e.outages == 1 and e.info()["outages"] == 1


def test_the_embedder_gives_up_after_its_wait(monkeypatch):
    monkeypatch.setattr(emb, "POLL_SECONDS", 0.0)
    e = ServiceEmbedder("http://x", wait_seconds=0.05)
    service(monkeypatch, fail_first=10 ** 6)
    monkeypatch.setattr(e, "_probe", lambda: False)
    with pytest.raises(urllib.error.URLError):
        e.embed_single("the well ran dry")
    assert e.outages == 0


def test_a_request_turned_down_while_the_service_embeds_is_not_waited_on(monkeypatch):
    e = ServiceEmbedder("http://x", wait_seconds=60)
    service(monkeypatch, fail_first=1)
    monkeypatch.setattr(e, "_probe", lambda: True)
    monkeypatch.setattr(e, "_wait_for_service", lambda: pytest.fail("waited"))
    with pytest.raises(urllib.error.URLError):
        e.embed_single("the well ran dry")


def test_without_a_wait_the_embedder_fails_as_before(monkeypatch):
    e = ServiceEmbedder("http://x")
    service(monkeypatch, fail_first=1)
    monkeypatch.setattr(e, "_probe", lambda: pytest.fail("probed"))
    with pytest.raises(urllib.error.URLError):
        e.embed_single("the well ran dry")


# -- the model server ---------------------------------------------------------

class DownOnce:
    """A BEAR LLM whose first call fails, as a server going down does."""

    def __init__(self):
        self.calls = 0

    async def generate(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("connection refused")
        return type("Response", (), {"content": "The well is dry again.", "usage": {}})()


def speech(monkeypatch, answers, wait=60.0):
    monkeypatch.setattr(llm_mod, "POLL_SECONDS", 0.0)
    s = SpeechModel("http://x/v1", "m")
    s.wait_seconds = wait
    s._llm = DownOnce()
    seq = iter(answers)

    async def probe():
        return next(seq)

    monkeypatch.setattr(s, "_probe", probe)
    return s


def test_a_line_waits_out_an_outage(monkeypatch):
    s = speech(monkeypatch, [False, True])           # down, then back
    line = asyncio.run(s.say("system", "user", seed=1))
    assert line == "The well is dry again."
    assert s.errors == 0 and s.outages == 1


def test_a_lesson_being_written_waits_too(monkeypatch):
    s = speech(monkeypatch, [False, True])
    reply = asyncio.run(s.llm_for_generation().generate(system="s", user="u",
                                                        temperature=0.4))
    assert reply.content == "The well is dry again."
    assert s.errors == 0 and s.outages == 1


def test_a_call_that_fails_while_the_server_answers_is_an_error(monkeypatch):
    s = speech(monkeypatch, [True])                  # it answers, so no outage
    assert asyncio.run(s.say("system", "user", seed=1)) is None
    assert s.errors == 1 and s.outages == 0


def test_without_a_wait_a_call_fails_as_before(monkeypatch):
    s = speech(monkeypatch, [], wait=0.0)
    assert asyncio.run(s.say("system", "user", seed=1)) is None
    assert s.errors == 1


# -- the run's checkpoint -----------------------------------------------------

def make_sim(tmp_path):
    from hearthwick.sim import Simulation
    return Simulation(SimConfig(seed=0, village="greater", llm_base_url=None,
                                runs_dir=tmp_path, embedder="bm25"))


def test_a_failed_tick_leaves_the_last_clean_checkpoint(tmp_path):
    from hearthwick.__main__ import _run_to
    sim = make_sim(tmp_path)
    step = sim.step

    async def failing():
        if sim.clock.tick == 7:
            raise RuntimeError("the embedding service is gone")
        return await step()

    sim.step = failing
    with pytest.raises(RuntimeError):
        asyncio.run(_run_to(sim, 20, every=5, save_at_end=True))
    saved = json.loads((sim.log.dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert saved["tick"] == 5


def test_a_run_that_ends_is_saved_where_it_ends(tmp_path):
    from hearthwick.__main__ import _run_to
    sim = make_sim(tmp_path)
    asyncio.run(_run_to(sim, 8, every=5, save_at_end=True))
    saved = json.loads((sim.log.dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert saved["tick"] == 8
