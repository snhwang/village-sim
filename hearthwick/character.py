"""Villager state. Behavior is decided by the brain, not here."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hearthwick.genome import diploid, load_loci, phenotype
from hearthwick.growth import Growth
from hearthwick.world import Tile

# An infant is born in the village (hearthwick/family.py). No founder is one.
STAGES = ("infant", "child", "apprentice", "adult", "elder")
# The temperament genes, declared once in data/loci.yaml (hearthwick/genome.py).
LOCI = tuple(locus.name for locus in load_loci().loci)

# What a temperament sounds like when a persona is assembled from it, so a
# generated villager or a visitor reads as a person rather than a row in a table.
TRAIT_PHRASES = {
    "gregarious": "seeks out company", "reserved": "keeps to themselves",
    "bold": "is not easily frightened", "wary": "expects trouble",
    "inquisitive": "asks questions", "settled": "likes things as they are",
    "trusting": "takes people at their word", "suspicious": "wants to know who says so",
    "diligent": "works without being asked", "easygoing": "is never in a hurry",
    "plainspoken": "says it plainly", "embellishing": "improves a story in the telling",
}

# Tiles moved per tick, by stage.
SPEED = {"infant": 2, "child": 3, "apprentice": 3, "adult": 3, "elder": 2}


@dataclass
class Activity:
    """What a character is currently doing, resolved from one action marker."""

    kind: str  # go, wander, rest, work, talk, follow, play
    data: dict[str, Any] = field(default_factory=dict)
    ticks_left: int | None = None  # for timed activities
    instruction_id: str | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "data": self.data, "ticks_left": self.ticks_left,
                "instruction_id": self.instruction_id}


@dataclass
class Character:
    id: str
    name: str
    sex: str
    age: float  # in-game years
    stage: str
    role: str | None
    home: str
    parents: list[str]
    partner: str | None
    mentor: str | None
    temperament: dict[str, str]   # what the genotype expresses, one allele per gene
    persona: str
    genotype: dict[str, list[str]] = field(default_factory=dict)   # two copies per gene
    # A visitor comes from outside, stays a while and goes (hearthwick/visitors.py).
    # Once gone it is no longer alive in the village, though what it said and
    # what it heard stay in the record.
    visitor: bool = False
    leaves_at: int | None = None
    # The trade a villager learns or practises (hearthwick/trades.py). An
    # apprentice's is the one it chose on graduating, and an adult's is its role.
    trade: str | None = None
    # The day this villager and its partner last tried for a child
    # (hearthwick/family.py). A couple tries at most once a day.
    tried_for_child: int | None = None
    pos: Tile = (0, 0)
    energy: float = 1.0
    social: float = 0.3  # filled by conversation, drains over time
    alive: bool = True

    path: list[Tile] = field(default_factory=list)
    activity: Activity | None = None
    queue: deque[Activity] = field(default_factory=deque)
    conversation_id: str | None = None
    visited_today: set[str] = field(default_factory=set)
    avoiding: dict[str, int] = field(default_factory=dict)   # place -> tick it expires
    growth: Growth = field(default_factory=Growth)

    @property
    def idle(self) -> bool:
        return self.activity is None and not self.queue and self.conversation_id is None

    @property
    def resting(self) -> bool:
        return self.activity is not None and self.activity.kind == "rest"

    @property
    def activity_label(self) -> str:
        if self.conversation_id:
            return "talk"
        if self.activity is None:
            return "idle"
        if self.path and self.activity.kind not in ("go", "wander"):
            return "go"  # walking to where the activity happens
        return self.activity.kind

    def frame(self) -> list:
        """Compact per-tick record: id, x, y, activity, stage, age."""
        return [self.id, self.pos[0], self.pos[1], self.activity_label, self.stage, round(self.age, 2)]

    def profile(self) -> dict:
        return {
            "id": self.id, "name": self.name, "sex": self.sex, "stage": self.stage,
            "role": self.role, "home": self.home, "parents": self.parents,
            "partner": self.partner, "mentor": self.mentor,
            "temperament": self.temperament, "genotype": self.genotype,
            "persona": self.persona,
            "age": round(self.age, 2), "alive": self.alive,
            "visitor": self.visitor, "leaves_at": self.leaves_at, "trade": self.trade,
            "growth": self.growth.to_dict(),
        }


def from_profile(profile: dict) -> Character:
    """Someone who joined during a run, a visitor or a child born here, as a
    checkpoint recorded them. Founders come from their file instead."""
    return Character(
        id=profile["id"], name=profile["name"], sex=profile["sex"],
        age=float(profile["age"]), stage=profile["stage"], role=profile.get("role"),
        home=profile["home"], parents=list(profile.get("parents") or []),
        partner=profile.get("partner"), mentor=profile.get("mentor"),
        temperament=dict(profile["temperament"]), persona=profile["persona"],
        genotype={k: list(v) for k, v in (profile.get("genotype") or {}).items()},
        visitor=bool(profile.get("visitor")), leaves_at=profile.get("leaves_at"),
        trade=profile.get("trade"))


def load_founders(path: str | Path) -> list[Character]:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in spec["founders"]:
        if f["stage"] not in STAGES:
            raise ValueError(f"{f['id']}: unknown stage {f['stage']!r}")
        copies = {locus: list(pair) for locus, pair in (f.get("genotype") or {}).items()}
        missing = set(LOCI) - set(copies)
        if missing:
            raise ValueError(f"{f['id']}: genotype missing loci {sorted(missing)}")
        if any(len(pair) != 2 for pair in copies.values()):
            raise ValueError(f"{f['id']}: every gene needs two copies")
        # The temperament is what the two copies express, by BEAR's dominance.
        temperament = phenotype(diploid(copies, f["id"]))
        written = f.get("temperament")
        if written is not None and dict(written) != temperament:
            raise ValueError(f"{f['id']}: temperament {written} is not what its "
                             f"genotype expresses ({temperament})")
        out.append(Character(
            id=f["id"], name=f["name"], sex=f["sex"], age=float(f["age"]),
            stage=f["stage"], role=f.get("role"), home=f["home"],
            parents=list(f.get("parents") or []), partner=f.get("partner"),
            mentor=f.get("mentor"), temperament=temperament,
            persona=f["persona"].strip(), genotype=copies,
        ))
    return out
