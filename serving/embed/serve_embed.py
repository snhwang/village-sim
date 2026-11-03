"""Nemotron embedding service, the embedder Village Sim's paper runs used.

One process holds the embedding model, and Village Sim is its client
(``--embedder service``, port 8360).

Two request shapes are served:

* ``POST /v1/embeddings`` — the OpenAI shape, so any client that speaks it
  (including BEAR's OpenAI embedding mode) works with only a base URL. That API
  has no field for "query or document", which this model distinguishes, so the
  side is taken from ``kind`` in the body or from a ``-query`` / ``-doc``
  suffix on the model name.
* ``POST /embed`` — ``texts``, base64 ``images`` and ``kind``, the shape
  Village Sim's client sends.

Text and images land in the same 2048-d space.

It runs on a GPU when one is present, and otherwise on the CPU, in bfloat16
either way. A CPU with AVX-512 BF16 (AMD Zen 4 or Zen 5) embeds a short
sentence in about a tenth to a third of a second.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger("embed")

MODEL_ID = os.environ.get("EMBED_MODEL_ID", "nvidia/llama-nemotron-embed-vl-1b-v2")
SERVED_NAME = os.environ.get("EMBED_SERVED_NAME", "nemotron-embed-vl")
MAX_BATCH = int(os.environ.get("EMBED_MAX_BATCH", "256"))
API_KEY = os.environ.get("EMBED_API_KEY", "").strip()
PRELOAD = os.environ.get("EMBED_PRELOAD", "1") not in ("0", "false", "False")
DEVICE = os.environ.get("EMBED_DEVICE") or None

QUERY_SUFFIXES = ("-query", "-q")
DOC_SUFFIXES = ("-doc", "-document", "-passage")


def gpu_context_lost(exc: BaseException) -> bool:
    """Whether ``exc`` means this process's GPU context is gone for good.

    On 2026-10-17 a GPU reset (NVIDIA driver event 153) left every request
    failing with "CUDA error: unknown error" while /health went on reporting
    the model loaded, until the container was restarted by hand. A CUDA error
    of that kind cannot be recovered inside the process. Running out of
    memory can, and is not one."""
    text = f"{type(exc).__name__}: {exc}"
    return "CUDA error" in text and "out of memory" not in text


def exit_for_restart(exc: BaseException) -> None:
    """End the process so Docker's restart policy (``unless-stopped``) starts
    the container again with a fresh GPU context, as the chat server's own
    container does when it hits the same error. ``os._exit`` because this
    runs in a worker thread, where ``sys.exit`` would end only the thread."""
    logger.critical("GPU context lost (%s); exiting so the container restarts", exc)
    logging.shutdown()
    os._exit(70)


def _unit(vectors: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization, matching MIRA's stored vectors."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


class NemotronEmbedder:
    """Lazily loaded text+image embedder (2048-d, task-aware).

    The model runs on the GPU and is not thread-safe, so calls are serialized.
    Requests are batched: ``encode_queries`` and ``encode_documents`` take
    lists, and one batched call is far cheaper than a call per text.
    """

    def __init__(self, model_id: str = MODEL_ID, device: str | None = DEVICE):
        self.model_id = model_id
        self.device = device
        self.dim = 0
        self._model: Any = None
        self._torch: Any = None
        self._load_lock = threading.Lock()
        self._gpu_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            from transformers import AutoModel

            self._torch = torch
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading %s on %s", self.model_id, self.device)
            model = AutoModel.from_pretrained(
                self.model_id, dtype=torch.bfloat16, trust_remote_code=True,
                device_map="auto" if self.device == "cuda" else None,
            )
            if self.device != "cuda":
                model = model.to(self.device)
            model.eval()
            self._model = model
            self.dim = int(self.encode_texts(["dimension probe"], "document").shape[1])
            logger.info("Loaded %s (dim=%d)", self.model_id, self.dim)

    def _on_gpu(self, run) -> np.ndarray:
        """Run one batch on the model, and end the process if the GPU context
        is lost (``gpu_context_lost``). Copying back to the CPU is inside,
        since that is where a lost context often shows first."""
        try:
            with self._gpu_lock, self._torch.inference_mode():
                return run().cpu().float().numpy()
        except Exception as exc:
            if gpu_context_lost(exc):
                exit_for_restart(exc)
            raise

    def encode_texts(self, texts: list[str], kind: str) -> np.ndarray:
        self.load()
        return _unit(self._on_gpu(
            lambda: self._model.encode_queries(texts) if kind == "query"
            else self._model.encode_documents(texts=texts)))

    def encode_images(self, images: list[Any]) -> np.ndarray:
        self.load()
        return _unit(self._on_gpu(
            lambda: self._model.encode_documents(images=[im.convert("RGB") for im in images])))


def resolve_kind(value: str | None, default: str = "document") -> str:
    """Map the many spellings of 'this is a search query' onto two modes."""
    if value is None:
        return default
    return "query" if str(value).lower() in ("query", "q", "queries") else "document"


def split_model_name(name: str | None) -> tuple[str, str | None]:
    """Return (base name, kind from suffix). ``nemotron-embed-vl-query`` -> query."""
    if not name:
        return SERVED_NAME, None
    lowered = name.lower()
    for suffix in QUERY_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)], "query"
    for suffix in DOC_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)], "document"
    return name, None


def decode_images(payload: Any) -> list[Any]:
    """Decode base64 images, matching MIRA's /api/embed payload."""
    if not payload:
        return []
    from PIL import Image, UnidentifiedImageError

    if isinstance(payload, (str, bytes)):
        payload = [payload]
    images = []
    for item in payload:
        if isinstance(item, str) and item.startswith("data:"):
            item = item.split(",", 1)[-1]
        try:
            raw = base64.b64decode(item, validate=False)
            images.append(Image.open(io.BytesIO(raw)))
        except (binascii.Error, ValueError, OSError, UnidentifiedImageError) as exc:
            raise HTTPException(400, f"could not decode image: {exc}") from exc
    return images


