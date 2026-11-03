"""Building: crafters fell timber and put up houses when a couple needs one.

Houses do not appear by themselves. A couple who marry and have nowhere of
their own wait in a family home (hearthwick/courtship.py), and while any
couple waits the village needs a house. The crafters see it:

    house_needed    a couple is waiting for a house
    building_site   a house has been started
    timber_short    there is not yet timber enough to finish it
    timber_ready    there is timber to build with

and their instructions do the rest. ``[!fell]`` sends a crafter to the forest
edge, where its work adds to the village's timber. ``[!build]`` lays out a
plot near the other houses if none is started, and otherwise sends it to the
site, where its work turns timber into a house. A house takes
``TIMBER_PER_HOUSE`` timber and ``WORK_PER_HOUSE`` ticks of work at the base
rate, and a skilled crafter does more in a tick (``trades.output_factor``).
When it is finished the site becomes a home, and the couple who have waited
longest move in with their young children.

Only crafters can do either, apprentices to a crafter included. Their skill is
their craft, practised at the mill, so the practice counts there wherever the
work is done, and an apprentice crafter can qualify by building.

With materials (SPECIFICATION.md section 2.9i) the village's stock is goods
of each kind, and the crafters see whatever the house going up is short of
(``timber_short``, ``stone_short``, ``clay_short``, ``iron_short``, and
``ore_short`` or ``ore_ready`` for the forge), and merchants what only the
road brings (``glass_short``, ``cloth_short``). A house is a cottage, which
takes timber alone, so in this edition timber is all it is ever short of: a
house of other goods was one built from a crafter's own drawing, which this
edition leaves out (README). ``timber_ready`` means there is enough of every
good to build with. Houses are the village's: nobody pays for them.
"""

from __future__ import annotations

from hearthwick.character import Character
from hearthwick.world import Place

TRADE = "crafter"
FOREST = "forest_edge"
FORGE = "forge"
SITE = "house_site"
TIMBER_PER_HOUSE = 30.0     # units of goods a cottage takes, all of it timber
WORK_PER_HOUSE = 180.0
TIMBER_PER_TICK = 0.5       # felled by one crafter in a tick, at the base rate
PLOT = 3                    # a house is a square this many tiles on a side
SMELT_UNIT = 0.25           # ore and timber a tick of smelting takes at the base rate


def is_builder(c: Character) -> bool:
    return (c.alive and not c.visitor and c.trade == TRADE
            and c.stage in ("apprentice", "adult", "elder"))


def is_merchant(c: Character) -> bool:
    return (c.alive and not c.visitor and c.role == "merchant"
            and c.stage in ("adult", "elder"))


