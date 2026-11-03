"""Vectors for retrieval, from the shared embedding service.

BM25 is the default and needs nothing running, which keeps development and the
tests fast. It is not enough for the knowledge work: it normalizes the best
match of every query to 1.0, so a fixed similarity threshold means something
different each time, and deciding whether an incoming fact duplicates one a
character already holds needs a stable cosine distance.

This client posts to the embedding service that serving/ runs (port 8360), a
2048-d text and image embedder. Situation strings
repeat constantly, so it caches; if the service is unreachable the caller falls
back to BM25 rather than failing a run.
"""

from __future__ import annotations

import logging
from collections import OrderedDict

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:8360"
CACHE_SIZE = 20000
# How often a request waiting on a service that stopped answering asks it again.
POLL_SECONDS = 15.0
# What the service is asked to embed to show it can, kept out of the cache.
PROBE_TEXT = "ok"


class ServiceEmbedder:
    """Duck-types BEAR's ``Embedder`` against the embedding service.

    The service is task-aware, so a query and a stored passage are encoded
    differently. ``is_query`` carries that through, which is why this cannot
    simply be an OpenAI-style endpoint call: that API has no field for it.
    """

    def __init__(self, url: str = DEFAULT_URL, api_key: str | None = None,
                 timeout: float = 60.0, batch_size: int = 128, wait_seconds: float = 0.0):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.batch_size = batch_size
        # How long a failed request waits for the service to embed again
        # (SimConfig.server_wait_minutes), and the outages waited out.
        self.wait_seconds = wait_seconds
        self.outages = 0
        self.outage_seconds = 0.0
        self.model_id = ""
        self.dim = 0
        self.calls = 0
        self.cache_hits = 0
        self.seconds = 0.0            # spent waiting on the service, for the cost section
        self._cache: OrderedDict[tuple[str, bool], np.ndarray] = OrderedDict()
        # Documents kept for good once embedded, beside the cache of recent
        # ones (set with config.forget_faded or config.forget_the_dead). A
        # memory index that drops items is rebuilt from what is left, and
        # BEAR asks for every remaining vector again: from here they come
        # back as first computed, in about a second, where re-embedding tens
        # of thousands would take a minute and move each vector a little with
        # its batch. Queries keep to the recent cache.
        self.keep_documents = False
        self._documents: dict[str, np.ndarray] = {}

    # -- lifecycle ----------------------------------------------------------

    def connect(self) -> bool:
        """Check the service answers and record what it serves."""
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                import json
                health = json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.warning("Embedding service at %s unavailable: %s", self.url, exc)
            return False
        self.model_id = str(health.get("model_id") or health.get("model") or "")
        self.dim = int(health.get("dim") or 0)
        # Its health says nothing of whether it can embed: on 2026-10-17 it
        # reported itself loaded while every request failed with a CUDA
        # error. So it is asked to embed, and waited on if it cannot.
        if not self._probe() and not self._wait_for_service():
            logger.warning("Embedding service at %s answers but cannot embed", self.url)
            return False
        logger.info("Embedder: %s (dim %d) at %s", self.model_id, self.dim, self.url)
        return True

    def info(self) -> dict:
        return {"kind": "service", "url": self.url, "model": self.model_id,
                "dim": self.dim, "calls": self.calls, "cache_hits": self.cache_hits,
                "seconds": round(self.seconds, 1), "outages": self.outages,
                "outage_seconds": round(self.outage_seconds, 1)}

    # -- the BEAR Embedder interface ---------------------------------------

    def embed(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim or 2048), dtype=np.float32)

        # What is already held is taken, and marked as just used, before
        # anything new goes in. Read back afterwards, a hit at the old end of
        # a full cache could be pushed out by this call's own misses: a 28-day
        # survival run stopped with a KeyError when a visitor joined and the
        # corpus was embedded again (2026-10-04).
        unique = list(dict.fromkeys(texts))
        got: dict[str, np.ndarray] = {}
        for text in unique:
            if (text, is_query) in self._cache:
                got[text] = self._cache[(text, is_query)]
                self._cache.move_to_end((text, is_query))
            elif not is_query and text in self._documents:
                got[text] = self._documents[text]
        missing = [t for t in unique if t not in got]
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start:start + self.batch_size]
            for text, vector in zip(batch, self._post(batch, is_query)):
                self._remember(text, is_query, vector)
                got[text] = vector

        self.cache_hits += len(texts) - len(missing)
        return np.vstack([got[text] for text in texts])

    def embed_single(self, text: str, is_query: bool = False) -> np.ndarray:
        return self.embed([text], is_query=is_query)[0]

    # -- internals ----------------------------------------------------------

    def _probe(self) -> bool:
        """Whether the service embeds now, asked directly so the answer is
        neither cached nor counted among the run's calls."""
        import json
        import urllib.request

        request = urllib.request.Request(
            f"{self.url}/embed",
            data=json.dumps({"texts": [PROBE_TEXT], "kind": "passage"}).encode(),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status == 200
        except Exception:  # noqa: BLE001 - any failure means it cannot embed
            return False

    def _wait_for_service(self) -> bool:
        """Wait, up to ``wait_seconds``, for the service to embed again. The
        whole village waits with it, since nothing can be recalled meanwhile.
        On 2026-10-17 a GPU reset left it failing every request until its
        container was restarted, so the wait is for whoever restarts it, and
        a service that does not come back stops the run, which resumes from
        its last checkpoint. Returns whether it came back."""
        import time

        if not self.wait_seconds:
            return False
        logger.warning("Embedding service at %s cannot embed; waiting up to %.0f minutes",
                       self.url, self.wait_seconds / 60)
        started = time.monotonic()
        while time.monotonic() - started < self.wait_seconds:
            time.sleep(POLL_SECONDS)
            if self._probe():
                waited = time.monotonic() - started
                self.outages += 1
                self.outage_seconds += waited
                logger.warning("Embedding service at %s embeds again after %.0f s",
                               self.url, waited)
                return True
        logger.error("Embedding service at %s did not come back within %.0f minutes",
                     self.url, self.wait_seconds / 60)
        return False

    def _remember(self, text: str, is_query: bool, vector: np.ndarray) -> None:
        if self.keep_documents and not is_query:
            self._documents[text] = vector
            return
        self._cache[(text, is_query)] = vector
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)

    def _post(self, texts: list[str], is_query: bool) -> np.ndarray:
        import json
        import urllib.request

        payload = json.dumps({"texts": [t or " " for t in texts],
                              "kind": "query" if is_query else "passage"}).encode()
        request = urllib.request.Request(
            f"{self.url}/embed", data=payload,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
        )
        import time

        self.calls += 1
        started = time.perf_counter()
        try:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.load(response)
            except OSError:
                # urllib's errors, refusals and timeouts are all OSErrors. A
                # service that cannot embed now is waited on, and the request
                # sent once more. One that still embeds turned this request
                # down for itself, and that is raised as before.
                if not self.wait_seconds or self._probe() or not self._wait_for_service():
                    raise
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.load(response)
        finally:
            self.seconds += time.perf_counter() - started
        vectors = np.asarray(body["vectors"], dtype=np.float32)
        self.dim = int(body.get("dim") or vectors.shape[1])
        if body.get("model"):
            self.model_id = str(body["model"])
        return vectors


