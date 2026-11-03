"""Structures as data: the designs the 3D viewer draws the village from.

Every building in the 3D viewer used to be code, one function per kind of
place. A design is data instead. It is parts (shapes with a size, a
position, a material, a parent), joints (how a part moves against its
parent), movements (what a joint does) and the triggers that set them going
(SPECIFICATION-v0.2.md section 1). The viewer draws a design and runs its
movements.

What a design may contain is ``data/structures/vocabulary.yaml``, and
:func:`validate` refuses anything else, with a reason for each refusal. The
founders' designs (``data/structures/designs``) are one for each kind of place
that has one. Designs drawn by villagers, and frames that say which of a
place's triggers hold, are left out of this edition (README). Here the
designs are only what the viewer draws, and a movement that waits on a
place's trigger stays still.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VOCABULARY = Path("structures") / "vocabulary.yaml"
DESIGNS = Path("structures") / "designs"
MATERIALS = Path("materials.yaml")


@dataclass
class Library:
    """Every design the village knows, and which kind of place each is for."""

    vocabulary: dict
    materials: dict[str, dict]
    designs: dict[str, dict] = field(default_factory=dict)     # id -> design
    kinds: dict[str, str] = field(default_factory=dict)        # place kind -> design id

    @classmethod
    def load(cls, data_dir: Path) -> "Library":
        data_dir = Path(data_dir)
        vocabulary = yaml.safe_load((data_dir / VOCABULARY).read_text(encoding="utf-8"))
        materials = yaml.safe_load((data_dir / MATERIALS).read_text(encoding="utf-8"))["materials"]
        library = cls(vocabulary, materials)
        for path in sorted((data_dir / DESIGNS).glob("*.yaml")):
            design = yaml.safe_load(path.read_text(encoding="utf-8"))
            reasons = validate(design, vocabulary, materials)
            if reasons:
                raise ValueError(f"{path.name} is not a valid design: {'; '.join(reasons)}")
            library.designs[path.stem] = design
            if design.get("default_for"):
                library.kinds[design["default_for"]] = path.stem
        return library

    def for_place(self, place) -> dict | None:
        design_id = self.kinds.get(place.kind)
        return self.designs.get(design_id) if design_id else None

    def payload(self) -> dict:
        """What the viewer needs to draw and run every design."""
        return {"designs": self.designs, "design_kinds": self.kinds,
                "materials": self.materials}


# --- the validator ---------------------------------------------------------

def _numbers(value, count: int | None = None) -> bool:
    return (isinstance(value, list) and (count is None or len(value) == count)
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value))


def validate(design: dict, vocabulary: dict, materials: dict) -> list[str]:
    """Why a design cannot exist, or nothing if it can.

    A design written by the model can be anything at all, so whatever is too
    malformed to check is refused rather than raising.
    """
    try:
        return _validate(design, vocabulary, materials)
    except (TypeError, AttributeError, KeyError, ValueError) as exc:
        return [f"it could not be read as a design ({type(exc).__name__})"]


def _named(value) -> bool:
    return isinstance(value, str) and bool(value)


def _validate(design: dict, vocabulary: dict, materials: dict) -> list[str]:
    """The checks themselves.

    Checks that everything in it is in the vocabulary, that it keeps within
    the limits, that every parent exists and none is its own ancestor, that
    every material is known, and that every movement names a joint of the
    kind it needs and a trigger the world has. Whether its footprint fits a
    plot is checked when it is placed, and whether it works, on the bench.
    """
    reasons: list[str] = []
    limits = vocabulary["limits"]
    shapes = vocabulary["shapes"]
    if not isinstance(design, dict):
        return ["a design is a mapping"]
    if not design.get("design"):
        reasons.append("it has no name")
    parts = design.get("parts")
    if not isinstance(parts, list) or not parts:
        return reasons + ["it has no parts"]

    footprint = design.get("footprint")
    if footprint is not None and not (_numbers(footprint, 2)
                                      and all(1 <= v <= limits["footprint"] for v in footprint)):
        reasons.append(f"its footprint must be two sizes from 1 to {limits['footprint']}")
    for key in ("joints", "movements"):
        value = design.get(key)
        if value is not None and not (isinstance(value, list) and all(isinstance(v, dict) for v in value)):
            return reasons + [f"its {key} must be a list of entries"]
    if design.get("claims") is not None and not (isinstance(design["claims"], list)
                                                 and all(_named(c) for c in design["claims"])):
        return reasons + ["its claims must be a list of words"]
    if design.get("ground") is not None and not (_named(design["ground"]) and design["ground"] in materials):
        reasons.append(f"its ground, {design['ground']}, is not a known material")

    ids: dict[str, dict] = {}
    for i, part in enumerate(parts):
        pid = part.get("id") if isinstance(part, dict) else None
        if not pid or not isinstance(pid, str):
            reasons.append(f"part {i + 1} has no id")
            continue
        if pid in ids:
            reasons.append(f"two parts are called {pid}")
        ids[pid] = part
        shape = part.get("shape")
        if not _named(shape) or shape not in shapes:
            reasons.append(f"{pid} is a {shape}, which is not a shape")
        else:
            size = part.get("size")
            counts = {len(form) for form in shapes[shape]}
            if not (_numbers(size) and len(size) in counts and all(v > 0 for v in size)):
                reasons.append(f"{pid} needs a size of {' or '.join(map(str, sorted(counts)))} positive numbers")
        if not _named(part.get("material")) or part["material"] not in materials:
            reasons.append(f"{pid} is made of {part.get('material')}, which is not a known material")
        for key in ("at", "rotation"):
            if key in part and not _numbers(part[key], 3):
                reasons.append(f"{pid}'s {key} must be three numbers")
        if "scale" in part and not (_numbers(part["scale"], 3) and all(v > 0 for v in part["scale"])):
            reasons.append(f"{pid}'s scale must be three positive numbers")
        if "sides" in part and not (isinstance(part["sides"], int) and 3 <= part["sides"] <= limits["sides"]):
            reasons.append(f"{pid} must have from 3 to {limits['sides']} sides")
        if part.get("open") and shape != "cylinder":
            reasons.append(f"only a cylinder can be open, and {pid} is a {shape}")
        repeat = _repeat(part)
        if repeat is None or not 1 <= repeat[0] <= limits["repeat"]:
            reasons.append(f"{pid} can repeat from 1 to {limits['repeat']} times")

    tree_sound = True
    for pid, part in ids.items():
        seen, parent = {pid}, part.get("parent")
        while parent is not None:
            if parent not in ids:
                reasons.append(f"{pid}'s parent, {parent}, is not a part")
                tree_sound = False
                break
            if parent in seen:
                reasons.append(f"{pid} is its own ancestor")
                tree_sound = False
                break
            seen.add(parent)
            parent = ids[parent].get("parent")

    # Counting copies and height walks up through parents, so it waits until
    # the parts form a tree. A loop of parents would otherwise never end.
    if tree_sound:
        copies = sum(_copies(pid, ids) for pid in ids)
        if copies > limits["parts"]:
            reasons.append(f"it has {copies} parts counting repeats, and the most is {limits['parts']}")
        top = max((_top(pid, ids) for pid in ids), default=0)
        if top > limits["height"]:
            reasons.append(f"it stands {top:.1f} high, and the most is {limits['height']}")

    joints: dict[str, dict] = {}
    for joint in design.get("joints") or []:
        part = joint.get("part")
        if part not in ids:
            reasons.append(f"a joint is on {part}, which is not a part")
            continue
        if part in joints:
            reasons.append(f"{part} has two joints")
        joints[part] = joint
        if "pivot" in joint and not _numbers(joint["pivot"], 3):
            reasons.append(f"{part}'s joint pivot must be three numbers")
        if joint.get("kind") not in vocabulary["joints"]:
            reasons.append(f"{part}'s joint is a {joint.get('kind')}, which is not a joint")
        elif joint["kind"] != "fixed" and joint.get("axis") not in vocabulary["axes"]:
            reasons.append(f"{part}'s joint needs an axis, x, y or z")

    triggers = set(vocabulary["triggers"]["world"]) | set(vocabulary["triggers"]["place"])
    kinds = vocabulary["movements"]
    for movement in design.get("movements") or []:
        joint = joints.get(movement.get("joint"))
        which = [k for k in kinds if k in movement]
        if joint is None:
            reasons.append(f"a movement is on {movement.get('joint')}, which has no joint")
            continue
        if len(which) != 1:
            reasons.append(f"a movement of {movement['joint']} must be one of {', '.join(kinds)}")
            continue
        kind = which[0]
        needs = kinds[kind] if isinstance(kinds[kind], list) else [kinds[kind]]
        if joint.get("kind") not in needs:
            reasons.append(f"{kind} needs a {' or '.join(needs)}, and {movement['joint']}'s joint is a {joint.get('kind')}")
        if movement.get("when", "always") not in triggers:
            reasons.append(f"{movement['joint']} moves when {movement.get('when')}, which the world does not know")
        value = movement[kind]
        if kind == "spin" and not (isinstance(value, (int, float)) and abs(value) <= limits["spin"]):
            reasons.append(f"{movement['joint']} can spin at most {limits['spin']} turns a minute")
        if kind in ("swing", "slide"):
            if not _numbers(value, 2) or not isinstance(movement.get("period"), (int, float)) or movement["period"] <= 0:
                reasons.append(f"{kind} needs two values, from and to, and a \"period\" in seconds")
            elif kind == "slide" and max(abs(v) for v in value) > limits["slide"]:
                reasons.append(f"{movement['joint']} can slide at most {limits['slide']}")
        if kind == "open" and (not isinstance(value, (int, float))
                               or not isinstance(movement.get("seconds"), (int, float))
                               or movement["seconds"] <= 0):
            reasons.append("open needs an angle or a distance, and seconds")

    unknown = set(design.get("claims") or []) - set(vocabulary["claims"])
    if unknown:
        reasons.append(f"it claims {', '.join(sorted(unknown))}, which the bench cannot test")
    return reasons


def _repeat(part: dict) -> tuple[int, str | None] | None:
    repeat = part.get("repeat", 1)
    if isinstance(repeat, int) and not isinstance(repeat, bool):
        return repeat, None
    if isinstance(repeat, dict) and isinstance(repeat.get("count"), int):
        return repeat["count"], repeat.get("axis")
    return None


def _copies(pid: str, ids: dict[str, dict]) -> int:
    """How many of a part are drawn: its own repeats times its ancestors'."""
    n, part = 1, ids[pid]
    while part is not None:
        n *= (_repeat(part) or (1, None))[0]
        part = ids.get(part.get("parent"))
    return n


def _top(pid: str, ids: dict[str, dict]) -> float:
    """Roughly how high a part reaches: its and its ancestors' heights above
    their parents, and half its own extent. Rotations are ignored, so a part
    lying down counts as standing, which only errs on the high side."""
    part = ids[pid]
    size = part.get("size") or [0]
    reach = max(size) if _numbers(size) else 0
    y, node = 0.0, part
    while node is not None:
        at = node.get("at") or [0, 0, 0]
        y += at[1] if _numbers(at, 3) else 0
        node = ids.get(node.get("parent"))
    return y + reach / 2
