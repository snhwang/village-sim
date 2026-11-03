"""Instructions a villager wrote for itself, and the gates they must carry.

Consolidation is the only place the corpus grows. That makes it the only place
a villager can add something nobody reviewed, so what goes in has to be
constrained on the way: owned by one villager, executable, and honest about
when it applies.

The generation itself needs a model, and was first tried in isolation by a
probe (results/consolidation_probe.md). Everything here is the part that must
hold whatever the model returns.
"""

import pytest
from bear import Instruction, InstructionType, ScopeCondition, parse_actions

from hearthwick.consolidation import MAX_PRIORITY, VILLAGER_MARKERS, _own
from hearthwick.markers import build_registry


class Villager:
    """Only what _own reads."""

    def __init__(self, id="bryn", name="Bryn"):
        self.id = id
        self.name = name


def made(content, priority=50, required=None, tags=None) -> Instruction:
    return Instruction(
        id="learned-x", type=InstructionType.DIRECTIVE, priority=priority,
        content=content,
        scope=ScopeCondition(required_tags=list(required or []), tags=list(tags or [])),
    )


# --- ownership ------------------------------------------------------------

def test_a_learned_instruction_is_gated_on_its_owner():
    """Ungated, one child's lesson becomes village law."""
    out = _own(made("Keep away from the fields. [!avoid(place=fields)]"),
               Villager(), "apprentice")
    assert "char_bryn" in out.scope.required_tags


def test_a_second_owner_cannot_be_smuggled_in():
    """Whatever scope came back, it ends up owned by exactly one villager."""
    out = _own(made("Go to the mill. [!go(to=mill)]", required=["char_rosa"]),
               Villager(), "adult")
    owners = [t for t in out.scope.required_tags if t.startswith("char_")]
    assert owners == ["char_bryn"]


def test_ownership_is_recorded_in_metadata():
    out = _own(made("Rest. [!rest(ticks=4)]"), Villager(), "elder")
    assert out.metadata["layer"] == "learned"
    assert out.metadata["character"] == "bryn"
    assert out.metadata["learned_at_stage"] == "elder"


# --- when it applies ------------------------------------------------------

def test_something_that_moves_a_villager_is_held_to_daylight():
    """Villagers sleeping at night is not left to an embedder to decide."""
    out = _own(made("Go and see the fields. [!go(to=fields)]"), Villager(), "adult")
    assert "daytime" in out.scope.required_tags


def test_an_instruction_about_the_night_is_gated_on_the_night():
    """The blanket daylight gate made an instruction that could never fire.

    A villager told to go home and sleep, admitted only while the sun is up, is
    inert -- and an instruction that can never fire is worse than none, because
    nothing reports it.
    """
    out = _own(made("It is night and dark. Go home and sleep. "
                    "[!go(to=home)] [!rest(ticks=8)]"), Villager(), "adult")
    assert "time_night" in out.scope.required_tags
    assert "daytime" not in out.scope.required_tags


def test_an_instruction_that_moves_nobody_needs_no_time_gate():
    out = _own(made("Keep away from the well. [!avoid(place=well)]"),
               Villager(), "adult")
    assert "daytime" not in out.scope.required_tags
    assert "time_night" not in out.scope.required_tags


# --- it may not outrank what was authored ---------------------------------

@pytest.mark.parametrize("given", (10, 40, 55, 99))
def test_a_learned_instruction_never_outranks_an_authored_one(given):
    """Authored instructions run 44 to 74. What a villager worked out for
    itself competes with the life-stage protocols rather than overruling them."""
    out = _own(made("Go to the mill. [!go(to=mill)]", priority=given),
               Villager(), "adult")
    assert out.priority <= MAX_PRIORITY


# --- it must be executable ------------------------------------------------

def test_the_marker_vocabulary_is_what_the_registry_implements():
    """A marker outside this set is dropped at dispatch, so an instruction
    carrying one is an instruction that does nothing."""
    assert set(VILLAGER_MARKERS) == {"go", "wander", "rest", "work", "clear", "talk",
                                     "avoid", "warn", "follow", "play", "depart", "apprentice",
                                     "have_child", "propose", "accept_proposal",
                                     "decline_proposal", "fell", "build", "gather", "save",
                                     "smelt", "fetch", "sell", "buy", "fight_blight"}
    assert set(VILLAGER_MARKERS) == set(build_registry()._handlers)


def test_gating_leaves_the_markers_alone():
    content = "Keep away and warn them. [!avoid(place=well)] [!warn(target=nearby)]"
    out = _own(made(content), Villager(), "adult")
    assert {m.name for m in parse_actions(out.content)} == {"avoid", "warn"}


