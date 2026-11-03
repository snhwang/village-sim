"""A switched-off mechanic's instructions are not loaded.

The paper profile switches off every mechanic added since the paper's
September runs. A directory or an instruction that needs a switch is loaded
only in a run that has it (hearthwick/corpus.py, SWITCHED_DIRS), so that with
the switch off the corpus is the one from before it, text for text.
"""

from dataclasses import replace

from hearthwick.__main__ import PROFILES
from hearthwick.config import DATA_DIR, NEW_IN_TALK, SimConfig
from hearthwick.corpus import SWITCHED_DIRS, corpus_composition, loaded_instructions


def _paper():
    return replace(SimConfig(), **PROFILES["paper"])


def _everything():
    return replace(SimConfig(), short_warnings=True, elders_in_fields=True,
                   **{name: True for name in NEW_IN_TALK})


def test_the_paper_profile_loads_no_switched_directory():
    dirs = {d for d, _ in loaded_instructions(DATA_DIR, _paper())}
    assert not dirs & set(SWITCHED_DIRS)


def test_the_paper_profile_loads_no_instruction_that_names_an_off_switch():
    paper = _paper()
    for _, inst in loaded_instructions(DATA_DIR, paper):
        needed = inst.metadata.get("switch")
        names = [needed] if isinstance(needed, str) else list(needed or [])
        assert all(getattr(paper, n) for n in names), inst.id


def test_with_every_switch_on_the_switched_instructions_load():
    ids = {inst.id for _, inst in loaded_instructions(DATA_DIR, _everything())}
    for wanted in ("go-sell", "crafter-cut-stone", "knows-fight-blight", "elder-help-tend",
                   "coming-pass-the-word"):
        assert wanted in ids, wanted


def test_the_paper_profile_leaves_them_out():
    ids = {inst.id for _, inst in loaded_instructions(DATA_DIR, _paper())}
    assert not ids & {"go-sell", "crafter-cut-stone", "knows-fight-blight", "elder-help-tend",
                      "coming-pass-the-word"}


def test_the_record_counts_what_was_loaded():
    paper, everything = corpus_composition(DATA_DIR, _paper()), corpus_composition(
        DATA_DIR, _everything())
    assert paper["authored"] == sum(paper["by_dir"].values())
    assert paper["authored"] < everything["authored"]
    assert paper["with_action_markers"] < everything["with_action_markers"]


def test_the_illustrative_profile_loads_the_corpus_the_paper_runs_recorded():
    """The record each paper-v4 run wrote of what it loaded (meta.json,
    ``corpus``), so the left-out mechanics took nothing from it."""
    config = replace(SimConfig(), **PROFILES["illustrative"])
    assert corpus_composition(DATA_DIR, config) == {
        "authored": 167, "with_action_markers": 128,
        "by_dir": {"coming": 1, "culture": 2, "elderwork": 3, "family": 6, "food": 10,
                   "knowledge": 21, "market": 3, "roles": 10, "stages": 51,
                   "temperament": 20, "trades": 15, "visitors": 7, "world": 18}}


def test_a_left_out_folder_holds_only_what_the_gene_library_reads():
    """A left-out mechanic's folder keeps only its instructions of a
    temperament gene, which decide the order alleles appear in
    (hearthwick/genome.py), and no profile loads it."""
    from bear import Corpus

    from hearthwick.config import LEFT_OUT
    kept = [d for d, switch in SWITCHED_DIRS.items() if switch in LEFT_OUT]
    assert sorted(kept) == ["search", "talk", "timeoff", "wants"]
    for d in kept:
        for inst in Corpus.from_directory(DATA_DIR / "instructions" / d):
            assert (inst.metadata or {}).get("gene_category"), inst.id
