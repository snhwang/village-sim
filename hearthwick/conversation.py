"""Conversations between two villagers.

A conversation holds both participants in place. Lines are generated
asynchronously by the speech model, each from the speaker's BEAR speech
guidance. Without a model, a conversation still happens and is logged, just
without lines.
"""

from __future__ import annotations

import asyncio
import zlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hearthwick.brain import relation
from hearthwick.character import Character

if TYPE_CHECKING:
    from hearthwick.sim import Simulation

ROLE_WORDS = {
    "farmer": "a farmer", "merchant": "the merchant", "healer": "the healer",
    "guard": "the guard", "crafter": "the miller", "storyteller": "the storyteller",
}
STAGE_WORDS = {"infant": "a baby", "child": "a child", "apprentice": "an apprentice", "adult": "an adult", "elder": "an elder"}


def describe(c: Character) -> str:
    if c.role:
        return f"{STAGE_WORDS[c.stage]}, {ROLE_WORDS.get(c.role, c.role)}"
    return STAGE_WORDS[c.stage]


@dataclass
class Conversation:
    id: str
    initiator: str
    partner: str
    topic: str
    start_tick: int
    turns: int
    place: str | None
    lines: list[dict] = field(default_factory=list)
    task: asyncio.Task | None = None
    generating: bool = False

    @property
    def participants(self) -> tuple[str, str]:
        return (self.initiator, self.partner)


