"""Every request carries the run's top-p and top-k as well as its temperature
(SimConfig.llm_top_p), so a run samples the same whatever the model server's
defaults. The paper's September runs got top-p 0.95 and top-k 20 from the
server's defaults, which stopped applying on 2026-10-12."""

import asyncio
from types import SimpleNamespace

from bear import LLM, LLMBackend

from hearthwick.__main__ import PROFILES
from hearthwick.config import SimConfig
from hearthwick.llm import Sampled, SpeechModel


class Recorder:
    """A BEAR LLM stand-in that keeps what each request asked for."""

    def __init__(self):
        self.calls = []

    async def generate(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content="Good morning.", usage={})


def model(**kw):
    speech = SpeechModel("http://localhost:8355/v1", **kw)
    speech._llm = Recorder()
    return speech


def test_the_paper_sends_what_september_got():
    config = SimConfig()
    assert (config.llm_temperature, config.llm_top_p, config.llm_top_k) == (0.8, 0.95, 20)
    assert "llm_top_p" not in PROFILES["paper"] and "llm_top_k" not in PROFILES["paper"]
    assert config.to_dict()["llm_top_p"] == 0.95          # in the run's record


def test_a_run_recorded_before_them_resumes_sending_none():
    old = {k: v for k, v in SimConfig().to_dict().items() if k not in ("llm_top_p", "llm_top_k")}
    resumed = SimConfig.from_saved(old, SimConfig())
    assert resumed.llm_top_p is None and resumed.llm_top_k is None
    kept = SimConfig.from_saved(SimConfig(llm_top_p=0.9, llm_top_k=40).to_dict(), SimConfig())
    assert (kept.llm_top_p, kept.llm_top_k) == (0.9, 40)


def test_speech_sends_them():
    speech = model(top_p=0.95, top_k=20)
    asyncio.run(speech.say("sys", "hello", seed=1))
    for call in speech._llm.calls:
        assert (call["temperature"], call["top_p"], call["top_k"]) == (0.8, 0.95, 20)


def test_without_them_a_request_is_as_before():
    speech = model()
    asyncio.run(speech.say("sys", "hello", seed=1))
    asyncio.run(speech.llm_for_generation().generate(system="s", user="u", temperature=0.4))
    for call in speech._llm.calls:
        assert "top_p" not in call and "top_k" not in call


def test_bears_generators_get_them_unless_they_set_their_own():
    speech = model(top_p=0.95, top_k=20)
    llm = speech.llm_for_generation()
    assert isinstance(llm, Sampled) and llm.calls is speech._llm.calls
    asyncio.run(llm.generate(system="s", user="u", temperature=0.4))
    asyncio.run(llm.generate(system="s", user="u", temperature=0.4, top_k=5))
    first, second = speech._llm.calls
    assert (first["temperature"], first["top_p"], first["top_k"]) == (0.4, 0.95, 20)
    assert (second["top_p"], second["top_k"]) == (0.95, 5)


def test_a_hosted_model_gets_none():
    speech = SpeechModel(None, "some-model", provider="anthropic", top_p=0.95, top_k=20)
    assert speech.sampling == {}


def test_the_request_on_the_wire_carries_them():
    """Through BEAR's OpenAI backend, as the paper's model server sees it:
    top-p as a parameter, top-k in the body vLLM reads."""
    sent = {}

    async def create(**kw):
        sent.update(kw)
        message = SimpleNamespace(content="Good morning.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    speech = SpeechModel("http://localhost:8355/v1", "qwen", top_p=0.95, top_k=20)
    speech._llm = LLM(backend=LLMBackend.OPENAI, model="qwen", base_url=speech.base_url)
    speech._llm._backend._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert asyncio.run(speech.say("sys", "hello", seed=3)) == "Good morning."
    assert (sent["temperature"], sent["top_p"], sent["extra_body"]["top_k"]) == (0.8, 0.95, 20)
    assert sent["seed"] == 3
