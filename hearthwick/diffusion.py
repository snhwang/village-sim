"""Knowledge moving between villagers, changed by whoever receives it.

A listener does not copy what it hears. It retrieves its own lens — the
instructions gated on ``absorbing`` for its character, temperament and stage —
and rewrites the incoming fact through that lens, or discards it. The same
retrieval that decides how a villager speaks decides what it keeps.

Children are the exception, and deliberately so: their filter is weak, so they
keep what they are told nearly as they heard it. What they absorb becomes the
instructions they grow into (milestone 3).
"""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import dataclass

from bear import Context, parse_actions

from hearthwick.knowledge import (
    AFAR_ROOTS,
    CAN_COME,
    KINDS,
    WITNESS_KINDS,
    can_come,
    witness_line,
    Fact,
    KnowledgeStore,
)
from hearthwick.markers import _about

logger = logging.getLogger(__name__)

REFRAME_SYSTEM = """You are {name}, {description} in the village of Hearthwick.

{lens}

Someone has just told you something. Decide what you make of it and how you
would put it to someone else later, in your own words and in one sentence.

Reply with JSON only:
{{"keep": true or false, "text": "the fact as you would tell it", "kind": "one of: hazard, sickness, opportunity, news, rumor"}}

Keep it if it matters to you; discard it if it does not. Do not answer with
anything but the JSON object."""

REFRAME_USER = """{teller} told you: "{text}"

You already know:
{known}

Your JSON:"""


LENS_QUERY = "{name} hears news and decides what to make of it."


def compose_lens(retriever, name: str, tags: list[str]) -> tuple[str, list[str]]:
    """The absorbing instructions a context retrieves, as lines for the prompt.

    One definition, used both by the running simulation and by the replay in
    experiments/diffusion_counterfactual.py, so a counterfactual lens is built
    exactly the way the real one was.
    """
    # top_k has to be generous because the filter comes after the cut: the
    # retriever ranks the whole corpus, and stage, role and action instructions
    # compete for the same slots. At top_k=8, half of all reframings came back
    # with no lens at all and the rest with one, so "the receiver rewrites what
    # it hears through its own instructions" was true about half the time. The
    # effect sizes that came out of that tracked instruction priority rather
    # than trait: absorb-trusting (priority 60) reached the prompt in 34% of
    # reframings and absorb-wary (55) in 3.5%.
    #
    # 24 did not quite saturate. In the paper's six runs, 2 of 675 lenses lost
    # absorb-suspicious and absorb-wary below it, and once the threshold
    # filters gated instructions (since 226c659 in BEAR's development
    # repository) a low threshold leaves
    # more candidates to compete for the slots. So everything the gates admit
    # is ranked before the filter, as decisions already are.
    scored = retriever.retrieve(LENS_QUERY.format(name=name),
                                Context(tags=sorted(tags)),
                                top_k=max(24, len(retriever.corpus)))
    lens = [s for s in scored
            if "absorbing" in s.instruction.scope.required_tags
            and not parse_actions(s.content)]
    return "\n".join(f"- {s.content.strip()}" for s in lens), [s.id for s in lens]


@dataclass
class Diffusion:
    """One attempt to pass a fact, whatever the outcome."""

    receiver: str
    teller: str | None
    source: str
    outcome: str            # stored | duplicate | refused | unchanged
    before: str
    after: str | None
    similarity: float = 0.0


