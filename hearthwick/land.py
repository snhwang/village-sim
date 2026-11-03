"""The land grows when the village is full (SPECIFICATION.md section 2.9h).

Houses, new fields and the places materials need each take a clear plot. A
village of 40 by 30 tiles filled in about two hundred days: its fields had
grown over the southwest, and houses stood in every gap. Scott decided on
2026-09-29 that the world should make room rather than stop. So when nothing
the crafters are about to start has a plot, the map gains a strip of open land
along its east edge, ``GROW_BY`` tiles wide, and the east road runs on to the
new edge. Nothing else changes. The forest and the stream stay where they
were, and the new ground is open grass, walkable at once.

It happens only where something is started (``Building.start``), so the land
grows because a house needs it, never on a guess. Read-only checks, such as
whether a crafter can start building, ask ``room``, which says yes whenever
the land could grow. Each growth is
logged as ``land_grown`` with the new width and the roads extended, so a
replay rebuilds the map as it was at every moment.
"""

from __future__ import annotations

GROW_BY = 10        # tiles of new land a growth adds, wide enough for any plot


class Land:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.grown = 0

    @property
    def able(self) -> bool:
        return self.sim.config.land

    def room(self, size: int) -> bool:
        """A plot this size can be had, now or once the land grows."""
        return self.able or self.sim.world.find_plot(size) is not None

    def plot(self, size: int, tick: int,
             near_kind: str = "home") -> tuple[int, int, int, int] | None:
        """A clear plot this size near places of ``near_kind`` (the houses,
        unless a quarry wants the forest), growing the land for one if there
        is none."""
        world = self.sim.world
        rect = world.find_plot(size, near_kind)
        if rect is None and self.able:
            self.grow(tick)
            rect = world.find_plot(size, near_kind)
        return rect

    def grow(self, tick: int) -> None:
        world = self.sim.world
        roads = world.extend_east(GROW_BY)
        self.grown += 1
        self.sim.log.event(tick, "land_grown", width=world.width, height=world.height,
                           by=GROW_BY, roads={k: list(v) for k, v in roads.items()})

    # -- checkpoints ------------------------------------------------------

    def to_dict(self) -> dict:
        world = self.sim.world
        return {"grown": self.grown, "width": world.width,
                "roads": {p.id: list(p.rect) for p in world.places.values() if p.kind == "road"}}

    def load(self, d: dict) -> None:
        if not d:
            return
        world = self.sim.world
        self.grown = d.get("grown", 0)
        world.width = d.get("width", world.width)
        for rid, rect in (d.get("roads") or {}).items():
            if rid in world.places:
                world.set_rect(rid, rect)