class Conversations:
    def __init__(self, sim: Simulation):
        self.sim = sim
        self.active: dict[str, Conversation] = {}
        self.exchanges: list[asyncio.Task] = []
        self._count = 0
        # Who talked with whom about what today (config.talk_once_a_day). A
        # checkpoint falls between days, so a resume loses nothing of it.
        self._today: tuple[int, set] = (-1, set())

    def talked_today(self, a: str, b: str, topic: str) -> bool:
        """Whether these two have already talked about ``topic`` today."""
        day, talks = self._today
        return day == self.sim.clock.day and (frozenset((a, b)), topic) in talks

    def start(self, a: Character, b: Character, topic: str, instruction_id: str | None) -> Conversation:
        sim = self.sim
        self._count += 1
        if self._today[0] != sim.clock.day:
            self._today = (sim.clock.day, set())
        self._today[1].add((frozenset((a.id, b.id)), topic))
        rng = sim.rng_for("talk", a.id)
        place = sim.world.place_at(a.pos)
        conv = Conversation(
            id=f"conv{self._count}", initiator=a.id, partner=b.id, topic=topic,
            start_tick=sim.clock.tick,
            turns=rng.randint(*sim.config.talk_turns),
            place=place.id if place else None,
        )
        a.conversation_id = b.conversation_id = conv.id
        for c in (a, b):
            c.social = min(1.0, c.social + sim.config.talk_social_gain)
        self.active[conv.id] = conv
        sim.log.event(sim.clock.tick, "conversation_start", conversation=conv.id,
                      participants=[a.id, b.id], topic=topic, place=conv.place,
                      instruction=instruction_id)
        if sim.speech and sim.speech.available:
            conv.generating = True
            conv.task = asyncio.get_running_loop().create_task(self._generate(conv))
        return conv

    async def _generate(self, conv: Conversation) -> None:
        sim = self.sim
        try:
            for turn in range(conv.turns):
                if conv.id not in self.active:
                    return  # ended by timeout
                speaker_id = conv.participants[turn % 2]
                listener_id = conv.participants[(turn + 1) % 2]
                speaker = sim.characters[speaker_id]
                listener = sim.characters[listener_id]
                system, user, used, history = self._prompt(speaker, listener, conv)
                seed = zlib.crc32(f"{sim.config.seed}:{conv.id}:{turn}".encode())
                line = await (sim.speech.say(system, user, seed, history) if history
                              else sim.speech.say(system, user, seed))
                if line is None or conv.id not in self.active:
                    return
                conv.lines.append({"speaker": speaker_id, "text": line})
                sim.log.event(sim.clock.tick, "utterance", conversation=conv.id,
                              speaker=speaker_id, listener=listener_id, text=line,
                              instructions=used)
        finally:
            conv.generating = False

    def _prompt(self, speaker: Character, listener: Character,
                conv: Conversation) -> tuple[str, str, list[str], list[tuple[str, str]]]:
        """The system prompt, the line the speaker answers, the instructions
        used, and what was said before that line, as turns."""
        from hearthwick import grounding

        sim = self.sim
        rel = relation(speaker, listener)
        who = f"{listener.name} is your {rel}." if rel else f"{listener.name} is a neighbor ({describe(listener)})."
        place = sim.world.name_of(conv.place)
        # What was last said, or else the topic, is what the villager recalls
        # its knowledge against.
        about = conv.lines[-1]["text"] if conv.lines else conv.topic
        guidance, used = sim.brain.speech_guidance(speaker, listener, conv.topic, sim.characters)
        system = (
            f"You are {speaker.name}, {describe(speaker)} in the village of Hearthwick.\n\n"
            f"{grounding.manner(guidance)}\n\n"
            f"{who}\n\n"
            f"{grounding.foundation(sim, speaker, about)}\n\n"
            "Reply with ONE short line of spoken dialogue, under 25 words. "
            f"{grounding.CONDUCT} "
            "No narration, no stage directions, no quotation marks, no name prefix."
        )
        setting = (f"You are talking with {listener.name} at {place}. "
                   f"It is {sim.clock.part_of_day}. Topic: {conv.topic}.")
        if sim.config.chat_turns:
            # Each line its own turn, the speaker's own as the model's, as in
            # a conversation with a stranger (hearthwick/player.py).
            system += f"\n\n{setting}"
            lines = conv.lines
            if not lines:
                return system, f"({listener.name} is here. Start the conversation.)", used, []
            history = [("assistant" if l["speaker"] == speaker.id else "user", l["text"])
                       for l in lines[:-1]]
            last = lines[-1]
            if last["speaker"] == speaker.id:
                return system, "(Go on.)", used, history + [("assistant", last["text"])]
            return system, last["text"], used, history
        history = "\n".join(f"{sim.characters[l['speaker']].name}: {l['text']}" for l in conv.lines)
        user = (
            f"{setting}\n"
            + (f"Conversation so far:\n{history}\n\nYour next line:" if history else "Start the conversation:")
        )
        return system, user, used, []

    def update(self) -> None:
        """End conversations that finished or ran out of time."""
        tick = self.sim.clock.tick
        for conv in list(self.active.values()):
            elapsed = tick - conv.start_tick
            finished = not conv.generating and elapsed >= min(conv.turns, self.sim.config.talk_max_ticks)
            if finished or elapsed >= self.sim.config.talk_max_ticks:
                self.end(conv)

    def end(self, conv: Conversation) -> None:
        sim = self.sim
        self.active.pop(conv.id, None)
        if conv.task and not conv.task.done():
            conv.task.cancel()
        for cid in conv.participants:
            c = sim.characters[cid]
            if c.conversation_id == conv.id:
                c.conversation_id = None
        sim.log.event(sim.clock.tick, "conversation_end", conversation=conv.id,
                      participants=list(conv.participants), lines=len(conv.lines))
        # Each side remembers having talked, which is the difference between a
        # second conversation and a repeat of the first. Without this a villager
        # could tell the same neighbour the same thing on consecutive days and
        # neither would know it had happened before.
        if getattr(sim, "diffuser", None) is not None:
            place = sim.world.name_of(conv.place)
            for me, them in (conv.participants, conv.participants[::-1]):
                if me not in sim.characters or them not in sim.characters:
                    continue
                sim.diffuser.remember(
                    me,
                    f"I talked with {sim.characters[them].name} at {place} "
                    f"about {conv.topic}.",
                    kind="met", tick=sim.clock.tick, place=conv.place)
        a, b = (sim.characters.get(cid) for cid in conv.participants)
        # Two who talk grow fonder of each other (hearthwick/courtship.py).
        if a is not None and b is not None and getattr(sim, "courtship", None) is not None:
            sim.courtship.conversed(a, b)
        # Talking is how knowledge moves. Each side offers what it knows; the
        # other rewrites it through its own lens, or does not keep it.
        if getattr(sim, "diffuser", None) is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return          # closing a run: no new work, just let it end
        self.exchanges.append(loop.create_task(sim.diffuser.exchange(conv)))

    async def wait_generating(self) -> None:
        tasks = [c.task for c in self.active.values() if c.task and not c.task.done()]
        tasks += [t for t in self.exchanges if not t.done()]
        self.exchanges = [t for t in self.exchanges if not t.done()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
