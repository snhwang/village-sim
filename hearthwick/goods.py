"""Goods: what things are built of, where each comes from, and its price
(SPECIFICATION-v0.2.md section 4.2, SPECIFICATION.md section 2.9i).

The registry is data (``data/goods.yaml``): the goods, what a tick of work
at each place yields, the market's prices and cut, and the places materials
need.
"""

from __future__ import annotations

from pathlib import Path

import yaml

GOODS = "goods.yaml"


class Goods:
    def __init__(self, spec: dict) -> None:
        self.goods: dict[str, dict] = spec.get("goods") or {}
        self.yields: dict[str, dict[str, float]] = spec.get("yields") or {}
        self.market: dict = spec.get("market") or {}
        self.places: dict[str, dict] = spec.get("places") or {}

    @classmethod
    def load(cls, data_dir: Path) -> "Goods":
        return cls(yaml.safe_load((Path(data_dir) / GOODS).read_text(encoding="utf-8")))

    def price(self, good: str) -> float:
        return float(self.goods.get(good, {}).get("price", 0.0))

    def value(self, amounts: dict[str, float]) -> float:
        return sum(self.price(g) * a for g, a in amounts.items())

    def source(self, good: str) -> str | None:
        """The place a good is gathered at, if it is gathered."""
        return self.goods.get(good, {}).get("from")

    def gatherable(self) -> list[str]:
        return [g for g, spec in self.goods.items() if spec.get("from")]

    def from_road(self, good: str) -> bool:
        return bool(self.goods.get(good, {}).get("road"))
