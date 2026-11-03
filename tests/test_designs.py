"""Structures are data, checked before they exist (hearthwick/designs.py)."""

import copy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from hearthwick.__main__ import PROFILES
from hearthwick.config import DATA_DIR, SimConfig
from hearthwick.designs import Library, validate
from hearthwick.server import create_app


@pytest.fixture(scope="module")
def library():
    return Library.load(DATA_DIR)


def part(design, pid):
    return next(p for p in design["parts"] if p["id"] == pid)


def refused(library, design) -> list[str]:
    return validate(design, library.vocabulary, library.materials)


def test_the_founders_designs_are_valid_and_cover_their_places(library):
    assert library.kinds == {"home": "cottage", "mill": "mill", "well": "well",
                             # the places materials add (hearthwick/economy.py)
                             "quarry": "quarry", "clay_pit": "clay_pit", "forge": "forge"}
    for design in library.designs.values():
        assert refused(library, design) == []


@pytest.mark.parametrize("change, reason", [
    (lambda d: d["parts"].append({"id": "x", "shape": "torus", "size": [1], "material": "timber"}),
     "not a shape"),
    (lambda d: d["parts"].append({"id": "x", "shape": "box", "size": [1, 1], "material": "timber"}),
     "needs a size of 3"),
    (lambda d: d["parts"].append({"id": "x", "shape": "box", "size": [1, 1, 1], "material": "gold"}),
     "not a known material"),
    (lambda d: d["parts"].append({"id": "x", "shape": "box", "size": [1, 1, 1], "material": "timber",
                                  "parent": "nowhere"}),
     "is not a part"),
    (lambda d: part(d, "hub").update(parent="sail"), "its own ancestor"),   # hub under its own sail
    (lambda d: [part(d, i).update(repeat=12) for i in ("hub", "sail")], "counting repeats"),  # 12 hubs of 12 sails
    (lambda d: d["parts"].append({"id": "x", "shape": "box", "size": [1, 1, 1], "material": "timber",
                                  "at": [0, 20, 0]}),
     "stands"),
    (lambda d: d["movements"].append({"joint": "cap", "spin": 5}), "has no joint"),
    (lambda d: d["movements"][0].update(spin=500), "at most"),
    (lambda d: d["movements"][0].update(when="thunder"), "does not know"),
    (lambda d: d["joints"][0].update(kind="slider"), "needs a hinge"),
    (lambda d: d.update(claims=["teleport"]), "cannot test"),
    (lambda d: d.update(footprint=[9, 9]), "footprint"),
])
def test_a_design_outside_the_vocabulary_is_refused_with_a_reason(library, change, reason):
    design = copy.deepcopy(library.designs["mill"])
    change(design)
    reasons = refused(library, design)
    assert any(reason in r for r in reasons), reasons


def test_the_paper_profile_turns_off_everything_added_since(tmp_path):
    config = replace(SimConfig(runs_dir=tmp_path), **PROFILES["paper"])
    assert config.mortality is False and config.materials is False


def test_the_viewer_gets_the_designs_with_the_world(tmp_path):
    config = SimConfig(seed=0, llm_base_url=None, runs_dir=tmp_path, embedder="bm25",
                       retrieval_threshold=0.0)
    with TestClient(create_app(config, live=False, speed=2.0, make_speech=None)) as client:
        world = client.get("/api/world").json()
    assert world["design_kinds"]["mill"] == "mill"
    assert world["designs"]["mill"]["movements"][0]["when"] == "worked"
    assert "plaster" in world["materials"]