# --- a marker with the wrong argument is inert, not an error --------------

@pytest.mark.parametrize("content,ok", [
    ("Keep away from the well. [!avoid(place=well)]", True),
    ("Get on with it. [!work(site=own, ticks=18)]", True),
    ("Go to the mill. [!go(to=mill)]", True),
    ("Rest a while. [!rest(ticks=6)]", True),
    ("Wander a bit. [!wander]", True),
    # Names the registry knows, arguments no handler reads. These resolve to
    # nothing, so the instruction is passed over every time it is retrieved.
    ("Do not repeat it. [!avoid(target=Mabel, topic=well)]", False),
    ("Check the stores. [!work(place=fields)]", False),
    ("Go somewhere. [!go(place=mill)]", False),
    # Not a marker this village implements at all.
    ("Do a thing. [!dance(with=Rosa)]", False),
    # Prose a villager cannot act on.
    ("You feel uneasy about the well.", False),
])
def test_only_instructions_that_can_actually_fire_are_kept(content, ok):
    """Two of the six the first rehearsal produced were inert.

    They carried valid marker names with arguments no handler reads, so they
    would have been retrieved, silently passed over at dispatch, and counted as
    a successful consolidation.
    """
    from hearthwick.consolidation import executable

    passed, why = executable(made(content))
    assert passed is ok, why or "should have been refused"


# --- a place that does not exist is inert too ----------------------------

PLACES = {"well", "inn", "mill", "fields", "east_road", "home_3", "watchpost"}


@pytest.mark.parametrize("content,ok", [
    ("Keep away from the well. [!avoid(place=well)]", True),
    ("Go home. [!go(to=home)]", True),
    ("Visit someone. [!go(to=random_home)]", True),
    ("Go to the inn. [!go(to=inn)]", True),
    ("Go to house 3. [!go(to=home_3)]", True),
    # Argument names the handlers read, values that are not places here.
    ("Stay in. [!avoid(place=outside)] [!rest(ticks=8)]", False),
    ("Go to house 3. [!go(to=house_3)]", False),
    ("Go to the square. [!go(to=village_center)]", False),
    ("Check the grain. [!work(site=granary)]", False),
])
def test_a_place_that_does_not_exist_is_refused(content, ok):
    """The thirty-day rehearsal wrote avoid(place=outside). The avoid part never
    fired, and nothing said so, because the name of the argument was right."""
    from hearthwick.consolidation import executable

    passed, why = executable(made(content), places=PLACES)
    assert passed is ok, why or "should have been refused"


PEOPLE = {"edek", "sena", "osric", "hilde28"}


@pytest.mark.parametrize("content,ok", [
    ("Tell someone. [!warn(target=nearby, topic=blight)]", True),
    ("Talk to Osric. [!talk(target=osric)]", True),
    ("Play with a child. [!play(target=nearby_child)]", True),
    ("Talk to the traveler. [!talk(target=traveler)]", False),
    ("Follow the miller. [!follow(target=miller)]", False),
])
def test_a_villager_who_does_not_exist_is_refused(content, ok):
    from hearthwick.consolidation import executable

    passed, why = executable(made(content), places=PLACES, people=PEOPLE)
    assert passed is ok, why or "should have been refused"


def test_a_name_is_written_as_the_id_it_resolves_to():
    """talk(target=Edek) never fired, because ids are lowercase."""
    from hearthwick.consolidation import executable, named_as_ids

    fixed = named_as_ids(made("Go and see Edek. [!talk(target=Edek, topic=the well)] "
                              "[!warn(target=Nobody)]"), PEOPLE)
    assert "target=edek" in fixed.content
    assert "target=Nobody" in fixed.content  # not someone, so left alone
    assert executable(named_as_ids(made("[!talk(target=Sena)]"), PEOPLE),
                      places=PLACES, people=PEOPLE) == (True, "")


# --- a lesson set somewhere applies there ---------------------------------

NAMES = {"well": "the well", "inn": "the Wick & Kettle inn", "fields": "the fields",
         "east_road": "the east road", "home_8": "house 8", "home_13": "house 13"}


