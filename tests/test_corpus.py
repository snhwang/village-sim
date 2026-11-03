"""Properties of the authored corpus and of how a run is resumed."""

from __future__ import annotations

from bear import Corpus

from hearthwick.config import DATA_DIR, SimConfig
from hearthwick.genome import alleles, load_loci

# Context tags of which a villager or the world holds at most one at a time.
EXCLUSIVE_PREFIXES = ("weather_", "time_", "stage_", "role_", "season_")
EXCLUSIVE_SETS = [
    {"daytime", "time_night"},
    {"road_watched", "road_quiet", "road_unwatched"},
    {"news_fresh", "news_stale"},
    {"sky", "happening"},
]


def test_no_instruction_requires_tags_that_cannot_hold_together():
    """Required tags must all hold at once. A speech instruction gated on
    weather_rain, weather_storm and weather_frost together was never retrieved,
    and nothing reported it."""
    corpus = Corpus.from_directory(DATA_DIR / "instructions")
    sets = list(EXCLUSIVE_SETS)
    for gene_alleles in alleles(corpus, load_loci()).values():
        sets.append({f"temp_{a}" for a in gene_alleles})

    problems = []
    for instruction in corpus:
        required = set(instruction.scope.required_tags or ())
        for prefix in EXCLUSIVE_PREFIXES:
            clash = sorted(t for t in required if t.startswith(prefix))
            if len(clash) > 1:
                problems.append(f"{instruction.id}: {clash}")
        for exclusive in sets:
            clash = sorted(required & exclusive)
            if len(clash) > 1:
                problems.append(f"{instruction.id}: {clash}")
    assert not problems, "\n".join(problems)


def test_a_resumed_run_keeps_its_own_settings(tmp_path):
    """The resume hint once named only --days and the run id, and a resume
    rebuilt the village from the command line, so following it would have
    resumed a greater-village run on the default map."""
    started = SimConfig(seed=51, village="greater", growth=True, consolidate=False,
                        llm_base_url="http://old-machine:8355/v1", embed_url="http://old:8360")
    saved = started.to_dict()
    here = SimConfig(llm_base_url="http://localhost:8355/v1", embed_url="http://localhost:8360",
                     runs_dir=tmp_path)

    resumed = SimConfig.from_saved(saved, here)
    assert (resumed.seed, resumed.village, resumed.growth, resumed.consolidate) == (51, "greater", True, False)
    assert resumed.talk_turns == started.talk_turns
    assert resumed.llm_base_url == "http://localhost:8355/v1"
    assert resumed.embed_url == "http://localhost:8360"
    assert resumed.runs_dir == tmp_path
