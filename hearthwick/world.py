"""The village map, places, pathfinding and the in-game clock."""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

Tile = tuple[int, int]
SEASONS = ("spring", "summer", "autumn", "winter")


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    kind: str
    rect: tuple[int, int, int, int]  # x, y, w, h

    def contains(self, x: int, y: int) -> bool:
        rx, ry, rw, rh = self.rect
        return rx <= x < rx + rw and ry <= y < ry + rh

    def tiles(self) -> list[Tile]:
        rx, ry, rw, rh = self.rect
        return [(x, y) for y in range(ry, ry + rh) for x in range(rx, rx + rw)]

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "rect": list(self.rect)}

    @classmethod
    def from_dict(cls, d: dict) -> "Place":
        return cls(d["id"], d["name"], d["kind"], tuple(d["rect"]))


@dataclass
class World:
    width: int
    height: int
    places: dict[str, Place]
    blocked: list[dict]
    role_sites: dict[str, str]
    _blocked_tiles: set[Tile] = field(default_factory=set, repr=False)
    _place_at: dict[Tile, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for b in self.blocked:
            x, y, w, h = b["rect"]
            self._blocked_tiles.update((i, j) for j in range(y, y + h) for i in range(x, x + w))
        for place in self.places.values():
            for t in place.tiles():
                self._place_at[t] = place.id

    @classmethod
    def from_yaml(cls, path: str | Path) -> World:
        spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        places = {
            p["id"]: Place(id=p["id"], name=p["name"], kind=p["kind"], rect=tuple(p["rect"]))
            for p in spec["places"]
        }
        return cls(
            width=spec["width"],
            height=spec["height"],
            places=places,
            blocked=spec.get("blocked", []),
            role_sites=spec.get("role_sites", {}),
        )

    def in_bounds(self, t: Tile) -> bool:
        return 0 <= t[0] < self.width and 0 <= t[1] < self.height

    def walkable(self, t: Tile) -> bool:
        return self.in_bounds(t) and t not in self._blocked_tiles

    def name_of(self, place_id: str | None, default: str = "the village") -> str:
        """A place's name, or ``default`` for none, or for one that is gone. A
        building site is removed when what stands on it is finished, and a
        conversation held there, or a walk begun toward it, can outlast it."""
        place = self.places.get(place_id) if place_id else None
        return place.name if place else default

    def place_at(self, t: Tile) -> Place | None:
        pid = self._place_at.get(t)
        return self.places[pid] if pid else None

    def places_of_kind(self, kind: str) -> list[Place]:
        return [p for p in self.places.values() if p.kind == kind]

    def random_tile_in(self, place_id: str, rng: random.Random) -> Tile:
        tiles = [t for t in self.places[place_id].tiles() if self.walkable(t)]
        return rng.choice(tiles)

    def random_walkable_tile(self, rng: random.Random) -> Tile:
        while True:
            t = (rng.randrange(self.width), rng.randrange(self.height))
            if self.walkable(t):
                return t

    def path(self, start: Tile, goal: Tile) -> list[Tile]:
        """Shortest 8-connected path from start to goal, excluding start.

        Returns an empty list when start == goal or the goal is unreachable.
        """
        if start == goal or not self.walkable(goal):
            return []
        frontier: list[tuple[float, Tile]] = [(0.0, start)]
        came_from: dict[Tile, Tile | None] = {start: None}
        cost: dict[Tile, float] = {start: 0.0}
        while frontier:
            _, cur = heapq.heappop(frontier)
            if cur == goal:
                break
            cx, cy = cur
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nxt = (cx + dx, cy + dy)
                    if not self.walkable(nxt):
                        continue
                    # No corner cutting past blocked tiles (stream banks).
                    if dx and dy and not (self.walkable((cx + dx, cy)) and self.walkable((cx, cy + dy))):
                        continue
                    new_cost = cost[cur] + (1.4142 if dx and dy else 1.0)
                    if nxt not in cost or new_cost < cost[nxt]:
                        cost[nxt] = new_cost
                        h = max(abs(goal[0] - nxt[0]), abs(goal[1] - nxt[1]))
                        heapq.heappush(frontier, (new_cost + h, nxt))
                        came_from[nxt] = cur
        if goal not in came_from:
            return []
        out: list[Tile] = []
        node: Tile | None = goal
        while node is not None and node != start:
            out.append(node)
            node = came_from[node]
        out.reverse()
        return out

    def _strip(self, place: Place, side: str) -> tuple[tuple[int, int, int, int], list[Tile]]:
        x, y, w, h = place.rect
        rect = {"up": (x, y - 1, w, h + 1), "left": (x - 1, y, w + 1, h),
                "down": (x, y, w, h + 1), "right": (x, y, w + 1, h)}[side]
        new = [t for t in Place(place.id, place.name, place.kind, rect).tiles()
               if not place.contains(*t)]
        return rect, new

    def growth(self, place_id: str) -> tuple[int, int, int, int] | None:
        """The place one strip larger, or None when there is no room.

        A strip must be on the map, dry, and clear of every other place by a
        tile, so a field never swallows a house or a road. Sides are tried in
        a fixed order, so the same village grows the same way.
        """
        place = self.places[place_id]
        for side in ("up", "left", "down", "right"):
            rect, new = self._strip(place, side)
            ok = all(self.walkable(t) for t in new)
            for tx, ty in new if ok else ():
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        other = self._place_at.get((tx + dx, ty + dy))
                        if other and other != place_id:
                            ok = False
            if ok:
                return rect
        return None

    def grow(self, place_id: str) -> tuple[int, int, int, int] | None:
        rect = self.growth(place_id)
        if rect is None:
            return None
        self.set_rect(place_id, rect)
        return rect

    def add_place(self, place: Place) -> None:
        """A place that did not exist when the run began, such as a house built."""
        self.places[place.id] = place
        for t in place.tiles():
            self._place_at[t] = place.id

    def remove_place(self, place_id: str) -> None:
        place = self.places.pop(place_id)
        for t in place.tiles():
            if self._place_at.get(t) == place_id:
                self._place_at.pop(t, None)

    def find_plot(self, size: int = 3, near_kind: str = "home") -> tuple[int, int, int, int] | None:
        """A free ``size`` square on dry ground, clear of every place by a tile,
        as close as it can be to the places of ``near_kind``. Deterministic:
        ties go to the lowest row, then column."""
        anchors = [p for p in self.places.values() if p.kind == near_kind]
        centres = [(p.rect[0] + p.rect[2] / 2, p.rect[1] + p.rect[3] / 2) for p in anchors]
        best = None
        for y in range(1, self.height - size):
            for x in range(1, self.width - size):
                ring = [(x + i, y + j) for i in range(-1, size + 1) for j in range(-1, size + 1)]
                if not all(self.walkable(t) and t not in self._place_at for t in ring):
                    continue
                cx, cy = x + size / 2, y + size / 2
                d = min((abs(cx - ax) + abs(cy - ay) for ax, ay in centres), default=0)
                if best is None or d < best[0]:
                    best = (d, (x, y, size, size))
        return best[1] if best else None

    def set_rect(self, place_id: str, rect) -> None:
        old = self.places[place_id]
        for t in old.tiles():
            self._place_at.pop(t, None)
        place = replace(old, rect=tuple(rect))
        self.places[place_id] = place
        for t in place.tiles():
            self._place_at[t] = place_id

    def extend_east(self, columns: int) -> dict[str, tuple[int, int, int, int]]:
        """Open land along the east edge, ``columns`` wide. A road that ran to
        the old edge runs on to the new one. Returns the roads extended."""
        edge = self.width
        self.width += columns
        roads = {}
        for p in list(self.places.values()):
            x, y, w, h = p.rect
            if p.kind == "road" and x + w == edge:
                roads[p.id] = (x, y, self.width - x, h)
                self.set_rect(p.id, roads[p.id])
        return roads

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "places": [p.to_dict() for p in self.places.values()],
            "blocked": self.blocked,
        }


