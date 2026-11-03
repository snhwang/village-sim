"""The shared instruction corpus and its retriever.

All villagers share one corpus and one retriever. Each instruction is gated by
``required_tags`` (stage, role, temperament allele, character id, situation),
and each character's context carries only its own tags, so retrieval returns
only what applies to that character in that moment.
"""

from __future__ import annotations

import logging
from pathlib import Path

from bear import (
    Config,
    Corpus,
    EmbeddingBackend,
    Instruction,
    InstructionType,
    Retriever,
    ScopeCondition,
)

from bear.ownership import own

from hearthwick.character import Character

logger = logging.getLogger(__name__)


def persona_instruction(c: Character) -> Instruction:
    """A villager's persona, owned by it (bear.ownership) and used when it talks."""
    return own(Instruction(
        id=f"persona-{c.id}",
        type=InstructionType.PERSONA,
        priority=70,
        content=c.persona,
        scope=ScopeCondition(),
        metadata={"layer": "persona", "character": c.id},
    ), c.id, keep_tags=["talking"])


# Instruction directories a switch adds, loaded only in a run that has it.
# Gating their instructions on a switch-only tag is not enough. The embedding
# service embeds the corpus in batches of 128, and a vector depends a little
# on what shares its batch, so adding three gated instructions moved other
# instructions' similarities by about 0.001 and changed choices that were
# nearly tied: a run with every new switch off stopped matching main on its
# first tick. Left out, the corpus is main's, text for text and in order.
#
# A directory can need more than one switch. The mechanics this edition
# leaves out (config.LEFT_OUT) were never loaded in the paper's runs. Four of
# their directories stay, holding only their instructions that belong to a
# temperament gene, which the gene library reads (hearthwick/genome.py).
# Their switches are always off, so the corpus never loads them.
SWITCHED_DIRS = {"market": "money", "coming": "short_warnings",
                 "elderwork": "elders_in_fields", "search": "search", "talk": "natural_talk",
                 "timeoff": "time_off", "wants": "wants"}


def _has(switches, needed) -> bool:
    """Whether every switch ``needed`` names is on."""
    names = (needed,) if isinstance(needed, str) else tuple(needed)
    return all(getattr(switches, name, False) for name in names)


def instruction_files(data_dir: Path, switches=None) -> list[Path]:
    """The instruction files a run loads, in Corpus.from_directory's order,
    without the directories of switches it does not have."""
    root = data_dir / "instructions"
    files = sorted(root.glob("**/*.yaml")) + sorted(root.glob("**/*.yml"))
    return [f for f in files
            if not (f.relative_to(root).parts[0] in SWITCHED_DIRS
                    and not _has(switches, SWITCHED_DIRS[f.relative_to(root).parts[0]]))]


def loaded_instructions(data_dir: Path, switches=None):
    """(directory, instruction) for every authored instruction a run loads.

    An instruction in a shared file can name the switches it needs
    (``metadata: {switch: ...}``), and is left out without them.
    """
    root = data_dir / "instructions"
    for f in instruction_files(data_dir, switches):
        for inst in Corpus.from_file(f):
            needed = inst.metadata.get("switch")
            if needed and not _has(switches, needed):
                continue
            yield f.relative_to(root).parts[0], inst


def corpus_composition(data_dir: Path, switches=None) -> dict:
    """What a run's authored corpus holds, for its record: how many
    instructions, by directory, and how many carry an action marker."""
    from bear import parse_actions

    by_dir: dict[str, int] = {}
    actionable = 0
    for directory, inst in loaded_instructions(data_dir, switches):
        by_dir[directory] = by_dir.get(directory, 0) + 1
        actionable += bool(parse_actions(inst.content))
    return {"authored": sum(by_dir.values()), "with_action_markers": actionable,
            "by_dir": dict(sorted(by_dir.items()))}


def build_corpus(data_dir: Path, characters: list[Character],
                 temperament: bool = True, switches=None) -> Corpus:
    corpus = Corpus()
    for _, inst in loaded_instructions(data_dir, switches):
        corpus.add(inst)
    if not temperament:
        # The individuality control: without these, two villagers of the same
        # stage and role are drawing on exactly the same instructions, and any
        # difference in what they do has to come from somewhere else.
        for inst in [i for i in corpus if i.metadata.get("gene_category")]:
            corpus.remove(inst.id)
    for c in characters:
        corpus.add(persona_instruction(c))
    return corpus


# Set by the brain on an elder while the school has fewer teachers than its
# children need (config.teachers_by_pupils, SPECIFICATION-warnings.md section 11).
PUPILS_WAITING = "pupils_waiting"
TEACHING = ("elder-teach",)


