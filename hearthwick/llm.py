"""Speech generation through an OpenAI-compatible endpoint.

Works with the local Qwen3.8 27B server (default ``localhost:8355``), LM Studio
(``localhost:1234/v1``) or Ollama (``localhost:11434``). An Ollama URL uses
BEAR's native Ollama backend: Ollama's OpenAI-compatible endpoint ignores the
thinking parameters, so a reasoning model spends the whole budget thinking and
returns nothing to say.

Speech asks BEAR for real output only: ``thinking=False`` so a short reply is
not spent on reasoning, and ``reasoning_fallback=False`` so a villager never
speaks the model's reasoning aloud. An empty reply counts as a failure and the
line is skipped.

A hosted model (``provider`` anthropic, openai or gemini, ``--llm-provider``)
goes through BEAR's own backend for it, with its key from the environment or
the repository's .env, read when connecting and never logged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from bear import LLM, LLMBackend, strip_actions
from bear.backends.llm.ollama_backend import normalize_host

logger = logging.getLogger(__name__)

THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

# Hosted providers, and the name of each one's key.
HOSTED = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GOOGLE_API_KEY"}


def hosted_key(provider: str) -> str | None:
    """A hosted provider's key, from the environment or the repository's .env."""
    return env_value(HOSTED[provider])


def env_value(name: str) -> str | None:
    """A variable from the environment or, failing that, the repository's
    .env. Keys are read this way rather than given on the command line, where
    the process list and shell history would show them."""
    if os.environ.get(name):
        return os.environ[name].strip()
    from hearthwick.config import ROOT
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name and value.strip():
                return value.strip().strip('"').strip("'")
    return None


# How often a call waiting on a server that stopped answering asks it again.
POLL_SECONDS = 10.0


class SpeechModel:
    # Also set in __init__. Here too, so a model built without it (as some
    # tests build one) still keeps time, and sends no sampling values.
    seconds = 0.0
    errors = 0
    provider = top_p = top_k = None
    # How long a failed call waits for a server that stopped answering
    # (SimConfig.server_wait_minutes), and the outages waited out. Zero
    # waits not at all, as a model built without it does.
    wait_seconds = 0.0
    outages = 0
    outage_seconds = 0.0

    def __init__(self, base_url: str | None, model: str | None = None, concurrency: int = 4,
                 max_tokens: int = 80, temperature: float = 0.8, timeout: float = 60.0,
                 api_key: str | None = None, provider: str | None = None,
                 top_p: float | None = None, top_k: int | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.api_key = api_key
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        # Sent with every request when set (SimConfig.llm_top_p), so the
        # model samples the same whatever its server's defaults.
        self.top_p = top_p
        self.top_k = top_k
        self.timeout = timeout
        self._sem = asyncio.Semaphore(concurrency)
        self._llm: LLM | None = None
        self.calls = 0
        self.failures = 0
        # Calls the server never answered: refused, timed out or failed, after
        # BEAR's own retries. They are failures too, but counted apart from a
        # reply with nothing usable in it, which a healthy server also gives.
        # A server that goes down mid-run makes these, and the run carries on
        # with lines unsaid, news passed on unreframed and lessons unwritten,
        # so a paper run with any is redone (experiments/reproduce.sh).
        self.errors = 0
        # Seconds spent waiting on the model, summed over calls. Calls overlap
        # up to ``concurrency``, so this is not wall-clock time. Divided by
        # ``calls`` it is the mean latency, which the cost section reports.
        self.seconds = 0.0

    @property
    def is_ollama(self) -> bool:
        return ":11434" in self.base_url

    async def connect(self) -> bool:
        """Resolve the model name and check the server answers."""
        if self.provider in HOSTED:
            key = self.api_key or hosted_key(self.provider)
            if not self.model or not key:
                logger.warning("A %s model needs a name and a key", self.provider)
                return False
            self._llm = LLM(backend=LLMBackend(self.provider), model=self.model, api_key=key)
            logger.info("Speech model: %s (%s, hosted)", self.model, self.provider)
            return True
        from openai import AsyncOpenAI

        models_url = self.base_url
        if self.is_ollama and not models_url.endswith("/v1"):
            models_url = f"{models_url}/v1"
        client = AsyncOpenAI(base_url=models_url, api_key=self.api_key or "not-needed",
                             timeout=self.timeout)
        try:
            models = [m.id async for m in client.models.list()]
        except Exception as exc:  # noqa: BLE001 - any failure means unavailable
            logger.warning("LLM server at %s unavailable: %s", self.base_url, exc)
            await client.close()
            return False
        if not models:
            logger.warning("LLM server at %s lists no models", self.base_url)
            await client.close()
            return False
        if self.model is None:
            self.model = models[0]
        elif self.model not in models:
            logger.warning("Model %r not served at %s (have: %s)", self.model, self.base_url, models)
            await client.close()
            return False
        await client.close()
        if self.is_ollama:
            host = normalize_host(self.base_url.removesuffix("/v1"))
            self._llm = LLM(backend=LLMBackend.OLLAMA, model=self.model, host=host)
        else:
            self._llm = LLM(backend=LLMBackend.OPENAI, model=self.model,
                            base_url=self.base_url, api_key=self.api_key)
        logger.info("Speech model: %s at %s (%s backend)", self.model, self.base_url,
                    "ollama" if self.is_ollama else "openai")
        return True

    @property
    def available(self) -> bool:
        return self._llm is not None

    @property
    def sampling(self) -> dict:
        """The sampling values sent beyond the temperature, only those set.
        None to a hosted model, which never had a local server's defaults to
        make up for, and some of which refuse top-p beside a temperature."""
        if self.provider in HOSTED:
            return {}
        return {k: v for k, v in (("top_p", self.top_p), ("top_k", self.top_k))
                if v is not None}

    async def say(self, system: str, user: str, seed: int,
                  history: list[tuple[str, str]] | None = None) -> str | None:
        """One spoken line. ``history`` is what was said before ``user``, as
        (role, text) turns, the speaker's own lines as the assistant's."""
        if self._llm is None:
            return None
        from bear.backends.llm.base import Message

        # Only when there are any, so a call without them is sent as before.
        extra = {"history": [Message(role=r, content=t) for r, t in history]} if history else {}
        extra.update(self.sampling)
        async with self._sem:
            self.calls += 1
            started = time.perf_counter()
            try:
                response = await self._generate(
                    system=system, user=user, **extra,
                    temperature=self.temperature, max_tokens=self.max_tokens,
                    seed=seed, thinking=False, reasoning_fallback=False,
                )
            except Exception as exc:  # noqa: BLE001 - a failed line must not stop the sim
                self.failures += 1
                self.errors += 1
                logger.warning("Speech generation failed: %s", exc)
                return None
            finally:
                self.seconds += time.perf_counter() - started
        line = clean_line(THINK_RE.sub("", response.content))
        if line is None:
            self.failures += 1
            logger.warning("Speech model returned no dialogue (thinking left on?)")
        return line

    async def _generate(self, *args, **kwargs):
        """The LLM's ``generate``, waiting out a server that went down.

        BEAR retries a failed call for about fifteen seconds. A model server
        that crashes takes minutes to come back: on 2026-10-17 a GPU reset
        took this one down at 22:27 and it answered again about four minutes
        later. A run that went on meanwhile would have lost every call in
        those minutes, and a paper run with any lost call is redone. So when
        a call fails and the server no longer answers, the call waits until
        it answers again, for up to ``wait_seconds``, and is sent once more.
        A lockstep run waits with it, so its outcome does not depend on the
        outage. A call that fails while the server answers fails as before.
        """
        try:
            return await self._llm.generate(*args, **kwargs)
        except Exception:
            if not self.wait_seconds or self.provider in HOSTED:
                raise
            if not await self._wait_for_server():
                raise
            return await self._llm.generate(*args, **kwargs)

    async def _wait_for_server(self) -> bool:
        """Whether the server came back after an outage: False at once if it
        answers now (the call failed for another reason), else True once it
        answers again, or False when ``wait_seconds`` runs out."""
        if await self._probe():
            return False
        logger.warning("Speech model at %s stopped answering; waiting up to %.0f minutes",
                       self.base_url, self.wait_seconds / 60)
        started = time.monotonic()
        while time.monotonic() - started < self.wait_seconds:
            await asyncio.sleep(POLL_SECONDS)
            if await self._probe():
                waited = time.monotonic() - started
                self.outages += 1
                self.outage_seconds += waited
                logger.warning("Speech model at %s answers again after %.0f s",
                               self.base_url, waited)
                return True
        logger.error("Speech model at %s did not come back within %.0f minutes",
                     self.base_url, self.wait_seconds / 60)
        return False

    async def _probe(self) -> bool:
        """Whether the server writes a reply now: a one-token request rather
        than a health address, since a server can list its model while it
        cannot run it (the embedding service did on 2026-10-17)."""
        import json
        import urllib.request

        url = self.base_url if not self.is_ollama or self.base_url.endswith("/v1") \
            else f"{self.base_url}/v1"
        body = json.dumps({"model": self.model, "max_tokens": 1,
                           "messages": [{"role": "user", "content": "ok"}]}).encode()
        request = urllib.request.Request(
            f"{url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})

        def ask() -> bool:
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.status == 200
            except Exception:  # noqa: BLE001 - any failure means not answering
                return False

        return await asyncio.to_thread(ask)

    def llm_for_generation(self):
        """The underlying BEAR LLM, for bear.evolution's generators.

        say() is shaped for one short spoken line -- capped tokens, thinking
        off. Authoring an instruction is a different job, so consolidation
        talks to the model directly rather than through that door. BEAR's
        generators set a temperature and nothing else, so the LLM is wrapped
        to send this model's other sampling values too, and to count a call
        the server never answers among this model's errors.
        """
        if self._llm is None:
            return None
        return Sampled(self._llm, self.sampling, counter=self)

    def info(self) -> dict:
        return {"base_url": self.base_url, "model": self.model}


class Sampled:
    """A BEAR LLM that sends the given sampling values with any request that
    does not set its own, and adds a request that raises to ``counter``'s
    errors (SpeechModel.errors). Everything else is the LLM's."""

    def __init__(self, llm: LLM, sampling: dict, counter=None):
        self.llm = llm
        self.sampling = dict(sampling)
        self.counter = counter

    async def generate(self, *args, **kwargs):
        for name, value in self.sampling.items():
            if kwargs.get(name) is None:
                kwargs[name] = value
        # Through the speech model's own call when there is one, so a lesson
        # being written waits out an outage as a spoken line does.
        call = getattr(self.counter, "_generate", None) or self.llm.generate
        try:
            return await call(*args, **kwargs)
        except Exception:
            if self.counter is not None:
                self.counter.errors += 1
            raise

    def __getattr__(self, name):
        return getattr(self.llm, name)


def clean_line(text: str) -> str | None:
    """Reduce model output to one line of spoken dialogue."""
    text = strip_actions(text or "").strip()
    if not text:
        return None
    line = text.splitlines()[0].strip()
    line = re.sub(r"^[A-Z][a-z]+:\s*", "", line)   # "Rosa: ..." prefix
    line = re.sub(r"^\*[^*]*\*\s*", "", line)      # leading *stage direction*
    line = line.strip().strip('"').strip("“”").strip()
    return line[:300] or None
