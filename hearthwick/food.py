"""The village's food: a granary, and the crop standing in its fields.

This is physics, like energy and weather. Nothing here decides what anyone
does. Villagers perceive the food situation as context tags (``food_low``,
``harvest_ripe``, ``crop_behind``, ``fields_small``, ``hungry``), and their
instructions decide how they answer it. Whether the village eats depends on
what they choose.

The unit is one adult's food for one day. A child eats half.

The year runs spring, summer, autumn, winter, two days each. In spring and
summer, work in the fields grows the crop, up to what the fields can hold. In
autumn the crop is ripe, and work in the fields gathers it into the granary.
Whatever is still standing when winter comes is lost. So the size of the crop
is set by how much the fields were tended, and how much of it is eaten is set
by how many hands bring it in.
"""

from __future__ import annotations

from dataclasses import dataclass

# What the fields can hold, per tile. The founding fields (99 tiles) hold 198,
# a little under what thirty villagers eat in a year (about 224), so the
# greater village cannot feed itself without clearing more ground. The
# ten-villager hamlet eats about 72 a year and has room to spare.
CROP_PER_TILE = 2.0
# Worker-ticks of tending each tile needs over the growing season to reach
# what it can hold. Two hours a tile. Nine farmers working six hours a day for
# the four growing days tend the founding fields to capacity.
TEND_TICKS_PER_TILE = 12
# Food one worker gathers in a tick. A full crop from the founding fields
# needs about eleven people working six hours on each of the two autumn days,
# which is more than there are farmers.
GATHER_PER_TICK = 0.25
# With richer fields (``SimConfig.richer_fields``, SPECIFICATION.md section
# 2.9j) a tile holds half as much again, tending grows it that much faster, and
# a tick of harvest brings in that much more. At its best, with a dozen hands
# in the fields, the live village's harvests covered 70 to 110% of a year's
# food, so every poor year left the granary low and refused births, and as
# hands fell to two the harvests fell to a quarter of what it ate.
RICH_FIELDS = 1.5
# Worker-ticks to clear one more strip along the edge of the fields. Ten
# worker-hours.
CLEAR_TICKS_PER_STRIP = 60
# At the start, the granary holds last year's harvest: enough to last until
# the first harvest is in, with a day to spare.
START_DAYS_OF_FOOD = 7.0
# A blight in the fields spoils this share of the standing crop each day it
# lasts. A frost takes half of it at once ("took what was in the fields").
BLIGHT_DAILY_LOSS = 0.15
FROST_LOSS = 0.5
# The crop is behind when it is below this share of where steady tending
# would have it by now.
BEHIND_SHARE = 0.8
# A harvest that brings in this share of a year's food is a good one.
GOOD_HARVEST_SHARE = 0.8
# The year these rates were set for. A longer year (``--days-per-year``)
# scales what a field holds, so a village needs the same land per person
# and opens with food to its first harvest (``year_scale``).
BASE_DAYS_PER_YEAR = 8


def year_scale(days_per_year: int) -> float:
    """How many base years' worth of days one year holds: 1 for the eight-day
    year, 3.5 for a year of four weeks."""
    return days_per_year / BASE_DAYS_PER_YEAR

GROWING = ("spring", "summer")
FIELDS = "fields"             # the place the crop grows in
NEW_FIELD = 4                 # tiles on a side of a field broken on new ground


def field_places(world) -> list:
    """Every field: the first, and any broken on new ground since (section
    2.9j), which grow one crop together."""
    return sorted((p for p in world.places.values() if p.kind == "fields"), key=lambda p: p.id)


def field_tiles(world) -> int:
    return sum(len(p.tiles()) for p in field_places(world))


def eats(stage: str) -> float:
    return {"infant": 0.25, "child": 0.5}.get(stage, 1.0)


def need_per_day(characters) -> float:
    return sum(eats(c.stage) for c in characters if c.alive)


