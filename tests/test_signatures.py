"""Consolidation shows the model each marker's arguments, and only the markers
a run can carry out (hearthwick/consolidation.py, found 2026-10-09)."""

from dataclasses import replace

from bear import Instruction, InstructionType

from hearthwick.__main__ import PROFILES
from hearthwick.config import SimConfig
from hearthwick.consolidation import LEFT_OUT_MARKERS, executable, offered_markers, signature


def _inst(content):
    return Instruction(id="learned-x-1", type=InstructionType.DIRECTIVE, priority=50,
                       content=content)


def test_a_marker_is_shown_with_the_arguments_its_handler_reads():
    assert signature("go", ["well"]) == "[!go(to=<a place: home, own, well>)] (to is required)"
    assert signature("wander") == "[!wander]"
    assert "place=<a place:" in signature("avoid", ["mill"])
    assert "target=<a villager's name" in signature("talk")


def test_the_paper_profile_offers_only_its_own_markers():
    paper = offered_markers(replace(SimConfig(), **PROFILES["paper"]))
    assert "go" in paper and "fell" in paper and "have_child" in paper
    for off in ("want", "search", "drive", "wear", "sell", "buy", "design", "gather",
                "fight_blight", "vacation", "swim", "fish"):
        assert off not in paper, off


def test_a_left_out_mechanic_is_never_offered_and_its_marker_is_refused():
    """The markers of the mechanics this edition leaves out (config.LEFT_OUT)
    are refused as the paper's runs refused them."""
    offered = offered_markers(replace(SimConfig(), **PROFILES["illustrative"]))
    assert not set(offered) & set(LEFT_OUT_MARKERS)
    ok, why = executable(_inst("Look it up. [!search(about=the blight)]"))
    assert not ok and why == "[!search] belongs to a mechanic this run has switched off"


def test_the_check_refuses_a_marker_of_a_switched_off_mechanic():
    ok, why = executable(_inst("Look it up. [!search(about=the blight)]"), offered={"go"})
    assert not ok and "switched off" in why
    ok, _ = executable(_inst("Go to the well. [!go(to=well)]"), offered={"go"})
    assert ok
