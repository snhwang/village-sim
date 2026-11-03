#!/usr/bin/env python3
"""Generate a village of any size.

Ten villagers is a hamlet, and it leaves too few peers — two farmers, two
children — to say much about whether villagers of the same kind behave
differently. This builds a larger one: households with couples and children,
roles spread across the trades, a temperament drawn from the allele library,
two copies of every gene that express it, and a house on the map for every
household.

Individuality here is compositional. Nobody hand-writes a personality: a
villager is a draw from the shared allele library plus a one-line persona
assembled from what it drew, which is exactly the claim the paper makes about
individuality costing an instruction rather than a branch.

    python experiments/make_village.py --villagers 30 --name greater
    python -m hearthwick run --days 10 --village greater

Writes data/villages/<name>/{village.yaml,founders.yaml}.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hearthwick.config import DATA_DIR  # noqa: E402
from hearthwick.character import TRAIT_PHRASES  # noqa: E402
from hearthwick.trades import TRADE_WEIGHTS  # noqa: E402
from hearthwick.genome import alleles, library, load_loci  # noqa: E402
from bear import Corpus  # noqa: E402

# Each gene's alleles, read from the temperament library in data/loci.yaml's
# gene order. A new allele written into the library becomes drawable here.
LOCI = alleles(Corpus.from_directory(DATA_DIR / "instructions" / "temperament"),
               load_loci())
# Each allele's dominance, as BEAR reads it: the metadata.dominance score
# on the allele's instructions (default 1.0).
DOMINANCE = {tag[len("temp_"):]: float(inst.metadata.get("dominance", 1.0))
             for inst in library() for tag in inst.scope.required_tags or ()
             if tag.startswith("temp_")}
# A farming village is mostly farmers, but it needs one of everything: the
# roles also decide where people spend their days, so a village with no healer
# has an empty shrine.
ROLE_WEIGHTS = TRADE_WEIGHTS   # hearthwick/trades.py, so graduates see the same shares

GIVEN_MALE = ["Bram", "Tobin", "Garrick", "Wynn", "Corin", "Hal", "Edek", "Merrick",
              "Osric", "Peder", "Sten", "Warin", "Dunn", "Fen", "Gorm", "Ivo"]
GIVEN_FEMALE = ["Hilde", "Rosa", "Ada", "Lise", "Nell", "Maren", "Bryn", "Edda",
                "Freya", "Gisla", "Ilsa", "Katrin", "Mabel", "Orla", "Sena", "Thea"]

# What a temperament sounds like in a persona (shared with visitors).
PHRASES = TRAIT_PHRASES
ROLE_PHRASE = {
    "farmer": "works the fields", "merchant": "keeps a stall at the market",
    "healer": "tends the sick at the shrine", "guard": "watches the east road",
    "crafter": "works at the mill", "storyteller": "tells the village its stories",
}


def temperament(rng: random.Random) -> dict[str, str]:
    return {locus: rng.choice(alleles) for locus, alleles in LOCI.items()}


def persona(name: str, stage: str, role: str | None, traits: dict[str, str],
            household: list[str]) -> str:
    bits = [f"{name}"]
    if role:
        bits.append(ROLE_PHRASE[role] + " and")
    bits.append(PHRASES[traits["sociability"]] + ",")
    bits.append(PHRASES[traits["diligence"]] + ",")
    bits.append("and " + PHRASES[traits["candor"]] + ".")
    line = " ".join(bits)
    if stage == "child":
        line = f"{name} is a child who {PHRASES[traits['curiosity']]} and {PHRASES[traits['caution']]}."
    elif stage == "elder":
        line += " Old enough to remember when things were done differently."
    if household:
        line += " Lives with " + ", ".join(household) + "."
    return line


def build(villagers: int, seed: int) -> tuple[list[dict], int]:
    """Households first, then the people in them, so families hold together."""
    rng = random.Random(seed)
    people: list[dict] = []
    households: list[list[dict]] = []
    used_names: set[str] = set()

    def name_for(sex: str) -> str:
        pool = GIVEN_MALE if sex == "male" else GIVEN_FEMALE
        free = [n for n in pool if n not in used_names]
        chosen = rng.choice(free) if free else f"{rng.choice(pool)}{len(used_names)}"
        used_names.add(chosen)
        return chosen

    while len(people) < villagers:
        house = f"home_{len(households) + 1}"
        members: list[dict] = []
        kind = rng.random()

        if kind < 0.60 and villagers - len(people) >= 2:          # a couple
            husband = {"sex": "male", "stage": "adult"}
            wife = {"sex": "female", "stage": "adult"}
            members += [husband, wife]
            for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
                if len(people) + len(members) >= villagers:
                    break
                members.append({"sex": rng.choice(["male", "female"]),
                                "stage": rng.choice(["child", "child", "apprentice"])})
        elif kind < 0.80:                                          # an elder alone
            members.append({"sex": rng.choice(["male", "female"]), "stage": "elder"})
            if rng.random() < 0.4 and len(people) + 1 < villagers:
                members.append({"sex": rng.choice(["male", "female"]),
                                "stage": rng.choice(["adult", "apprentice"])})
        else:                                                      # one adult
            members.append({"sex": rng.choice(["male", "female"]), "stage": "adult"})

        for m in members:
            m["home"] = house
            m["name"] = name_for(m["sex"])
            m["id"] = m["name"].lower()
            m["temperament"] = temperament(rng)
            m["age"] = {"child": rng.randint(2, 5), "apprentice": rng.randint(6, 8),
                        "adult": rng.randint(11, 22), "elder": rng.randint(24, 34)}[m["stage"]]
            m["role"] = None          # assigned once the village is complete
        households.append(members)
        people += members

    people = people[:villagers]

    # Roles: one of each first so no trade is missing, then by weight. A
    # village with no healer has an empty shrine, and a village of eleven
    # farmers has nobody on the road.
    working = [p for p in people if p["stage"] in ("adult", "elder")]
    rng.shuffle(working)
    roles = list(ROLE_WEIGHTS)
    pool = [r for r, w in ROLE_WEIGHTS.items() for _ in range(w)]
    for i, person in enumerate(working):
        person["role"] = roles[i] if i < len(roles) else rng.choice(pool)

    # families, mentors and the persona line, once everyone exists
    for household in households:
        adults = [m for m in household if m["stage"] in ("adult", "elder") and m in people]
        kids = [m for m in household if m["stage"] in ("child", "apprentice") and m in people]
        if len(adults) == 2 and adults[0]["stage"] == adults[1]["stage"] == "adult":
            adults[0]["partner"], adults[1]["partner"] = adults[1]["id"], adults[0]["id"]
        for kid in kids:
            kid["parents"] = [a["id"] for a in adults]

    healers = [p for p in people if p.get("role") == "healer"]
    for apprentice in [p for p in people if p["stage"] == "apprentice"]:
        mentors = [p for p in people if p.get("role")] or healers
        apprentice["mentor"] = rng.choice(mentors)["id"] if mentors else None

    # Genes have their own random stream, so adding them left every draw
    # above as it was.
    for who, locus, was, now in genotypes(people, random.Random(f"genes-{seed}")):
        print(f"  {who}: {locus} {was} -> {now}, which neither parent could pass on")

    for household in households:
        for m in household:
            if m in people:
                others = [o["name"] for o in household if o is not m and o in people]
                m["persona"] = persona(m["name"], m["stage"], m.get("role"),
                                       m["temperament"], others)

    return people, len(households)


def genotypes(people: list[dict], rng: random.Random) -> list[tuple]:
    """Two copies of every gene, consistent with each villager's temperament.

    A villager showing the recessive allele carries two copies of it, so each
    listed parent must carry it too. A villager showing the dominant allele
    carries it and a second copy. For someone with no listed parents that
    copy is drawn the way the first was, unless a descendant needs it to be
    recessive. Someone with listed parents gets one copy from each, drawn
    from the pairs that express their temperament, as Mendel would have it. A
    villager with one listed parent draws the other copy freely.

    A child whose two parents both show the recessive allele cannot show the
    dominant one. Such a child takes the recessive allele, and is returned so
    the change is visible.
    """
    by_id = {p["id"]: p for p in people}
    order: list[dict] = []               # parents before their children
    def place(p: dict) -> None:
        if p not in order:
            for i in p.get("parents") or ():
                place(by_id[i])
            order.append(p)
    for p in people:
        place(p)

    changed = []
    for locus, pair in LOCI.items():
        if len(pair) != 2 or DOMINANCE[pair[0]] == DOMINANCE[pair[1]]:
            raise ValueError(f"{locus}: needs two alleles of distinct dominance, has {pair}")
        dom, rec = sorted(pair, key=lambda a: -DOMINANCE[a])
        shows = lambda p: p["temperament"][locus]
        parents_of = lambda p: [by_id[i] for i in p.get("parents") or ()]

        for p in order:
            parents = parents_of(p)
            if shows(p) == dom and len(parents) == 2 and all(shows(q) == rec for q in parents):
                changed.append((p["id"], locus, dom, rec))
                p["temperament"][locus] = rec

        # Who must carry the recessive allele, worked up from the youngest.
        carrier = {p["id"] for p in people if shows(p) == rec}
        for p in reversed(order):
            parents = parents_of(p)
            if shows(p) == rec:
                carrier.update(q["id"] for q in parents)
            elif (p["id"] in carrier and len(parents) == 2
                  and not any(q["id"] in carrier for q in parents)):
                carrier.add(rng.choice(parents)["id"])

        for p in order:
            parents = parents_of(p)
            if not parents:
                p.setdefault("genotype", {})[locus] = (
                    [rec, rec] if shows(p) == rec
                    else [dom, rec if p["id"] in carrier else rng.choice(pair)])
                continue
            pools = [q["genotype"][locus] for q in parents]
            if len(pools) == 1:
                pools.append(list(pair))
            fits = [[x, y] for x in pools[0] for y in pools[1]
                    if (dom if dom in (x, y) else rec) == shows(p)
                    and (p["id"] not in carrier or rec in (x, y))]
            if not fits:
                raise ValueError(f"{p['id']}: no copies from {p['parents']} express "
                                 f"{locus} {shows(p)}")
            p.setdefault("genotype", {})[locus] = rng.choice(fits)
    return changed


def world_with_homes(base: Path, households: int, rng: random.Random) -> dict:
    """The base map, widened if need be, with a house per household."""
    spec = yaml.safe_load(base.read_text(encoding="utf-8"))
    spec["places"] = [p for p in spec["places"] if p["kind"] != "home"]

    # grow the map until there is room to place every house without overlap
    while True:
        taken = []
        for p in spec["places"]:
            x, y, w, h = p["rect"]
            taken.append((x - 1, y - 1, w + 2, h + 2))
        for b in spec.get("blocked", []):
            taken.append(tuple(b["rect"]))

        def free(x, y, w=3, h=3):
            if x < 1 or y < 1 or x + w >= spec["width"] or y + h >= spec["height"]:
                return False
            return not any(x < tx + tw and tx < x + w and y < ty + th and ty < y + h
                           for tx, ty, tw, th in taken)

        homes = []
        for i in range(households):
            for _ in range(600):
                x, y = rng.randrange(1, spec["width"] - 4), rng.randrange(1, spec["height"] - 4)
                if free(x, y):
                    homes.append({"id": f"home_{i + 1}", "name": f"house {i + 1}",
                                  "kind": "home", "rect": [x, y, 3, 3]})
                    taken.append((x - 1, y - 1, 5, 5))
                    break
            else:
                break
        if len(homes) == households:
            spec["places"] += homes
            return spec
        spec["width"] += 8
        spec["height"] += 6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villagers", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--name", default="greater")
    parser.add_argument("--base", default=str(DATA_DIR / "world" / "village.yaml"))
    args = parser.parse_args()

    people, households = build(args.villagers, args.seed)
    world = world_with_homes(Path(args.base), households, random.Random(args.seed))

    out = DATA_DIR / "villages" / args.name
    out.mkdir(parents=True, exist_ok=True)
    header = (f"# Generated by experiments/make_village.py "
              f"--villagers {args.villagers} --seed {args.seed}\n"
              f"# Nobody here is hand-written: each villager is a draw from the shared\n"
              f"# allele library plus a persona assembled from what it drew. genotype is\n"
              f"# two copies of every gene, and temperament is what they express.\n")
    (out / "village.yaml").write_text(header + yaml.safe_dump(world, sort_keys=False),
                                      encoding="utf-8")
    founders = []
    for p in people:
        founders.append({
            "id": p["id"], "name": p["name"], "sex": p["sex"], "age": p["age"],
            "stage": p["stage"], "role": p.get("role"), "home": p["home"],
            "parents": p.get("parents", []), "partner": p.get("partner"),
            "mentor": p.get("mentor"), "genotype": p["genotype"],
            "temperament": p["temperament"],
            "persona": p["persona"],
        })
    (out / "founders.yaml").write_text(header + yaml.safe_dump({"founders": founders},
                                                              sort_keys=False),
                                       encoding="utf-8")

    stages = {s: sum(1 for p in people if p["stage"] == s)
              for s in ("child", "apprentice", "adult", "elder")}
    roles = {}
    for p in people:
        if p.get("role"):
            roles[p["role"]] = roles.get(p["role"], 0) + 1
    print(f"{out}: {len(people)} villagers in {households} households")
    print(f"  stages {stages}")
    print(f"  roles  {roles}")
    print(f"  map    {world['width']}x{world['height']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