class BearEmbedder(ServiceEmbedder):
    """BEAR's own Embedder (``bear.retriever.Embedder``), for an embedding model
    other than the service's, behind the same cache and document keeping.

    The model name picks BEAR's mode: ``openai:<name>`` calls OpenAI's
    embeddings API with OPENAI_API_KEY, or any server that speaks that API
    when OPENAI_BASE_URL names it (Ollama, LM Studio, vLLM). Both are read from
    the environment or the repository's .env. A sentence-transformers name
    such as ``BAAI/bge-base-en-v1.5`` runs a local model on the CPU or GPU,
    and an MLX name runs on a Mac.
    ``hash`` gives vectors with no meaning, for tests. None of these knows a
    query from a passage the way the service's model does, beyond a prefix
    BEAR can add, and the vectors are made unit length as the service's are.
    """

    def __init__(self, model_name: str, batch_size: int = 128):
        super().__init__(url="", batch_size=batch_size)
        self.model_name = model_name
        self._bear = None

    def connect(self) -> bool:
        if not self.model_name:
            logger.warning("--embedder bear needs --embed-model")
            return False
        import os

        from hearthwick.llm import env_value

        for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            value = None if os.environ.get(name) else env_value(name)
            if value:
                os.environ[name] = value
        from bear.retriever import Embedder

        try:
            self._bear = Embedder(model_name=self.model_name)
            probe = self._bear.embed([PROBE_TEXT])
        except Exception as exc:          # a missing package, key or model
            logger.warning("Embedding model %s unavailable: %s", self.model_name, exc)
            return False
        self.dim = int(probe.shape[1])
        self.model_id = self.model_name
        logger.info("Embedder: %s (dim %d), through BEAR", self.model_name, self.dim)
        return True

    def info(self) -> dict:
        return {"kind": "bear", "model": self.model_name, "dim": self.dim,
                "calls": self.calls, "cache_hits": self.cache_hits,
                "seconds": round(self.seconds, 1)}

    def _post(self, texts: list[str], is_query: bool) -> np.ndarray:
        import time

        self.calls += 1
        started = time.perf_counter()
        try:
            vectors = np.asarray(self._bear.embed(list(texts), is_query=is_query),
                                 dtype=np.float32)
        finally:
            self.seconds += time.perf_counter() - started
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)
