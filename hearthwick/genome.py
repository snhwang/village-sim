"""Temperament as a BEAR genome.

Hearthwick uses BEAR's genetics as they are. The genes are declared in
data/loci.yaml as a LocusRegistry. An allele is the set of instructions that
carry ``metadata.gene_category: <locus>`` and share a ``temp_<allele>`` gate,
so a gene has as many alleles as the library holds for it, and a new one is
written rather than declared. Breeding is ``bear.evolution.breed`` and
expression is ``bear.evolution.express``.

This module only connects the two. The library itself stays shared: villagers
are told apart at retrieval by their ``temp_`` tags, not by copies of the
instructions. A villager's genotype is a small corpus of its alleles'
instructions, which is what ``breed`` and ``express`` operate on, and what it
expresses decides its tags.

``metadata.allele`` is left to BEAR, which marks the two copies of a
diploid gene "a" and "b" with it. The allele's own name is its gate.

Every founder carries two copies of every gene (``genotype`` in
founders.yaml). Dominance is BEAR's ``metadata.dominance`` score, written
on every instruction of a dominant allele. What a founder expresses is its
temperament, and its temperament decides its tags.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from bear import Corpus, Instruction
from bear.evolution import breed, express
from bear.genetics import breeding_config
from bear.models import LocusRegistry

from hearthwick.config import DATA_DIR

LOCI_FILE = DATA_DIR / "loci.yaml"
LOCUS_KEY = "gene_category"      # bear.genetics.DEFAULT_LOCUS_KEY
ALLELE_TAG = "temp_"


def load_loci(path: Path = LOCI_FILE) -> LocusRegistry:
    return LocusRegistry.from_yaml(Path(path).read_text(encoding="utf-8"))


def allele_of(instruction: Instruction) -> str | None:
    """The allele an instruction belongs to, read from its gate."""
    for tag in instruction.scope.required_tags or ():
        if tag.startswith(ALLELE_TAG):
            return tag[len(ALLELE_TAG):]
    return None


def alleles(instructions: Iterable[Instruction],
            registry: LocusRegistry) -> dict[str, list[str]]:
    """Each gene's alleles, in registry order, each in order of first appearance."""
    found: dict[str, list[str]] = {locus.name: [] for locus in registry.loci}
    for instruction in instructions:
        locus = (instruction.metadata or {}).get(LOCUS_KEY)
        allele = allele_of(instruction)
        if locus in found and allele and allele not in found[locus]:
            found[locus].append(allele)
    return found


def genotype(temperament: Mapping[str, str | Iterable[str]],
             instructions: Iterable[Instruction]) -> Corpus:
    """A villager's genome: the instructions of every allele it carries.

    ``temperament`` maps each gene to one allele, or to the alleles it
    carries. The instructions are the shared library's own, so a founder's
    genome is exactly the part of the library its tags already select.
    """
    carried = {locus: {value} if isinstance(value, str) else set(value)
               for locus, value in temperament.items()}
    corpus = Corpus()
    for instruction in instructions:
        locus = (instruction.metadata or {}).get(LOCUS_KEY)
        if locus in carried and allele_of(instruction) in carried[locus]:
            corpus.add(instruction)
    return corpus


@lru_cache(maxsize=1)
def library() -> tuple[Instruction, ...]:
    """Every instruction that belongs to a gene, wherever in the corpus it lives."""
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    return tuple(i for i in corpus if (i.metadata or {}).get(LOCUS_KEY))


def diploid(copies: Mapping[str, Sequence[str]], name: str,
            instructions: Iterable[Instruction] | None = None,
            registry: LocusRegistry | None = None) -> Corpus:
    """A founder's genome, with two copies of every gene.

    ``copies`` maps each gene to its two alleles. A founder has no parents in
    the simulation, so its genome is bred from two gametes, each carrying one
    copy of every gene. That is ``bear.evolution.breed`` doing what it does
    for any child, and it labels the copies "a" and "b" as ``express``
    expects. Built any other way, a heterozygote's two alleles would carry no
    labels and ``express`` would pass both through.
    """
    instructions = list(library() if instructions is None else instructions)
    registry = registry or load_loci()
    gametes = [genotype({locus: pair[k] for locus, pair in copies.items()}, instructions)
               for k in (0, 1)]
    config = breeding_config(recombination="locus", registry=registry, seed=0)
    return breed(gametes[0], gametes[1], name, f"{name}-a", f"{name}-b", config).child


def bred(mother: Mapping[str, Sequence[str]], father: Mapping[str, Sequence[str]],
         name: str, seed: int, instructions: Iterable[Instruction] | None = None,
         registry: LocusRegistry | None = None) -> dict[str, list[str]]:
    """A child's two copies of every gene, one from each parent, by BEAR's ``breed``.

    Each parent's genome is diploid, so breeding is Mendelian: at every gene
    ``breed`` passes one of the mother's two copies at random, and one of the
    father's. The child's copies are read back from the bred instructions,
    copy "a" from the mother and "b" from the father.
    """
    instructions = list(library() if instructions is None else instructions)
    registry = registry or load_loci()
    config = breeding_config(recombination="locus", registry=registry, seed=seed)
    child = breed(diploid(mother, f"{name}-mother", instructions, registry),
                  diploid(father, f"{name}-father", instructions, registry),
                  name, "mother", "father", config).child
    found: dict[str, dict[str, str]] = {}
    for instruction in child:
        metadata = instruction.metadata or {}
        locus, side, allele = metadata.get(LOCUS_KEY), metadata.get("allele"), allele_of(instruction)
        if locus and side in ("a", "b") and allele:
            found.setdefault(locus, {})[side] = allele
    missing = [locus for locus in mother if set(found.get(locus, {})) != {"a", "b"}]
    if missing:
        raise ValueError(f"{name}: breeding left genes without two copies: {missing}")
    return {locus: [found[locus]["a"], found[locus]["b"]] for locus in mother}


def phenotype(genome: Corpus, registry: LocusRegistry | None = None) -> dict[str, str]:
    """The one allele a genome expresses at each gene.

    Hearthwick's alleles all carry distinct dominance scores within a gene,
    so a heterozygote expresses exactly one. A tie would express both, which
    a villager's tags cannot say, so it is refused.
    """
    registry = registry or load_loci()
    out = {}
    for locus, shown in expressed(genome, registry).items():
        if len(shown) != 1:
            raise ValueError(f"{locus}: {shown} are tied in dominance, so both are expressed")
        out[locus] = shown[0]
    return out


def expressed(genome: Corpus, registry: LocusRegistry) -> dict[str, list[str]]:
    """What a genome expresses, as each gene's expressed alleles.

    Dominance is BEAR's: the allele with the higher ``metadata.dominance``
    score is expressed, and tied alleles are both expressed.
    """
    out: dict[str, list[str]] = {}
    for instruction in express(genome, registry, locus_key=LOCUS_KEY):
        locus = (instruction.metadata or {}).get(LOCUS_KEY)
        allele = allele_of(instruction)
        if locus and allele and allele not in out.setdefault(locus, []):
            out[locus].append(allele)
    return out
