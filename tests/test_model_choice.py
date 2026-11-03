"""Choosing the models: a hosted language model by --llm-provider, BEAR's own
embedder by --embedder bear, and a run that stops when its embedder does not
answer rather than falling back to BM25."""

import numpy as np
import pytest

from hearthwick.__main__ import _config_from, build_parser
from hearthwick.corpus import make_embedder
from hearthwick.embedder import BearEmbedder

DEAD = "http://127.0.0.1:9"      # nothing listens on the discard port


def test_bear_embedder_gives_unit_vectors_and_keeps_documents():
    embedder = BearEmbedder("hash")
    assert embedder.connect()
    assert embedder.dim > 0
    vectors = embedder.embed(["the well has turned", "raiders on the east road"])
    assert vectors.shape == (2, embedder.dim)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    embedder.keep_documents = True
    embedder.embed(["a kept memory"])
    calls = embedder.calls
    again = embedder.embed(["a kept memory"])
    assert embedder.calls == calls            # served from the kept documents
    assert again.shape == (1, embedder.dim)
    assert embedder.info()["kind"] == "bear"
    assert embedder.info()["model"] == "hash"


def test_make_embedder_bear():
    assert isinstance(make_embedder("bear", DEAD, model="hash"), BearEmbedder)


def test_bear_without_a_model_stops_when_strict():
    assert make_embedder("bear", DEAD, model="") is None
    with pytest.raises(SystemExit, match="did not answer"):
        make_embedder("bear", DEAD, model="", strict=True)


def test_dead_service_stops_when_strict_and_falls_back_otherwise():
    assert make_embedder("service", DEAD) is None
    with pytest.raises(SystemExit, match="embedding service at http://127.0.0.1:9"):
        make_embedder("service", DEAD, strict=True)


def test_command_line_sets_the_models():
    args = build_parser().parse_args(
        ["run", "--llm-provider", "anthropic", "--model", "claude-sonnet-5-5",
         "--embedder", "bear", "--embed-model", "openai:text-embedding-3-small"])
    config = _config_from(args, lockstep=True)
    assert config.llm_provider == "anthropic"
    assert config.llm_model == "claude-sonnet-5-5"
    assert config.embedder == "bear"
    assert config.embed_model == "openai:text-embedding-3-small"
    assert config.embedder_strict


def test_only_bm25_runs_without_a_strict_embedder():
    config = _config_from(build_parser().parse_args(["run", "--embedder", "bm25"]),
                          lockstep=True)
    assert not config.embedder_strict
    default = _config_from(build_parser().parse_args(["run"]), lockstep=True)
    assert default.embedder == "service" and default.embedder_strict
    assert default.llm_provider is None and default.embed_model == ""


def test_keys_and_model_choice_in_the_record():
    config = _config_from(build_parser().parse_args(
        ["run", "--embedder", "bear", "--embed-model", "hash"]), lockstep=True)
    record = config.to_dict()
    assert record["embed_model"] == "hash"           # shapes the village, so recorded
    assert "llm_provider" in record
