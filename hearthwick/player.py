"""A human in the village: a stranger who talks with villagers.

Interactive mode, first version. The player is a separate interactor, not a
villager taken over. Every villager stays an independent entity, whose words
come from its own instructions and what it knows, and what the player says
enters the village as news with the player as its source, so it can be traced
as it spreads and changes.

The player picks a villager and talks. While a conversation with the player is
open, the world stands still (hearthwick/server.py stops stepping), so a chat
does not use up hours of village time. The villager answers in character, from
its speech instructions and the things it holds that bear most on what it was
just asked. When the player leaves, the villager decides what to keep of what
it heard, through its own lens, as it does after any conversation
(hearthwick/diffusion.py), and remembers having met a stranger.

A visitor can have a name, kept against its account (hearthwick/accounts.py).
Then the villager is told who has come to talk, and whether they have talked
before, the visitor's lines reach the model under that name, and the villager
remembers "I talked with Scott, who is from outside the village, at ...".
Without a name the visitor is a stranger, as before.

What the player said is one fact with a root of its own (``player:<id>``).
The villager who keeps it holds it at one remove, told by the stranger, and
may pass it on. The player holds no store of its own, and the analyses of the
measured runs never see it, since there is no first-hand account to measure
drift from.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from types import SimpleNamespace

from hearthwick import grounding
from hearthwick.conversation import Conversation, describe
from hearthwick.knowledge import Fact

PLAYER_ID = "stranger"
PLAYER_NAME = "a stranger"
TOPIC = "whatever the stranger brings up"
MAX_HEARD = 600          # characters of what the player said, offered to the lens


@dataclass
class PlayerTalk:
    conversation: Conversation
    villager: str
    said: list[str] = field(default_factory=list)
    who: str | None = None       # what the villagers call the visitor (hearthwick/accounts.py)


class Players:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.talk: PlayerTalk | None = None
        self.count = 0
        # What the lens and the speech guidance need of a teller and a listener.
        self.stranger = SimpleNamespace(id=PLAYER_ID, name=PLAYER_NAME, visitor=True,
                                        stage="adult", role=None)

    @property
    def talking(self) -> bool:
        return self.talk is not None

    # -- starting -----------------------------------------------------------

    def refusal(self, villager_id: str) -> str | None:
        """Why the player cannot talk to this villager now, or None."""
        c = self.sim.characters.get(villager_id)
        if c is None or not c.alive:
            return "there is nobody by that name"
        if self.talk is not None:
            return "someone is already talking with a villager"
        if c.stage == "infant":
            return f"{c.name} is a baby"
        if c.resting:
            return f"{c.name} is asleep"
        if c.conversation_id is not None:
            return f"{c.name} is talking with someone else"
        return None

    def begin(self, villager_id: str, name: str | None = None) -> Conversation:
        """Open a conversation with a villager. ``name`` is what the villagers
        call the visitor, kept against its account; without one it is a
        stranger, as before."""
        reason = self.refusal(villager_id)
        if reason:
            raise ValueError(reason)
        sim = self.sim
        c = sim.characters[villager_id]
        self.count += 1
        place = sim.world.place_at(c.pos)
        conv = Conversation(id=f"player{self.count}", initiator=PLAYER_ID, partner=c.id,
                            topic=TOPIC, start_tick=sim.clock.tick, turns=0,
                            place=place.id if place else None)
        c.conversation_id = conv.id
        self.talk = PlayerTalk(conv, c.id, who=name)
        # The lens and the speech guidance know the visitor by its name.
        self.stranger.name = name or PLAYER_NAME
        sim.log.event(sim.clock.tick, "conversation_start", conversation=conv.id,
                      participants=[PLAYER_ID, c.id], topic=TOPIC, place=conv.place,
                      instruction=None, player=True, **({"visitor": name} if name else {}))
        return conv

    def met_before(self, c, name: str) -> bool:
        """Whether this villager remembers having talked with the visitor."""
        said = f"I talked with {name},"
        return any(f.kind == "met" and f.text.startswith(said)
                   for f in self.sim.diffuser.store_for(c.id).facts)

    def _who(self, c) -> str:
        """Who has come up to talk, as the villager is told."""
        who = self.talk.who if self.talk else None
        if not who:
            # Neutral on purpose: how a villager takes to someone from
            # outside is its temperament's to decide. "A stranger you have
            # never seen before" made even the trusting ones guarded.
            return "Someone from outside the village has come up to talk with you."
        again = f" You have talked with {who} before." if self.met_before(c, who) else ""
        return f"{who}, who is from outside the village, has come up to talk with you.{again}"

    # -- talking ------------------------------------------------------------

    async def say(self, text: str) -> str | None:
        """The player's line, and the villager's answer to it."""
        if self.talk is None:
            raise ValueError("no conversation is open")
        sim, talk = self.sim, self.talk
        text = text.strip()
        if not text:
            return None
        c = sim.characters[talk.villager]
        talk.said.append(text)
        talk.conversation.lines.append({"speaker": PLAYER_ID, "text": text})
        sim.log.event(sim.clock.tick, "utterance", conversation=talk.conversation.id,
                      speaker=PLAYER_ID, listener=c.id, text=text, instructions=[],
                      **({"visitor": talk.who} if talk.who else {}))
        if sim.speech is None or not sim.speech.available:
            return None
        system, user, used, history = self._prompt(c, text)
        seed = zlib.crc32(f"{sim.config.seed}:{talk.conversation.id}:"
                          f"{len(talk.conversation.lines)}".encode())
        line = await (sim.speech.say(system, user, seed, history) if history
                      else sim.speech.say(system, user, seed))
        if line is None:
            return None
        talk.conversation.lines.append({"speaker": c.id, "text": line})
        sim.log.event(sim.clock.tick, "utterance", conversation=talk.conversation.id,
                      speaker=c.id, listener=PLAYER_ID, text=line, instructions=used)
        return line

    def _prompt(self, c, heard: str) -> tuple[str, str, list[str], list[tuple[str, str]]]:
        """What the villager answers with: the system prompt, the stranger's
        last line, the instructions used, and what was said before it."""
        sim, talk = self.sim, self.talk
        guidance, used = sim.brain.speech_guidance(c, self.stranger, TOPIC, sim.characters)
        system = (
            f"You are {c.name}, {describe(c)} in the village of Hearthwick.\n\n"
            f"{grounding.manner(guidance)}\n\n"
            f"{self._who(c)}\n\n"
            f"{grounding.foundation(sim, c, heard)}\n\n"
            "Reply with ONE short line of spoken dialogue, under 40 words. "
            f"{grounding.CONDUCT} "
            "No narration, no stage directions, no quotation marks, no name prefix."
        )
        place = sim.world.name_of(talk.conversation.place)
        lines = talk.conversation.lines
        if sim.config.chat_turns:
            # Each line its own turn, the villager's own as the model's. As
            # a transcript in one message, a small model lost track of who
            # had said what, and echoed the stranger's words back as its own
            # (2026-10-02).
            system += f"\n\nYou are at {place}. It is {sim.clock.part_of_day}."
            # What was said before the line heard, which say() has logged last.
            before = (lines[:-1] if lines and lines[-1]["speaker"] == PLAYER_ID
                      and lines[-1]["text"] == heard else lines)
            # A named visitor's lines carry its name, so the villager does not
            # take the visitor for someone in its own life: Ivar283 once
            # greeted Scott by his wife's name (2026-10-02).
            label = (lambda t: f"{talk.who}: {t}") if talk.who else (lambda t: t)
            history = [("assistant", l["text"]) if l["speaker"] == c.id else ("user", label(l["text"]))
                       for l in before]
            return system, label(heard), used, history
        visitor = talk.who or "Stranger"
        history = "\n".join(
            f"{visitor if l['speaker'] == PLAYER_ID else c.name}: {l['text']}"
            for l in lines)
        user = (f"You are at {place}. It is {sim.clock.part_of_day}.\n"
                f"Conversation so far:\n{history}\n\nYour next line:")
        return system, user, used, []

    # -- ending -------------------------------------------------------------

    async def end(self) -> dict:
        """The villager decides what to keep of what it heard, and remembers
        having met the visitor, by name if it has one. Returns what it made of
        it."""
        if self.talk is None:
            return {"kept": None}
        sim, talk = self.sim, self.talk
        self.talk = None
        conv = talk.conversation
        try:
            return await self._ended(talk, conv)
        finally:
            self.stranger.name = PLAYER_NAME

    async def _ended(self, talk: PlayerTalk, conv: Conversation) -> dict:
        sim = self.sim
        c = sim.characters.get(talk.villager)
        if c is not None and c.conversation_id == conv.id:
            c.conversation_id = None
        sim.log.event(sim.clock.tick, "conversation_end", conversation=conv.id,
                      participants=[PLAYER_ID, talk.villager], lines=len(conv.lines),
                      player=True)
        if c is None or not talk.said:
            return {"kept": None}
        place = sim.world.name_of(conv.place)
        met = (f"I talked with {talk.who}, who is from outside the village, at {place}."
               if talk.who else f"I talked with a stranger at {place}.")
        sim.diffuser.remember(c.id, met, kind="met", tick=sim.clock.tick, place=conv.place)
        # What the stranger said, as one piece of news with a root of its own.
        heard = " ".join(talk.said)[:MAX_HEARD]
        fact = Fact(id=f"{PLAYER_ID}-{conv.id}", holder=PLAYER_ID, text=heard, kind="news",
                    place=conv.place, root=f"player:{conv.id}", parent=None, teller=None,
                    hop=0, tick=conv.start_tick)
        sim.log.event(sim.clock.tick, "player_said", conversation=conv.id,
                      villager=c.id, fact=fact.id, root=fact.root, text=heard,
                      **({"visitor": talk.who} if talk.who else {}))
        result = await sim.diffuser.offer(fact, self.stranger, c)
        return {"kept": result.outcome in ("stored", "unchanged"), "outcome": result.outcome,
                "as": result.after}
