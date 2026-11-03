"""Money: coins, goods to sell, and the merchant as the market
(SPECIFICATION-v0.2.md section 4.3, SPECIFICATION.md section 2.9i).

Each villager has a purse. When money begins, every villager then living has
``starting_coins``, and a child born later starts with none. Coins come from
selling. A tick of work at a place yields what is made there, whoever does it
(grain in the fields, flour at the mill, herbs at the shrine,
``data/goods.yaml``), and a villager may gather timber, stone, clay or ore for
itself. What it carries it
sells at the market, which is the merchant: set prices, less the merchants'
cut, which the living merchants share. What the market buys goes out along the
road, and what it sells comes in by it, so coins enter and leave the village.

Houses are the village's, built from what the crafters gather, and nobody
pays for them (Scott, 2026-09-30). ``[!sell]`` takes what a villager carries
to market, and ``carrying_goods`` says when there is enough to be worth the
walk. Coins bought a wanted thing, which this edition leaves out (README), so
here they only accumulate.

When a villager dies its coins and goods go to its partner, or else are shared
among its living children, or else go out along the road.
"""

from __future__ import annotations

from hearthwick import trades
from hearthwick.world import Place

MONEY_WANTERS = ("apprentice", "adult", "elder")


def _rounded(goods: dict[str, float]) -> dict[str, float]:
    return {g: round(a, 2) for g, a in sorted(goods.items()) if a > 0.005}


class Economy:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.purse: dict[str, float] = {}
        self.carried: dict[str, dict[str, float]] = {}
        self.funded = False

    # -- switches and data ----------------------------------------------

    @property
    def goods(self):
        return getattr(self.sim, "goods", None)

    @property
    def money(self) -> bool:
        return self.sim.config.money and self.goods is not None

    @property
    def materials(self) -> bool:
        return self.sim.config.materials and self.goods is not None

    def _market(self, key: str, default=None):
        return (self.goods.market if self.goods else {}).get(key, default)

    # -- set up (in the simulation step) ----------------------------------

    def ensure(self, tick: int) -> None:
        """At a run's start, and when a run takes money or materials up:
        purses for the villagers living, and the places materials need."""
        sim = self.sim
        if self.money and not self.funded:
            coins = float(self._market("starting_coins", 10))
            living = sorted(c.id for c in sim.characters.values() if c.alive and not c.visitor)
            for cid in living:
                self.purse.setdefault(cid, coins)
            self.funded = True
            sim.log.event(tick, "purses_opened", coins=coins, villagers=len(living))
        if self.materials:
            for pid, spec in self.goods.places.items():
                if pid in sim.world.places:
                    continue
                rect = sim.land.plot(spec.get("size", 3), tick, near_kind=spec.get("near", "home"))
                if rect is None:
                    continue
                place = Place(pid, spec.get("name", pid), pid, rect)
                sim.world.add_place(place)
                sim.log.event(tick, "place_added", place=place.to_dict(), by=None)

    # -- what a villager has and sees (read-only) --------------------------

    def coins(self, cid: str) -> float:
        return self.purse.get(cid, 0.0)

    def carrying(self, cid: str) -> dict[str, float]:
        return self.carried.get(cid, {})

    def worth(self, cid: str) -> float:
        return self.goods.value(self.carrying(cid)) if self.goods else 0.0

    def tags(self, c) -> list[str]:
        if not self.money or c.visitor or not c.alive or c.stage not in MONEY_WANTERS:
            return []
        out = []
        if self.worth(c.id) >= float(self._market("sell_at", 3.0)):
            out.append("carrying_goods")
        return out

    def can_gather(self, c) -> bool:
        return self.money and not c.visitor and c.alive and c.stage in MONEY_WANTERS

    def can_sell(self, c) -> bool:
        return (self.money and self.worth(c.id) > 0
                and self._market("place", "market") in self.sim.world.places)

    # -- carried out (in the simulation step) -----------------------------

    def worked(self, c, place_id: str, factor: float) -> None:
        """A tick of work at a place yields what is made there, whoever does
        it: grain in the fields, flour at the mill, herbs at the shrine."""
        if not self.money or c.visitor:
            return
        for good, rate in (self.goods.yields.get(place_id) or {}).items():
            self._add(c.id, good, rate * factor)

    def gathered(self, c, good: str) -> None:
        """A tick of gathering for oneself."""
        spec = self.goods.goods.get(good, {})
        self._add(c.id, good, float(spec.get("gather", 0.0)))

    def _add(self, cid: str, good: str, amount: float) -> None:
        held = self.carried.setdefault(cid, {})
        held[good] = held.get(good, 0.0) + amount

    def sell(self, c, tick: int) -> None:
        goods = _rounded(self.carried.pop(c.id, {}))
        value = self.goods.value(goods)
        if value <= 0:
            return
        cut = value * float(self._market("cut", 0.1))
        self.purse[c.id] = self.coins(c.id) + value - cut
        self._to_merchants(cut)
        self.sim.log.event(tick, "sold", character=c.id, goods=goods,
                           coins=round(value - cut, 2), cut=round(cut, 2))

    def _to_merchants(self, amount: float) -> None:
        """The merchants' cut, shared among those living. With none, it goes
        out along the road."""
        merchants = sorted(o.id for o in self.sim.characters.values()
                           if o.alive and not o.visitor and o.role == "merchant")
        for mid in merchants:
            self.purse[mid] = self.coins(mid) + amount / len(merchants)

    def died(self, c, tick: int) -> None:
        coins, goods = self.purse.pop(c.id, 0.0), self.carried.pop(c.id, {})
        if coins <= 0 and not goods:
            return
        chars = self.sim.characters
        partner = chars.get(c.partner) if c.partner else None
        heirs = ([partner.id] if partner is not None and partner.alive else
                 sorted(o.id for o in chars.values() if c.id in o.parents and o.alive and not o.visitor))
        for heir in heirs:
            self.purse[heir] = self.coins(heir) + coins / len(heirs)
            for g, a in goods.items():
                self._add(heir, g, a / len(heirs))
        self.sim.log.event(tick, "inherited", character=c.id, heirs=heirs, coins=round(coins, 2),
                           goods=_rounded(goods))

    # -- for the viewer and the record ------------------------------------

    def summary(self) -> dict[str, list[float]]:
        """Each villager's coins, and what its goods would fetch."""
        return {c.id: [round(self.coins(c.id), 1), round(self.worth(c.id), 1)]
                for c in self.sim.characters.values() if c.alive and not c.visitor}

    def to_dict(self) -> dict:
        return {"purse": dict(self.purse),
                "carried": {k: dict(v) for k, v in self.carried.items() if v},
                "funded": self.funded}

    def load(self, d: dict) -> None:
        self.purse = dict(d.get("purse") or {})
        self.carried = {k: dict(v) for k, v in (d.get("carried") or {}).items()}
        self.funded = d.get("funded", False)


def site_factor(c, world) -> float:
    """How much a tick of a villager's work does, by its skill at its site."""
    site = trades.site_of(c.trade or c.role, world)
    return trades.output_factor(trades.level_at(c, site)) if site else 1.0
