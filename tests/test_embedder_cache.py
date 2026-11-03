"""The embedding client's cache (hearthwick/embedder.py). A 28-day survival
run stopped with a KeyError: the corpus was embedded again when a visitor
joined, the cache was full, and the call's own new texts pushed out texts it
had found there and had yet to read back."""

import numpy as np

from hearthwick import embedder
from hearthwick.embedder import ServiceEmbedder


def fake(monkeypatch, size):
    monkeypatch.setattr(embedder, "CACHE_SIZE", size)
    e = ServiceEmbedder("http://nowhere")
    e.dim = 4
    posted = []

    def post(texts, is_query):
        posted.extend(texts)
        return np.array([[len(t), sum(map(ord, t)) % 97, 1.0 if is_query else 0.0, 1.0]
                         for t in texts], dtype=np.float32)
    monkeypatch.setattr(e, "_post", post)
    return e, posted


def test_a_full_cache_keeps_what_a_call_found_there(monkeypatch):
    e, posted = fake(monkeypatch, 5)
    corpus = ["a", "bb", "ccc"]
    e.embed(corpus)
    e.embed(["q1", "q2"], is_query=True)
    # Full, with the corpus at the old end. Embedding it again with two new
    # texts pushes two entries out before the corpus is read back.
    out = e.embed(corpus + ["dddd", "eeeee"])
    assert out.shape == (5, 4)
    assert [int(v[0]) for v in out] == [1, 2, 3, 4, 5]
    assert posted == ["a", "bb", "ccc", "q1", "q2", "dddd", "eeeee"]
    assert len(e._cache) == 5


def test_repeats_and_order_are_kept(monkeypatch):
    e, _ = fake(monkeypatch, 100)
    out = e.embed(["x", "yy", "x"])
    assert [int(v[0]) for v in out] == [1, 2, 1] and e.cache_hits == 1