embedder = NemotronEmbedder()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if PRELOAD:
        await run_in_threadpool(embedder.load)
    yield


app = FastAPI(title="Nemotron embedding service", lifespan=lifespan)


def check_auth(authorization: str | None) -> None:
    if not API_KEY:
        return
    expected = f"Bearer {API_KEY}"
    if authorization != expected:
        raise HTTPException(401, "invalid or missing bearer token")


def check_model(name: str | None) -> str:
    base, kind = split_model_name(name)
    if base and base not in (SERVED_NAME, MODEL_ID):
        raise HTTPException(404, f"model {name!r} not served; this server serves {SERVED_NAME!r}")
    return kind


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": SERVED_NAME, "model_id": MODEL_ID,
            "dim": embedder.dim, "loaded": embedder.loaded}


@app.get("/health/deep")
async def health_deep() -> dict:
    """Health that embeds a word, for Docker's healthcheck. /health says the
    model is loaded, which stayed true after a GPU reset left it unable to
    embed. Here a lost GPU ends the process (``exit_for_restart``), and Docker
    restarts the container, so it heals while no client is calling."""
    if not embedder.loaded:
        return {**health(), "embedded": False}
    await run_in_threadpool(embedder.encode_texts, ["health probe"], "document")
    return {**health(), "embedded": True}


@app.get("/v1/models")
def models() -> dict:
    return {"object": "list", "data": [{
        "id": SERVED_NAME, "object": "model", "owned_by": "local",
        "root": MODEL_ID, "dim": embedder.dim,
    }]}


@app.post("/v1/embeddings")
async def embeddings(body: dict = Body(...), authorization: str | None = Header(default=None)) -> dict:
    """OpenAI-shaped embeddings. ``kind`` selects the query or document side."""
    check_auth(authorization)
    kind_from_name = check_model(body.get("model"))

    texts = body.get("input")
    if isinstance(texts, str):
        texts = [texts]
    texts = [str(t) if str(t).strip() else " " for t in (texts or [])]
    if not texts:
        raise HTTPException(400, "input is required")
    if len(texts) > MAX_BATCH:
        raise HTTPException(400, f"at most {MAX_BATCH} inputs per request")

    kind = resolve_kind(body.get("kind"), default=kind_from_name or "document")
    vectors = await run_in_threadpool(embedder.encode_texts, texts, kind)
    logger.info("embeddings: %d texts, kind=%s", len(texts), kind)
    return {
        "object": "list",
        "model": SERVED_NAME,
        "data": [{"object": "embedding", "index": i, "embedding": v.tolist()}
                 for i, v in enumerate(vectors)],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


@app.post("/embed")
@app.post("/api/embed")
async def embed(body: dict = Body(...), authorization: str | None = Header(default=None)) -> dict:
    """MIRA's shape: texts plus base64 images, in one shared space.

    Also served at ``/api/embed``, the path MIRA uses, so a client only has to
    change which host it points at.
    """
    check_auth(authorization)

    texts = body.get("texts")
    if isinstance(texts, str):
        texts = [texts]
    texts = [str(t) for t in (texts or []) if str(t).strip()]
    images = decode_images(body.get("images"))
    if not texts and not images:
        raise HTTPException(400, "texts or images is required")
    if len(texts) + len(images) > MAX_BATCH:
        raise HTTPException(400, f"at most {MAX_BATCH} items per request")

    kind = resolve_kind(body.get("kind"))
    vectors: list[list[float]] = []
    kinds: list[str] = []
    if texts:
        out = await run_in_threadpool(embedder.encode_texts, texts, kind)
        vectors += [v.tolist() for v in out]
        kinds += ["text"] * len(texts)
    if images:
        out = await run_in_threadpool(embedder.encode_images, images)
        vectors += [v.tolist() for v in out]
        kinds += ["image"] * len(images)
    logger.info("embed: %d texts, %d images, kind=%s", len(texts), len(images), kind)
    return {"vectors": vectors, "dim": len(vectors[0]), "kinds": kinds,
            "model": MODEL_ID, "kind": kind}