@pytest.mark.parametrize("content,hard,soft", [
    # The rehearsal's inn lesson, used 24 of 25 times at home.
    ("You are at the Wick & Kettle inn with Peder and Ilsa. Listen to their "
     "accounts of the blight. [!talk(target=nearby)]", {"at_inn"}, set()),
    ("While at the well, tell people the water is bad. [!warn(target=nearby)]",
     {"at_well"}, set()),
    # Scene-setting is a preference, not a condition.
    ("A storm broke over the village. Stay at the Wick & Kettle inn. [!rest(ticks=8)]",
     set(), {"at_inn"}),
    ("The whole village gathered at the well tonight. Warn them. [!warn(target=nearby)]",
     set(), {"at_well"}),
    # Where a marker sends the villager is neither. Keeping away from the
    # fields must apply wherever the villager is.
    ("A blight is on the crop at the fields. Do not go near the fields. "
     "[!avoid(place=fields)]", set(), set()),
    ("Go home and rest. [!go(to=home)]", set(), set()),
])
def test_a_lesson_is_tied_to_where_it_is_set(content, hard, soft):
    out = _own(made(content), Villager(), "adult", NAMES)
    required = {t for t in out.scope.required_tags if t.startswith("at_")}
    preferred = {t for t in out.scope.tags if t.startswith("at_")}
    assert required == hard
    assert preferred == soft


def test_a_place_is_written_as_the_id_it_resolves_to():
    """go(to=house_13) never fired. The place is called house 13, its id is home_13."""
    from hearthwick.consolidation import executable, named_as_ids

    fixed = named_as_ids(made("See Edek. [!go(to=house_13)] [!talk(target=Edek)] "
                              "[!avoid(place=the well)] [!go(to=village)]"),
                         {"edek"}, NAMES)
    assert "go(to=home_13)" in fixed.content
    assert "avoid(place=well)" in fixed.content
    assert "go(to=village)" in fixed.content  # nowhere, so left alone
    assert executable(named_as_ids(made("[!go(to=house_13)] [!talk(target=Edek)]"),
                                   {"edek"}, NAMES),
                      places=set(NAMES), people={"edek"}) == (True, "")


@pytest.mark.parametrize("content,ok", [
    # Positional arguments are what the handlers read first.
    ("Keep away from the well. [!avoid(well)]", True),
    ("Tell someone. [!warn(nearby, the well is bad)]", True),
    ("Keep away. [!avoid(outside)]", False),
    # A handler that cannot act without its argument.
    ("Go to the mill and inspect the stock. [!go(to=mill)] [!work(ticks=2)]", False),
    ("Talk it over. [!talk(topic=the blight)]", False),
    ("Rest a while. [!rest(ticks=4)]", True),
    ("Walk about. [!wander]", True),
])
def test_positional_and_missing_arguments(content, ok):
    from hearthwick.consolidation import executable

    passed, why = executable(made(content), places=PLACES, people=PEOPLE)
    assert passed is ok, why or "should have been refused"


def test_every_authored_instruction_passes_the_same_check():
    """Rule 12 applies to what we write, not only to what the model writes.

    The first time this ran it found two authored faults. A crafter who knew
    the grain had spoiled walked to the mill and never worked there, because
    [!work(ticks=6)] names no site. A warning about the blight passed on
    "something you should know", because it said about= where the handler
    reads topic=.
    """
    import glob

    import yaml

    from pathlib import Path

    from hearthwick.config import DATA_DIR, LEFT_OUT
    from hearthwick.consolidation import executable
    from hearthwick.corpus import SWITCHED_DIRS

    village = yaml.safe_load((DATA_DIR / "villages" / "greater" / "village.yaml")
                             .read_text(encoding="utf-8"))
    places = {p["id"] for p in village["places"]}
    # And the places materials add to it, the quarry, the clay pit and the
    # forge (data/goods.yaml).
    goods = yaml.safe_load((DATA_DIR / "goods.yaml").read_text(encoding="utf-8"))
    places |= set(goods.get("places") or {})
    # A left-out mechanic's folder is never loaded, and keeps only what the
    # gene library reads (hearthwick/corpus.py).
    never = {d for d, switch in SWITCHED_DIRS.items() if switch in LEFT_OUT}
    failures = []
    for path in glob.glob(str(DATA_DIR / "instructions" / "**" / "*.yaml"), recursive=True):
        if "world" in path:
            continue  # the world's markers are a different registry
        if Path(path).relative_to(DATA_DIR / "instructions").parts[0] in never:
            continue
        data = yaml.safe_load(open(path, encoding="utf-8"))
        for item in data if isinstance(data, list) else data.get("instructions", []):
            if not parse_actions(item["content"]):
                continue
            ok, why = executable(made(item["content"]), places=places)
            if not ok:
                failures.append(f"{item['id']}: {why}")
    assert not failures, "\n".join(failures)