def teach_by_pupils(corpus: Corpus) -> Corpus:
    """Let an elder be offered teaching only while pupils are waiting for a
    teacher (config.teachers_by_pupils). The teaching instructions gain the
    gate ``pupils_waiting``, which the brain sets on an elder only while the
    school has fewer teachers than its children need."""
    for inst in corpus:
        if inst.id in TEACHING:
            inst.scope.required_tags = list(dict.fromkeys(
                list(inst.scope.required_tags) + [PUPILS_WAITING]))
    return corpus


# Stopping for rain (config.work_in_rain): the easygoing still step in out of
# it, everyone else works on, and a storm sends everyone in as before.
SHELTER_FROM_RAIN = ("weather-wait-out-rain",)


def rain_for_the_easygoing(corpus: Corpus) -> Corpus:
    """Make easygoing a gate on sheltering from rain, rather than a
    preference (config.work_in_rain). Without it, the instruction applied to
    anyone in any rain, outranked most work, and was the most chosen adult
    instruction by day (SPECIFICATION-warnings.md section 12)."""
    for inst in corpus:
        if inst.id in SHELTER_FROM_RAIN and "temp_easygoing" in inst.scope.tags:
            inst.scope.required_tags = list(dict.fromkeys(
                list(inst.scope.required_tags) + ["temp_easygoing"]))
            inst.scope.tags = [t for t in inst.scope.tags if t != "temp_easygoing"]
    return corpus


def harden_scopes(corpus: Corpus) -> Corpus:
    """Move every soft scope tag into ``required_tags``.

    The ablation knob for "did the gates decide, or did the query?". With every
    situational condition hard-gated, retrieval can only choose among
    instructions that already match the situation exactly, which is the design
    Hearthwick started with.
    """
    for inst in corpus:
        if inst.scope.tags:
            inst.scope.required_tags = list(dict.fromkeys(
                list(inst.scope.required_tags) + list(inst.scope.tags)))
            inst.scope.tags = []
    return corpus


# Said once per process, not once per retriever.
_WARNED_OLD_BEAR = False


def build_retriever(corpus: Corpus, embedder=None, threshold: float = 0.0,
                    restore_below_threshold: bool = False) -> Retriever:
    """A retriever over the shared corpus.

    Without an ``embedder`` this is BM25: no model, no service, instant start.
    With one (the embedding service), vectors are dense and cosine distances
    are stable, which is what the knowledge work needs.

    ``restore_below_threshold`` asks for BEAR's behavior before its threshold
    fix (SimConfig). A bear that predates the switch always behaves that way,
    and is told nothing.
    """
    global _WARNED_OLD_BEAR
    switch = ({"restore_below_threshold": restore_below_threshold}
              if "restore_below_threshold" in Config.model_fields else {})
    if not switch and not restore_below_threshold and not _WARNED_OLD_BEAR:
        _WARNED_OLD_BEAR = True
        logger.warning("this bear predates restore_below_threshold, so the "
                       "threshold never filters a gated instruction")
    if embedder is None:
        config = Config(embedding_backend=EmbeddingBackend.BM25,
                        default_threshold=threshold, mandatory_tags=[], **switch)
    else:
        config = Config(embedding_backend=EmbeddingBackend.NUMPY,
                        default_threshold=threshold, mandatory_tags=[], **switch)
    retriever = Retriever(corpus, config=config, embedder=embedder)
    retriever.build_index()
    return retriever


def make_embedder(kind: str, url: str, api_key: str | None = None,
                  wait_seconds: float = 0.0, model: str = "", strict: bool = False):
    """The embedder named by ``--embedder``, or None for BM25.

    ``service`` is the embedding service (``serving/``), ``bear`` is BEAR's own
    Embedder loading ``model``. One that does not answer falls back to BM25
    with a warning, and the run metadata records which was actually used. With
    ``strict``, as the command line asks, it stops the run instead, since
    BM25 breaks the village (the retrieval ablation).
    """
    if kind == "bm25":
        return None
    if kind == "bear":
        from hearthwick.embedder import BearEmbedder

        embedder = BearEmbedder(model)
        where = f"the model {model!r}"
    else:
        from hearthwick.embedder import ServiceEmbedder

        embedder = ServiceEmbedder(url, api_key=api_key, wait_seconds=wait_seconds)
        where = f"the embedding service at {url}"
    if embedder.connect():
        return embedder
    if strict:
        raise SystemExit(
            f"No embedder: {where} did not answer. Start the service (serving/README.md), "
            "choose another with --embedder bear --embed-model <name> (README, "
            "\"Choosing the models\"), or pass --embedder bm25 to run without one, "
            "which degrades retrieval.")
    logger.warning("Falling back to BM25. Similarity thresholds and knowledge "
                   "deduplication are not meaningful on BM25 scores.")
    return None
