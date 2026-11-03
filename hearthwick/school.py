"""School: a lesson a day, of a piece of news, for each child there.

School is a child's placement (hearthwick/trades.py). Children go in the
mornings, an elder teaches, and the hours count toward graduating. Whoever
teaches at the schoolyard gives each pupil there a lesson once a day, a piece
of news the teacher can tell, which the pupil hears through its own lens like
any other news (hearthwick/diffusion.py).

Lessons in practices, ways of doing things such as sheltering from the rain
that the young learn by watching, being told, or at school, are left out of
this edition (README).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hearthwick.growth import SCHOOL

if TYPE_CHECKING:
    from hearthwick.sim import Simulation


class School:
    def __init__(self, sim: Simulation):
        self.sim = sim
        self.taught_today: set[tuple[str, int]] = set()           # (pupil, day)
        self.lessons: list[tuple] = []                            # news: (fact, teacher, pupil)

    def teach(self) -> None:
        """Whoever teaches at the schoolyard gives each pupil there a lesson,
        once a day: a piece of news."""
        place = self.sim.world.places.get(SCHOOL)
        if place is None:
            return
        present = [c for c in self.sim.characters.values()
                   if c.alive and not c.resting and place.contains(*c.pos)]
        teachers = [c for c in present if c.stage in ("adult", "elder")]
        pupils = [c for c in present if c.stage == "child"]
        if not teachers or not pupils:
            return
        day = self.sim.clock.day
        for pupil in pupils:
            if (pupil.id, day) in self.taught_today:
                continue
            for teacher in teachers:
                store = self.sim.diffuser.store_for(teacher.id)
                news = store.tellable(limit=1)
                if news:
                    self.lessons.append((news[0], teacher, pupil))
                    break
            self.taught_today.add((pupil.id, day))

    async def settle(self) -> None:
        """Deliver the day's lessons."""
        lessons, self.lessons = self.lessons, []
        for fact, teacher, pupil in lessons:
            await self.sim.diffuser.offer(fact, teacher, pupil)
