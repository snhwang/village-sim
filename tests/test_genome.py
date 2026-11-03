"""Temperament follows BEAR's genetics: loci, alleles, breeding, expression."""

from __future__ import annotations

import pytest
from bear import Corpus
from bear.evolution import breed
from bear.genetics import breeding_config
from bear.models import Dominance

from hearthwick.character import LOCI, load_founders
from hearthwick.config import DATA_DIR
from hearthwick.genome import (LOCUS_KEY, allele_of, alleles, diploid, expressed, genotype,
                               load_loci, phenotype)

VILLAGES = [DATA_DIR / "characters" / "founders.yaml",
            DATA_DIR / "villages" / "greater" / "founders.yaml"]


@pytest.fixture(scope="module")
def registry():
    return load_loci()


@pytest.fixture(scope="module")
def library():
    """Every instruction that belongs to a gene, wherever it lives."""
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    return [i for i in corpus if (i.metadata or {}).get(LOCUS_KEY)]


def test_the_genes_are_declared_once_in_bear_format(registry):
    assert tuple(locus.name for locus in registry.loci) == LOCI
    assert all(locus.dominance == Dominance.DOMINANT for locus in registry.loci)


def test_every_allele_instruction_belongs_to_a_declared_gene(registry):
    """Gated on an allele means part of that allele's gene. The lens
    instructions were once gated on alleles with no gene named, so code that
    grouped by locus would have left them out of their trait."""
    declared = {locus.name for locus in registry.loci}
    locus_of: dict[str, str] = {}
    problems = []
    for instruction in Corpus.from_directory(DATA_DIR / "instructions"):
        allele = allele_of(instruction)
        locus = (instruction.metadata or {}).get(LOCUS_KEY)
        if allele is None:
            continue
        if locus not in declared:
            problems.append(f"{instruction.id}: gated on {allele}, gene {locus!r}")
        elif locus_of.setdefault(allele, locus) != locus:
            problems.append(f"{allele} is in both {locus_of[allele]} and {locus}")
    assert not problems, "\n".join(problems)


def test_allele_names_are_left_to_bear(library):
    """BEAR marks the two copies of a diploid gene "a" and "b" in
    metadata.allele. A name there would be overwritten by breeding."""
    assert not [i.id for i in library if "allele" in (i.metadata or {})]


def test_each_gene_has_the_alleles_the_library_holds(library, registry):
    found = alleles(library, registry)
    assert set(found) == set(LOCI)
    assert all(len(values) >= 2 for values in found.values()), found


@pytest.mark.parametrize("village", VILLAGES, ids=["small", "greater"])
def test_every_founder_carries_two_copies_that_express_its_temperament(village, registry):
    for founder in load_founders(village):
        assert set(founder.genotype) == set(LOCI)
        assert all(len(pair) == 2 for pair in founder.genotype.values())
        assert phenotype(diploid(founder.genotype, founder.id), registry) == founder.temperament


@pytest.mark.parametrize("village", VILLAGES, ids=["small", "greater"])
def test_a_founder_child_has_one_copy_from_each_parent(village):
    founders = {f.id: f for f in load_founders(village)}
    for child in founders.values():
        parents = [founders[p] for p in child.parents]
        for locus, pair in child.genotype.items():
            if len(parents) == 2:
                a, b = (p.genotype[locus] for p in parents)
                assert pair[0] in a and pair[1] in b, (child.id, locus)
            elif parents:
                assert pair[0] in parents[0].genotype[locus], (child.id, locus)


def test_each_gene_has_one_dominant_allele(library, registry):
    """An allele's instructions share one score, and a gene's alleles differ,
    so a heterozygote expresses one allele and its tags can say which."""
    score: dict[str, set[float]] = {}
    for instruction in library:
        score.setdefault(allele_of(instruction), set()).add(
            float(instruction.metadata.get("dominance", 1.0)))
    assert all(len(s) == 1 for s in score.values()), score
    for locus, values in alleles(library, registry).items():
        assert len({next(iter(score[v])) for v in values}) == len(values), locus


def test_a_founder_expresses_exactly_its_temperament(library, registry):
    founders = load_founders(DATA_DIR / "villages" / "greater" / "founders.yaml")
    for founder in founders:
        genome = genotype(founder.temperament, library)
        assert expressed(genome, registry) == {
            locus: [allele] for locus, allele in founder.temperament.items()}, founder.id


def _two_that_differ(locus: str):
    founders = load_founders(DATA_DIR / "villages" / "greater" / "founders.yaml")
    first = founders[0]
    other = next(f for f in founders if f.temperament[locus] != first.temperament[locus])
    return first, other


def test_breeding_is_bears_and_keeps_where_a_gene_acts(library, registry):
    """A child carries one copy of each gene from each parent, and every copy
    keeps its gate and the situation it acts in. Without that a rain
    instruction would act in the sun, and a lens while the villager speaks."""
    mother, father = _two_that_differ("trust")
    child = breed(genotype(mother.temperament, library), genotype(father.temperament, library),
                  "child", mother.id, father.id,
                  breeding_config(recombination="locus", registry=registry, seed=3)).child

    by_copy: dict[str, dict[str, set[str]]] = {}
    for instruction in child:
        locus = (instruction.metadata or {}).get(LOCUS_KEY)
        if locus:
            by_copy.setdefault(locus, {}).setdefault(
                instruction.metadata.get("allele"), set()).add(allele_of(instruction))
    for locus in LOCI:
        assert set(by_copy[locus]) == {"a", "b"}, locus
        assert by_copy[locus]["a"] == {mother.temperament[locus]}
        assert by_copy[locus]["b"] == {father.temperament[locus]}

    originals = {i.id: set(i.scope.required_tags) for i in library}
    for instruction in child:
        source = instruction.metadata.get("original_id")
        if source in originals:
            assert set(instruction.scope.required_tags) == originals[source], instruction.id


def test_dominance_decides_what_a_heterozygote_expresses(library, registry):
    """BEAR's rule. A higher score expresses one allele, and equal
    scores express both, which phenotype() refuses."""
    mother, father = _two_that_differ("trust")
    config = breeding_config(recombination="locus", registry=registry, seed=3)
    child = breed(genotype(mother.temperament, library), genotype(father.temperament, library),
                  "child", mother.id, father.id, config).child
    assert expressed(child, registry)["trust"] == ["trusting"]

    tied = [i.model_copy(update={"metadata": {k: v for k, v in i.metadata.items()
                                              if k != "dominance"}}) for i in library]
    child = breed(genotype(mother.temperament, tied), genotype(father.temperament, tied),
                  "child", mother.id, father.id, config).child
    assert sorted(expressed(child, registry)["trust"]) == ["suspicious", "trusting"]
    with pytest.raises(ValueError, match="tied"):
        phenotype(child, registry)