class Diffuser:
    def __init__(self, sim):
        self.sim = sim
        # The village's memories as BEAR items (config.bear_memory), imported
        # only with the switch, so a run without it works on an older BEAR.
        self.memory = None
        if sim.config.bear_memory:
            from hearthwick.memory import MemoryIndex
            self.memory = MemoryIndex(sim)
        self.stores: dict[str, KnowledgeStore] = {
            cid: self._new_store(cid) for cid in sim.characters
        }
        self._count = 0
        # What each villager remembers sharing: for each other villager, the
        # news roots it told them or heard from them (config.told_memory).
        self.told: dict[str, dict[str, set[str]]] = {}

    # -- helpers ------------------------------------------------------------

    def _new_store(self, character_id: str) -> KnowledgeStore:
        if self.memory is not None:
            from hearthwick.memory import BearKnowledgeStore
            return BearKnowledgeStore(character_id, self.sim.config.duplicate_above, self.memory)
        return KnowledgeStore(character_id, self.sim.config.duplicate_above)

    def store_for(self, character_id: str) -> KnowledgeStore:
        if character_id not in self.stores:
            self.stores[character_id] = self._new_store(character_id)
        return self.stores[character_id]

    def _next_id(self, holder: str) -> str:
        self._count += 1
        return f"f{self._count}:{holder}"

    def known_to(self, holder: str, other: str) -> set[str]:
        """The news ``holder`` remembers ``other`` having, because it told them
        or heard it from them (config.told_memory). Never the other's own
        store, which a villager cannot see into."""
        return self.told.get(holder, {}).get(other, set())

    def _note_told(self, teller: str, receiver: str, root: str) -> None:
        """Both remember it: the teller that it told, the receiver who from."""
        self.told.setdefault(teller, {}).setdefault(receiver, set()).add(root)
        self.told.setdefault(receiver, {}).setdefault(teller, set()).add(root)

    def vectors(self, texts: list[str], chunk: int = 1024) -> dict:
        """Vectors for many texts, each distinct text embedded once, in
        batches the embedder sends together: what a checkpoint restore needs
        for every fact. One at a time, the live village's 34,000 facts took
        ten minutes. Chunked, so the embedder's cache never drops a vector
        before it is read."""
        embedder = self.sim.embedder
        distinct = list(dict.fromkeys(texts))
        if embedder is None or not distinct:
            return {}
        out: dict = {}
        for start in range(0, len(distinct), chunk):
            part = distinct[start:start + chunk]
            try:
                out.update(zip(part, embedder.embed(part, is_query=False)))
            except Exception as exc:  # noqa: BLE001 - a failed vector must not stop the sim
                logger.warning("Could not embed facts together, one at a time instead: %s", exc)
                out.update((t, self._vector(t)) for t in part)
        return out

    def _vector(self, text: str):
        embedder = self.sim.embedder
        if embedder is None:
            return None
        try:
            return embedder.embed_single(text, is_query=False)
        except Exception as exc:  # noqa: BLE001 - a failed vector must not stop the sim
            logger.warning("Could not embed a fact: %s", exc)
            return None

    def lens(self, character, tags: list[str] | None = None) -> tuple[str, list[str], list[str]]:
        """How this villager filters what it hears, from its own instructions.

        ``tags`` overrides the context, which is how the counterfactual replays
        one villager's situation through another villager's temperament.
        """
        if tags is None:
            tags = self.sim.brain.context_tags(character, self.sim.characters) + ["absorbing"]
        text, used = compose_lens(self.sim.retriever, character.name, tags)
        return text, used, sorted(tags)

    # -- witnessing ---------------------------------------------------------

    def witness(self, event: str, place: str | None, witnesses: list[str],
                data: dict, tick: int, root: str | None = None) -> list[Fact]:
        """A villager who saw it holds it first-hand: hop 0, no teller.

        ``root`` is for several things that happen at one place in one tick,
        such as the news a storyteller arrives with, which would otherwise
        share a root and be taken for one another.
        """
        kind = WITNESS_KINDS.get(event, "news")
        template = witness_line(event, data)
        if template is None:
            return []
        place_name = self.sim.world.places[place].name if place in self.sim.world.places else "the village"
        text = template.format(place=place_name, topic=data.get("topic", "news"))
        root = root or f"{event}:{place or '-'}:{tick}"

        stored = []
        afar = self._afar(root, None)
        # A storyteller's tale or a traveller's word of something that can
        # come here (config.short_warnings).
        tags = ((CAN_COME,) if self.sim.config.short_warnings and event in ("tale", "traveler")
                and can_come(data.get("topic", "")) else ())
        for holder in witnesses:
            fact = Fact(id=self._next_id(holder), holder=holder, text=text, kind=kind,
                        place=place, root=root, parent=None, teller=None, hop=0, tick=tick,
                        from_afar=afar, tags=tags)
            if self._commit(fact, source="witnessed"):
                stored.append(fact)
        return stored

    def remember(self, holder: str, text: str, kind: str, tick: int,
                 place: str | None = None, root: str | None = None) -> Fact | None:
        """Record something this villager did or lived through.

        Same machinery as witnessing -- hop 0, no teller, its own entry in its
        own store -- but with an experience kind, so it carries no knows_ tag
        and is never offered to anybody. Repeating it reinforces rather than
        duplicates, so a villager that talks to the same neighbour six times
        ends up holding one memory with a count rather than six memories.
        """
        fact = Fact(id=self._next_id(holder), holder=holder, text=text, kind=kind,
                    place=place, root=root or f"lived:{holder}:{tick}", parent=None,
                    teller=None, hop=0, tick=tick)
        return fact if self._commit(fact, source="lived") else None

    def _afar(self, root: str, parent: Fact | None) -> bool:
        """Whether news is held as from afar (config.afar_news): a storyteller's
        tale or a traveller's news from beyond the village, or anything retold
        from it. Such news never makes a local hazard: a tale of wolves in
        distant pastures no longer tags its holder knows_hazard_east_road, which
        is how 1,883 of the open-ended run's 2,020 hazard facts came about."""
        if not self.sim.config.afar_news:
            return False
        return root.startswith(AFAR_ROOTS) or bool(parent is not None and parent.from_afar)

    # -- telling ------------------------------------------------------------

    def _to_tell(self, teller, receiver_id: str, topic: str | None = None,
                 roots: list[str] | None = None) -> list[Fact]:
        """What a teller brings up. A storyteller tells what it brought first,
        a tale this listener has not heard. Otherwise the village's hazards,
        which every villager brings up first, crowded out every tale a
        storyteller carried once it had heard of the blight.

        ``roots``, given by a warning (config.fresh_warnings), are the events
        it is about, and nothing else is told."""
        n = self.sim.config.facts_per_conversation
        if self.sim.config.told_memory:
            return self._untold(teller, receiver_id, topic, n, roots)
        store = self.store_for(teller.id)
        usual = store.tellable(n)
        if not getattr(teller, "visitor", False):
            return usual
        heard = {f.root for f in self.store_for(receiver_id).facts}
        tales = [f for f in store.facts if f.root.startswith("tale:") and f.root not in heard]
        return (tales + [f for f in usual if f not in tales])[:n]

    def _untold(self, teller, receiver_id: str, topic: str | None, n: int,
                roots: list[str] | None = None) -> list[Fact]:
        """What a teller brings up when it remembers what it has shared
        (config.told_memory): news it has not told this listener or heard
        from them, in the usual order, with news of the place a topic names
        first, and one telling of each event.

        Without it, every conversation offered a villager's same top two
        facts, whatever the listener had. In the second long run one warning,
        chosen about 2,100 times, passed on 5,220 facts its listeners already
        held and 23 they did not (SPECIFICATION-warnings.md section 1).
        """
        store = self.store_for(teller.id)
        shared = self.known_to(teller.id, receiver_id)
        order = store.tellable(len(store))
        if getattr(teller, "visitor", False):
            tales = [f for f in store.facts if f.root.startswith("tale:")]
            order = tales + [f for f in order if f not in tales]
        fresh = [f for f in order if f.root not in shared]
        if roots is not None:
            wanted = set(roots)
            fresh = [f for f in fresh if f.root in wanted]
        elif topic:
            about = _about({f.root for f in fresh}, topic, self.sim.world)
            fresh = [f for f in fresh if f.root in about] + [f for f in fresh if f.root not in about]
        chosen, roots = [], set()
        for fact in fresh:
            if fact.root not in roots:
                roots.add(fact.root)
                chosen.append(fact)
        return chosen[:n]

    def warning(self, teller, receiver, topic: str, instruction_id: str | None = None,
                roots: list[str] | None = None):
        """A warning with config.fresh_warnings: what it passes on is chosen,
        and both remember it as told, as it is given, and the offers follow
        in the coroutine returned. A villager whose warning ends partway
        through a tick decides again in that tick (config.decide_again).
        Remembered only once the offers ran, the listener still looked
        untold, and the second warning to it carried nothing: 14 to 18% of
        the warnings in the first trial of fresh_warnings
        (SPECIFICATION-warnings.md section 13)."""
        facts = self._to_tell(teller, receiver.id, topic, roots)
        for fact in facts:
            self._note_told(teller.id, receiver.id, fact.root)
        return self.tell(teller, receiver, topic, instruction_id, roots, facts)

    async def tell(self, teller, receiver, topic: str,
                   instruction_id: str | None = None,
                   roots: list[str] | None = None,
                   facts: list[Fact] | None = None) -> list[Diffusion]:
        """A warning as a word in passing (config.quick_warnings): the teller's
        news on the topic goes to the receiver now, with no conversation, so
        neither stops what it is doing. What the receiver keeps still goes
        through its lens, as in a conversation. With config.fresh_warnings
        the warning names the events it is about in ``roots``, and
        ``warning`` has already chosen the ``facts``."""
        if facts is None:
            facts = self._to_tell(teller, receiver.id, topic, roots)
        self.sim.log.event(self.sim.clock.tick, "warned", teller=teller.id,
                           receiver=receiver.id, topic=topic, instruction=instruction_id,
                           facts=[f.id for f in facts])
        return [await self.offer(fact, teller, receiver) for fact in facts]

    async def exchange(self, conversation) -> list[Diffusion]:
        """After a conversation, each side offers what it knows to the other."""
        results = []
        for teller_id, receiver_id in (conversation.participants,
                                       conversation.participants[::-1]):
            teller = self.sim.characters[teller_id]
            receiver = self.sim.characters[receiver_id]
            for fact in self._to_tell(teller, receiver_id, conversation.topic):
                results.append(await self.offer(fact, teller, receiver))
        return results

    async def offer(self, fact: Fact, teller, receiver) -> Diffusion:
        """One fact, offered to one villager, filtered through their lens."""
        tick = self.sim.clock.tick
        store = self.store_for(receiver.id)
        if self.sim.config.told_memory:
            self._note_told(teller.id, receiver.id, fact.root)

        # Already descended from the same event? Then this is the same news.
        if fact.root in store.roots():
            known = next(f for f in store.facts if f.root == fact.root)
            store.reinforce(known)
            return self._log(Diffusion(receiver.id, teller.id, fact.id, "duplicate",
                                       fact.text, known.text, 1.0), tick)

        text, kind, keep = await self._reframe(fact, teller, receiver)
        if not keep:
            return self._log(Diffusion(receiver.id, teller.id, fact.id, "refused",
                                       fact.text, None), tick)

        vector = self._vector(text)
        duplicate, similarity = store.duplicate_of(vector)
        if duplicate is not None:
            store.reinforce(duplicate)
            return self._log(Diffusion(receiver.id, teller.id, fact.id, "duplicate",
                                       fact.text, duplicate.text, similarity), tick)

        new = Fact(id=self._next_id(receiver.id), holder=receiver.id, text=text,
                   kind=kind, place=fact.place, root=fact.root, parent=fact.id,
                   teller=teller.id, hop=fact.hop + 1, tick=tick, vector=vector,
                   from_afar=self._afar(fact.root, fact),
                   # What can come here stays so in every retelling.
                   tags=((CAN_COME,) if self.sim.config.short_warnings and CAN_COME in fact.tags
                         else ()),
                   # Word of danger abroad is as old as the telling it came
                   # from: renewed when the storyteller brought it again,
                   # otherwise from when it reached the village
                   # (config.far_danger_dated, MemoryIndex.dated).
                   refreshed=(fact.refreshed if self.sim.config.far_danger_dated
                              and CAN_COME in fact.tags else None))
        self._commit(new, source="told")
        outcome = "unchanged" if text.strip() == fact.text.strip() else "stored"
        return self._log(Diffusion(receiver.id, teller.id, fact.id, outcome,
                                   fact.text, text, similarity), tick)

    async def _reframe(self, fact: Fact, teller, receiver) -> tuple[str, str, bool]:
        """The receiver's version of what it just heard.

        A child keeps it as it heard it: its filter is weak on purpose. An adult
        rewrites it through its lens, which is what makes two villagers' stores
        diverge. Without a speech model, everyone keeps it verbatim and the
        provenance chain still holds.
        """
        speech = self.sim.speech
        if receiver.stage == "child" or speech is None or not speech.available:
            return fact.text, fact.kind, True

        lens, used, lens_tags = self.lens(receiver)
        from hearthwick.conversation import describe

        known = "\n".join(f"- {f.text}" for f in self.store_for(receiver.id).facts[-5:])
        system = REFRAME_SYSTEM.format(name=receiver.name, description=describe(receiver),
                                       lens=lens or "- nothing in particular")
        user = REFRAME_USER.format(teller=teller.name, text=fact.text,
                                   known=known or "- nothing yet")
        seed = zlib.crc32(f"{self.sim.config.seed}:{fact.id}:{receiver.id}".encode())
        reply = await speech.say(system, user, seed)
        parsed = _parse(reply)

        # Everything the counterfactual needs to replay this exact call with a
        # different lens: the inputs, not the prompt, so swapping the lens is
        # the only thing that differs (experiments/diffusion_counterfactual.py).
        self.sim.log.event(self.sim.clock.tick, "lens", character=receiver.id,
                           instructions=used, fact=fact.id, teller=teller.name, tags=lens_tags,
                           heard=fact.text, known=known, seed=seed,
                           kept=None if parsed is None else parsed[0],
                           wrote=None if parsed is None else parsed[1],
                           parsed=parsed is not None)
        if parsed is None:
            logger.debug("Unparseable reframing from %s; keeping it verbatim", receiver.id)
            return fact.text, fact.kind, True
        keep, text, kind = parsed
        return text or fact.text, kind if kind in KINDS else fact.kind, keep

    # -- storing ------------------------------------------------------------

    def _commit(self, fact: Fact, source: str) -> bool:
        store = self.store_for(fact.holder)
        if fact.vector is None:
            fact.vector = self._vector(fact.text)
        duplicate, similarity = store.duplicate_of(fact.vector)
        payload = fact.to_dict()
        payload.pop("tick")          # the event carries the tick itself
        if duplicate is not None:
            # Living it again restarts its clock (config.news_fades). Hearing it
            # again, in offer(), does not.
            store.reinforce(duplicate, refreshed=fact.tick if source == "witnessed" else None)
            self.sim.log.event(fact.tick, "knowledge_duplicate", **payload,
                               matched=duplicate.id, similarity=round(similarity, 3))
            return False
        store.add(fact)
        # Growth counts distinct events, not sentences: hearing the same rumour
        # six times is one thing known.
        holder = self.sim.characters.get(fact.holder)
        if holder is not None:
            if fact.is_experience:
                holder.growth.lived_through(fact.kind)
            else:
                holder.growth.learned(fact.root)
                holder.growth.lived_through(fact.kind)
        self.sim.log.event(fact.tick, "knowledge_stored", source=source,
                           provenance=fact.provenance("store", source).to_dict(),
                           **payload)
        return True

    def _log(self, result: Diffusion, tick: int) -> Diffusion:
        self.sim.log.event(tick, "diffusion", receiver=result.receiver,
                           teller=result.teller, source_fact=result.source,
                           outcome=result.outcome, before=result.before,
                           after=result.after, similarity=round(result.similarity, 3))
        return result


def _parse(reply: str | None) -> tuple[bool, str, str] | None:
    """The model's JSON, or None if it did not produce any."""
    if not reply:
        return None
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(reply[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return bool(data.get("keep", True)), str(data.get("text") or ""), str(data.get("kind") or "")