class Building:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.stock: dict[str, float] = {}   # the village's goods, for what the crafters build
        self.needs: dict[str, float] | None = None   # what the house going up takes
        self.progress = 0.0         # work done on the house going up
        self.built = 0              # houses finished
        self.site: Place | None = None

    @property
    def timber(self) -> float:
        return self.stock.get("timber", 0.0)

    @timber.setter
    def timber(self, value: float) -> None:
        self.stock["timber"] = value

    # -- what a crafter sees ---------------------------------------------

    @property
    def needed(self) -> bool:
        return bool(self.sim.courtship.waiting)

    @property
    def busy(self) -> bool:
        """A house is needed, or going up."""
        return self.needed or self.site is not None

    # -- goods -------------------------------------------------------------

    def _materials(self):
        """The goods registry, while materials are on (hearthwick/goods.py)."""
        goods = getattr(self.sim, "goods", None)
        return goods if goods is not None and self.sim.config.materials else None

    @staticmethod
    def needs_of_a_house() -> dict[str, float]:
        """The goods a house takes: a cottage's timber."""
        return {"timber": TIMBER_PER_HOUSE}

    def _plan_now(self) -> tuple[dict[str, float], dict[str, float]]:
        """What the house going up, or the next, still takes, and the
        village's stock it is built from."""
        if self.site is not None:
            needs = self.needs or self.needs_of_a_house()
            done = min(1.0, self.progress / max(1e-9, WORK_PER_HOUSE))
        else:
            needs = self.needs_of_a_house()
            done = 0.0
        remaining = {g: a * (1.0 - done) for g, a in needs.items()}
        return remaining, self.stock

    def short(self, good: str) -> bool:
        remaining, source = self._plan_now()
        return source.get(good, 0.0) + 1e-9 < remaining.get(good, 0.0)

    @property
    def ready(self) -> bool:
        """Enough of every good to do some work with."""
        remaining, source = self._plan_now()
        return all(source.get(g, 0.0) + 1e-9 >= min(1.0, r) for g, r in remaining.items() if r > 1e-9)

    def _ore_for_iron(self) -> bool:
        return self.stock.get("ore", 0.0) >= SMELT_UNIT and self.timber >= SMELT_UNIT

    def timber_to_finish(self) -> float:
        return self._plan_now()[0].get("timber", 0.0)

    def tags(self, c: Character) -> list[str]:
        if not self.busy:
            return []
        if is_merchant(c) and not is_builder(c):
            goods = self._materials()
            return sorted(f"{g}_short" for g in self._plan_now()[0]
                          if goods is not None and goods.from_road(g) and self.short(g))
        if not is_builder(c):
            return []
        # A house still going up once nobody waits for it reads as a
        # project, as the paper's runs recorded it.
        out = ["house_needed"] if self.needed else ["project_needed"]
        if self.site is not None:
            out.append("building_site")
        remaining, _ = self._plan_now()
        for good in ("timber", "stone", "clay", "iron"):
            if good in remaining and self.short(good):
                out.append(f"{good}_short")
        if "iron" in remaining and self.short("iron"):
            out.append("ore_ready" if self._ore_for_iron() else "ore_short")
        if self.ready:
            out.append("timber_ready")
        return out

    # -- what can be done (read-only, for the handlers) ------------------

    def can_fell(self, c: Character) -> bool:
        return is_builder(c) and self.busy and self.short("timber")

    def can_gather(self, c: Character, good: str) -> bool:
        """A crafter cutting stone, digging clay or ore, or felling, for what
        is going up."""
        if not is_builder(c) or not self.busy:
            return False
        if good == "ore":
            return self.short("iron") and not self._ore_for_iron()
        return good in ("timber", "stone", "clay") and self.short(good)

    def can_smelt(self, c: Character) -> bool:
        return is_builder(c) and self.busy and self.short("iron") and self._ore_for_iron()

    def can_fetch(self, c: Character, good: str) -> bool:
        goods = self._materials()
        return (is_merchant(c) and self.busy and goods is not None and goods.from_road(good)
                and self.short(good))

    def can_build(self, c: Character) -> bool:
        if not is_builder(c) or not self.busy or not self.ready:
            return False
        return self.site is not None or self._room(PLOT)

    def _room(self, size: int) -> bool:
        land = getattr(self.sim, "land", None)
        return land.room(size) if land else self.sim.world.find_plot(size) is not None

    def _plot(self, size: int, tick: int) -> tuple[int, int, int, int] | None:
        """A clear plot, the land growing for one if the village is full
        (hearthwick/land.py)."""
        land = getattr(self.sim, "land", None)
        return land.plot(size, tick) if land else self.sim.world.find_plot(size)

    # -- carried out (in the simulation step) ----------------------------

    def start(self, c: Character, tick: int) -> str | None:
        """Lay out a plot for a house, if none is started. Returns the site."""
        if self.site is not None:
            return self.site.id
        rect = self._plot(PLOT, tick)
        if rect is None:
            return None
        self.site = Place(SITE, "the house going up", "site", rect)
        self.needs = self.needs_of_a_house()
        self.progress = 0.0
        self.sim.world.add_place(self.site)
        self.sim.log.event(tick, "place_added", place=self.site.to_dict(), by=c.id)
        return self.site.id

    def fell(self, c: Character, factor: float) -> None:
        self.timber += TIMBER_PER_TICK * factor

    def gather(self, good: str, amount: float) -> None:
        self.stock[good] = self.stock.get(good, 0.0) + amount

    def smelt(self, amount: float) -> float:
        """Ore and timber into iron at the forge, one for one, as far as they
        go and as much as is still short. Returns the iron made."""
        remaining, _ = self._plan_now()
        made = max(0.0, min(amount, self.stock.get("ore", 0.0), self.timber,
                            remaining.get("iron", 0.0) - self.stock.get("iron", 0.0)))
        if made > 0:
            self.stock["ore"] -= made
            self.timber -= made
            self.gather("iron", made)
        return made

    def work(self, c: Character, factor: float, tick: int) -> None:
        """One tick of a crafter's work at the site, as far as the goods go."""
        if self.site is None or not self.site.contains(*c.pos):
            return
        needs = self.needs or self.needs_of_a_house()
        _, source = self._plan_now()
        per_work = {g: a / WORK_PER_HOUSE for g, a in needs.items() if a > 0}
        done = min([factor, WORK_PER_HOUSE - self.progress]
                   + [source.get(g, 0.0) / p for g, p in per_work.items()])
        if done <= 0:
            return
        self.progress += done
        for g, p in per_work.items():
            source[g] = max(0.0, source.get(g, 0.0) - done * p)
        if self.progress >= WORK_PER_HOUSE - 1e-9:
            self._finish(tick)

    def _finish(self, tick: int) -> None:
        sim, site = self.sim, self.site
        self.built += 1
        n = 1 + max((int(p.id.split("_")[-1]) for p in sim.world.places.values()
                     if p.kind == "home" and p.id.split("_")[-1].isdigit()), default=0)
        home = Place(f"home_{n}", f"house {n}", "home", site.rect)
        sim.world.remove_place(site.id)
        sim.world.add_place(home)
        self.site, self.progress, self.needs = None, 0.0, None
        sim.log.event(tick, "place_removed", place=site.id)
        sim.log.event(tick, "place_added", place=home.to_dict())
        couple = sim.courtship.waiting[0] if sim.courtship.waiting else None
        if couple is not None:
            sim.courtship.settle(couple, home.id)
        sim.log.event(tick, "house_built", place=home.id,
                      couple=list(couple) if couple else None)
        sim.diffuser.witness("house", home.id, sim._nearest_witnesses(home.id),
                             {"topic": home.name}, tick)

    # -- for the viewer --------------------------------------------------

    def status(self) -> dict | None:
        """The house going up, as each frame reports it, so a viewer shows
        its progress between dawns and whoever opens the page mid-build sees
        it at once. None while no house is needed and none is going up.

        ``project``, ``queued``, ``unpaid`` and ``plan`` were a wanted thing
        and a crafter's drawing. This edition has neither, and they stay at
        their resting values so the frames read as the paper's runs wrote
        them."""
        if not self.busy:
            return None
        remaining, source = self._plan_now()
        return {"site": self.site.id if self.site else None,
                "goods": {g: [round(source.get(g, 0.0), 1), round(r, 1)]
                          for g, r in sorted(remaining.items())},
                "timber": round(self.timber, 1),
                "timber_needed": round(self.timber_to_finish(), 1),
                "work": round(self.progress, 1),
                "work_needed": round(WORK_PER_HOUSE, 1),
                "project": None, "queued": 0, "unpaid": 0, "plan": None,
                "waiting": [list(couple) for couple in self.sim.courtship.waiting]}

    # -- checkpoints -----------------------------------------------------

    def to_dict(self) -> dict:
        # The record of a building logged each dawn keeps the keys a design
        # and a wanted thing used (``plan``, ``factor``, ``queue``,
        # ``project``) at their resting values, as in status().
        return {"timber": self.timber, "stock": dict(self.stock), "needs": self.needs,
                "progress": self.progress,
                "built": self.built, "site": self.site.to_dict() if self.site else None,
                "plan": None, "factor": 1.0, "queue": [], "project": None}

    def load(self, d: dict) -> None:
        self.stock = dict(d.get("stock") or {"timber": d.get("timber", 0.0)})
        self.needs = d.get("needs")
        self.progress = d.get("progress", 0.0)
        self.built = d.get("built", 0)
        site = d.get("site")
        self.site = Place.from_dict(site) if site else None
