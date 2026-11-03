"""The paired lens swap: does it hold everything it claims to hold?

The measurement in experiments/diffusion_counterfactual.py is only worth
anything if a swap changes the temperament tags and nothing else. That is
checked here rather than trusted, along with the weaker property that actually
holds for the no-lens loci: they cannot hand a villager a temperament filter,
though they can still move the lens around one.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.diffusion_counterfactual import (  # noqa: E402
    NO_LENS_LOCI,
    audit_placebos,
    cosine,
    swapped_tags,
    whole_swap,
)
from hearthwick.character import LOCI, load_founders  # noqa: E402
from hearthwick.config import DATA_DIR  # noqa: E402
from hearthwick.corpus import build_corpus, build_retriever  # noqa: E402
from hearthwick.diffusion import compose_lens  # noqa: E402

TAGS = ["absorbing", "at_well", "role_healer", "stage_adult", "temp_bold",
        "temp_diligent", "temp_gregarious", "temp_plainspoken", "temp_settled",
        "temp_trusting", "time_morning"]


@pytest.fixture(scope="module")
def village():
    founders = load_founders(DATA_DIR / "villages" / "greater" / "founders.yaml")
    corpus = build_corpus(DATA_DIR, founders)
    return founders, build_retriever(corpus, None, 0.0)


# --- the swap changes one thing -------------------------------------------

def test_one_locus_swap_touches_exactly_one_tag():
    before = set(TAGS)
    after = set(swapped_tags(TAGS, "trusting", "suspicious"))
    assert before - after == {"temp_trusting"}
    assert after - before == {"temp_suspicious"}


def test_a_whole_swap_leaves_every_non_temperament_tag_alone():
    donor = {"sociability": "reserved", "caution": "wary", "curiosity": "inquisitive",
             "trust": "suspicious", "diligence": "easygoing", "candor": "embellishing"}
    after = whole_swap(TAGS, donor)
    assert [t for t in after if not t.startswith("temp_")] == \
           sorted(t for t in TAGS if not t.startswith("temp_"))
    assert sorted(after) == after, "tags must be sorted; order moves retrieval scores"


def test_swapped_tags_come_back_sorted():
    assert swapped_tags(TAGS, "trusting", "suspicious") == \
        sorted(swapped_tags(TAGS, "trusting", "suspicious"))


# --- the no-lens loci -----------------------------------------------------

def test_the_no_lens_loci_carry_no_absorbing_instruction(village):
    founders, retriever = village
    roster = {c.id: {"temperament": c.temperament} for c in founders}
    audit = audit_placebos(retriever, roster)
    for locus in NO_LENS_LOCI:
        assert locus in audit, f"{locus} is not a locus in this village"
        assert not any(audit[locus].values()), \
            f"{locus} gained an absorbing instruction; it is no longer a no-lens locus"


def test_every_locus_is_audited(village):
    founders, retriever = village
    roster = {c.id: {"temperament": c.temperament} for c in founders}
    assert set(audit_placebos(retriever, roster)) == set(LOCI)


def test_a_no_lens_swap_adds_no_temperament_filter(village):
    """What a no-lens swap cannot do.

    It can still move the lens: the tags are embedded with the query, so
    changing one reorders the role instructions around it and shifts the
    top-k cut. Measured across the real logged contexts that happens about 5%
    of the time for sociability and 12% for diligence, which is why these are
    a weak control and the measurement reports a same-prompt floor instead.
    What a no-lens swap can never do is hand the villager a temperament
    filter, and that is the invariant worth pinning.
    """
    _, retriever = village

    def temperament_filters(tags):
        _, ids = compose_lens(retriever, "Ada", tags)
        return [i for i in ids if i.startswith("absorb-") and "role" not in i]

    base = temperament_filters(TAGS)
    for mine, theirs in (("gregarious", "reserved"), ("diligent", "easygoing")):
        after = temperament_filters(swapped_tags(TAGS, mine, theirs))
        assert after == base, (
            "swapping " + mine + " for " + theirs + " changed a temperament filter")


def test_swapping_a_live_locus_does_change_the_lens(village):
    """And the contrast: trust really does hand the villager another filter."""
    _, retriever = village
    _, base_ids = compose_lens(retriever, "Ada", TAGS)
    _, ids = compose_lens(retriever, "Ada", swapped_tags(TAGS, "trusting", "suspicious"))
    assert "absorb-trusting" in base_ids
    assert "absorb-suspicious" in ids
    assert "absorb-trusting" not in ids


# --- the divergence measure -----------------------------------------------

def test_cosine_of_a_vector_with_itself_is_one():
    assert cosine([0.3, 0.4], [0.3, 0.4]) == pytest.approx(1.0)


def test_cosine_survives_a_zero_vector():
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