def distance(a: Tile, b: Tile) -> int:
    """Chebyshev distance, matching 8-connected movement."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


@dataclass
class Clock:
    """In-game time. One tick is ``minutes_per_tick`` minutes."""

    minutes_per_tick: int = 10
    days_per_year: int = 8
    start_hour: int = 6
    tick: int = 0

    @property
    def ticks_per_day(self) -> int:
        return 24 * 60 // self.minutes_per_tick

    @property
    def total_minutes(self) -> int:
        return self.start_hour * 60 + self.tick * self.minutes_per_tick

    @property
    def day(self) -> int:
        return self.total_minutes // (24 * 60)

    @property
    def hour(self) -> float:
        return (self.total_minutes % (24 * 60)) / 60

    @property
    def year(self) -> int:
        return self.day // self.days_per_year

    @property
    def part_of_day(self) -> str:
        h = self.hour
        if h < 6 or h >= 21:
            return "night"
        if h < 11:
            return "morning"
        if h < 14:
            return "midday"
        if h < 18:
            return "afternoon"
        return "evening"

    @property
    def days_per_season(self) -> int:
        return max(1, self.days_per_year // 4)

    @property
    def season(self) -> str:
        """Four seasons to a year, so a season is a couple of in-game days."""
        return SEASONS[(self.day // self.days_per_season) % 4]

    def season_of_day(self, day: int) -> str:
        return SEASONS[(day // self.days_per_season) % 4]

    @property
    def growing_progress(self) -> float:
        """How far through spring and summer it is, from 0 to 1 (1 after)."""
        into_year = (self.total_minutes / (24 * 60)) % self.days_per_year
        return min(1.0, into_year / (2 * self.days_per_season))

    def years_per_tick(self) -> float:
        return 1.0 / (self.ticks_per_day * self.days_per_year)

    def ticks_until_hour(self, hour: float) -> int:
        """Ticks until the next time the clock reads ``hour``."""
        minutes_now = self.total_minutes % (24 * 60)
        target = int(hour * 60)
        delta = (target - minutes_now) % (24 * 60) or 24 * 60
        return max(1, delta // self.minutes_per_tick)

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "day": self.day,
            "year": self.year,
            "hour": round(self.hour, 2),
            "part": self.part_of_day,
        }