def days_to_harvest_end(day: int, days_per_year: int) -> int:
    """Days until the end of the next autumn, when the next harvest is in."""
    season = max(1, days_per_year // 4)
    end = (day // days_per_year) * days_per_year + 3 * season
    if day >= end:
        end += days_per_year
    return end - day


@dataclass
class Food:
    store: float = 0.0
    crop: float = 0.0          # standing in the fields
    tended: int = 0            # worker-ticks of tending this growing season
    gathered: float = 0.0      # brought in this autumn
    cleared: int = 0           # worker-ticks toward the next strip
    last_harvest: float | None = None   # what the last autumn brought in
    rich: float = 1.0          # how much the fields yield, set by the simulation, not kept
    # Days in a year against the base year (year_scale), set by the
    # simulation, not kept. A field holds this many base years' crop, and the
    # same hands fill it, since its seasons are as many times longer.
    scale: float = 1.0

    @classmethod
    def founding(cls, characters, days_per_year: int = BASE_DAYS_PER_YEAR) -> Food:
        """Last year's harvest: enough to last until the first harvest is in,
        with a day to spare. In a year of 28 days that is 22 days, not 7, and
        with 7 the first survival run of four-week years starved in year 1."""
        days = (START_DAYS_OF_FOOD if days_per_year == BASE_DAYS_PER_YEAR
                else days_to_harvest_end(0, days_per_year) + 1)
        return cls(store=round(days * need_per_day(characters), 2))

    # -- work -----------------------------------------------------------

    def capacity(self, tiles: int) -> float:
        return tiles * CROP_PER_TILE * self.rich * self.scale

    def work(self, season: str, tiles: int, skill: float = 1.0) -> str | None:
        """One villager, one tick of work in the fields. Returns what it did.

        ``skill`` scales what the tick yields (hearthwick/trades.py,
        ``output_factor``): a farmer of years does more than a helper.
        """
        if season in GROWING:
            self.tended += 1
            self.crop = min(self.capacity(tiles),
                            self.crop + skill * self.rich * CROP_PER_TILE / TEND_TICKS_PER_TILE)
            return "tend"
        if season == "autumn" and self.crop > 0:
            take = min(skill * self.rich * GATHER_PER_TICK, self.crop)
            self.crop -= take
            self.store += take
            self.gathered += take
            return "gather"
        return None

    def clear(self) -> bool:
        """One villager, one tick of clearing. True when a strip is ready."""
        self.cleared += 1
        if self.cleared >= CLEAR_TICKS_PER_STRIP:
            self.cleared = 0
            return True
        return False

    # -- the day --------------------------------------------------------

    def dawn(self, season: str, yesterday: str, need: float,
             blighted: bool) -> float | None:
        """A day passes. The village eats, and the season may turn.

        Returns what the harvest brought in, on the first day of winter.
        """
        self.store = max(0.0, self.store - need)
        if blighted and self.crop > 0:
            self.crop *= 1 - BLIGHT_DAILY_LOSS
        if season == "winter" and yesterday == "autumn":
            brought_in = round(self.gathered, 2)
            self.last_harvest = brought_in
            self.crop, self.gathered, self.tended = 0.0, 0.0, 0
            return brought_in
        if season == "spring" and yesterday == "winter":
            self.crop, self.tended = 0.0, 0
        return None

    def frost(self) -> None:
        self.crop *= 1 - FROST_LOSS

    # -- what villagers can see -----------------------------------------

    def tags(self, season: str, day: int, days_per_year: int, need: float,
             tiles: int, season_progress: float) -> list[str]:
        """``season_progress`` is how far into the growing season it is, 0 to 1."""
        out = []
        if self.store <= 0:
            out += ["hungry", "food_low"]
        elif need and self.store / need < days_to_harvest_end(day, days_per_year):
            out.append("food_low")
        if season == "autumn" and self.crop > 0:
            out.append("harvest_ripe")
        if season in GROWING and self.crop < BEHIND_SHARE * season_progress * self.capacity(tiles):
            out.append("crop_behind")
        if self.capacity(tiles) < need * days_per_year:
            out.append("fields_small")
        return out

    def verdict(self, brought_in: float, need: float, days_per_year: int) -> str:
        return "good" if brought_in >= GOOD_HARVEST_SHARE * need * days_per_year else "poor"

    def to_dict(self) -> dict:
        return {"store": round(self.store, 2), "crop": round(self.crop, 2),
                "tended": self.tended, "gathered": round(self.gathered, 2),
                "cleared": self.cleared, "last_harvest": self.last_harvest}

    @classmethod
    def from_dict(cls, d: dict) -> Food:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
