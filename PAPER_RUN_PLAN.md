# Hearthwick paper: plan for the runs

October 17, 2026, updated October 22 · Scott Hwang

The live copy, where the open decisions get ticked off and commented on, is
the Claude doc [Hearthwick paper: plan for the runs](https://claude.ai/code/artifact/c81092f7-1af6-4681-8eec-6adbb00ee0b1).
The commands themselves are in `RUNNING_EXPERIMENTS.md`.

## Goal and assumptions

All of the paper's data come from one frozen build of the illustrative village, run as set out below. Short runs measure knowledge flow, growing up and families. Long runs show a village's life over generations.

The three trial runs of the illustrative profile (seeds 1 to 3, ten in-game years each) did not pass. Villagers looped on lessons they had written, one choosing the same lesson up to 129 times in a day. Two fixes followed on 2026-10-18. A one-shot lesson now rests once carried out until something rekindles it, and every lesson declares as it is written what it answers, how often it recurs and how long it lasts. Two 56-day trials of the fixed build (seeds 1 and 2) came back clean. Runs now also wait out a server that stops answering. The build was frozen as paper-v3, and steps 1 to 4 were run on it from 2026-10-18 to 2026-10-21. Seed 3's long run then showed a warning loop: a warning could carry anything its warner had ever heard, so one villager warned up to 134 times a day, and 49,926 of the six measured runs' 196,604 decisions were warnings. The fix (fresh_warnings) makes a warning about only the fresh news that unlocked it. Two 56-day trials of seeds 1 to 3 checked it, and the second, after a smaller fix, came back clean. The build is frozen again as paper-v4, and every set is run again on it. Nothing from the September runs, the paper-v2.x builds or the paper-v3 runs goes into the new results.

## The build we freeze

One Hearthwick tag and one BEAR commit, pinned before any paper run starts, so every number in the paper comes from the same pair.

| Part | What we pin | Note |
| --- | --- | --- |
| Hearthwick | tag `paper-v4` (0313244), on main after the warning trials, 2026-10-22 | adds resting and declared lessons, waits out server outages, and warns only of fresh news. Replaces `paper-v3` and `paper-v3.1`, whose runs are not used |
| BEAR | commit 1ceebc7 of its development repository, in its own WSL clone (`/mnt/c/tmp/bear-paper-v3`) | adds declared instructions, built for the lessons. The switches-off replay is unchanged from the trials' 8e26162 |
| Public `bear` | v0.3.0 (2398e5a), the release of 1ceebc7 | pushed 2026-10-18 after Scott saw it. Four tests that need unpublished example code are held back |
| Village | `--profile illustrative`, settled 2026-10-17 | creation and leisure off, economy on, memory gene off. Resting and declared lessons on since 2026-10-18, fresh warnings since 2026-10-21 |
| Model | Qwen3.8-27B on 8355 (SGLang, DFlash) | temperature 0.8, top-p 0.95, top-k 20 sent with every call |
| Embedder | Nemotron on 8360 | restarts itself after a GPU reset (`serving/embed/serve_embed.py`) |
| Environment | lockstep runs with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1` | without the limits a big village kept eight cores busy for nothing |

Before any run: the full test suite on the pinned BEAR and the switches-off replay, in the run checkout. Done for paper-v3 on 2026-10-18 (649 tests) and for paper-v4 on 2026-10-22 (656 tests, the replay unchanged).

## The runs

Four sets, all on the frozen build and the greater village at 28-day years. Times assume 8355 to ourselves, at about 27 in-game days an hour per run with three running at once.

| Set | Seeds | Length | What it is for | Time |
| --- | --- | --- | --- | --- |
| Threshold ablation | 1 to 6 | short, no model | choose the similarity threshold *t* for this profile | minutes |
| Measured runs | 1 to 6 | 40 days (1.4 years) | knowledge flow, rewording, the counterfactuals, the retrieval ablation | about 3 h, three at a time |
| Long runs | 1 to 3 | 280 days (10 years) | a village's life over generations: people, births per family, food, memory | about 12 h, all three at once |
| Village of 300 | 1 | 10 days | cost and speed at scale | about 3 h |

The measured runs keep the design settled on 2026-10-07 (six seeds, 40 days each), so the paper's analyses carry over unchanged. The long runs replace the trials, which ran a few hours before the freeze.

## Checks on every run

A run enters the paper only if it passes all four. One that fails is redone, never patched.

- **No unanswered model calls.** `experiments/unanswered.py` on its record. The batch script already stops on any run with one.
- **A clean health check.** `experiments/health_check.py` flags nothing, or every flag has a written reason in the run's notes.
- **A clean build.** Its record names the frozen Hearthwick tag and BEAR commit, neither marked dirty.
- **A logged command.** Run through `experiments/logged.sh`, so the command, time and versions land in the run log.

## Analyses and what each feeds

Every analysis is an existing script, run on the frozen runs, and `paper/check_numbers.py` then checks every number the paper quotes. Section numbers are the current draft's and may move.

| Analysis | Runs | Feeds |
| --- | --- | --- |
| Knowledge flow (`knowledge_flow.py`) | measured | §5 and §6, Figure 1 |
| World balance (`world_balance.py`) | measured | §4 and §7 |
| Memory carryover, knowledge by day, couples and families | measured | §5, §5.3, §5.7 (births by family only) |
| Figures 2 and 3 (`figures.py`) | measured, seed 1 | §5 |
| Action, absorption and two-step counterfactuals, rewording | measured | §7 |
| Retrieval ablation (`retrieval_ablation.py`) | its own short runs | §8 |
| Food, storytellers, school and trades | measured | §4 |
| Long-run report, comparison, health check | long | one short section on the village over generations |
| Scale (`scale.py`) | village of 300 | §8, cost and speed |

To keep the paper concise, the long runs get one figure and a short paragraph. The detail stays in the repository.

## Order, timing and who runs what

About a day and a half of machine time from freeze to results. A run waits up to 30 minutes for a server that stops answering, and a long run that stops resumes from its last checkpoint. Scott runs every batch from `RUNNING_EXPERIMENTS.md`. Claude prepares the build, the runbook and the drafts.

1. **Trials** (done 2026-10-17 and 2026-10-18, and again 2026-10-21). The ten-year trials found the lesson loops, and two 56-day trials checked the fixes. Two 56-day trials of three seeds checked the warning fix.
2. **Freeze** (done 2026-10-18 as paper-v3, and 2026-10-22 as paper-v4). Claude pinned BEAR, tagged Hearthwick, ran the suite and the replay, and updated the runbook for the profile. Public `bear` v0.3.0, the sync of 1ceebc7, was pushed after Scott saw it, and is unchanged for paper-v4.
3. **Threshold ablation.** Scott, no model, minutes. Scott picks *t* from it.
4. **Measured runs and analyses.** Scott, about 3 h of runs and 1.5 h of analyses.
5. **Long runs.** Scott, about 12 h, best overnight.
6. **Village of 300.** Scott, about 3 h.
7. **Into the paper.** Claude updates numbers and figures, and drafts the methods table and the long-run section. Scott edits.

## Decisions

Settled with Scott on 2026-10-17.

- BEAR is pinned at whatever its development repository is at on freeze day, checked against the suite: 1ceebc7, with declared instructions (2026-10-18).
- Public `bear` is synced to that commit. Approved.
- The threshold ablation is rerun under this profile, and *t* comes from it.
- The measured runs stay at six seeds of 40 days.
- No 25-year life-story run.
- The paper describes only the frozen build. It does not mention the September or paper-v2.x runs.

Settled with Scott on 2026-10-18.

- A one-shot lesson's urge ends once its goal is met, unless something rekindles it, rather than a hard limit of once a day.
- Each lesson declares as it is written which news it answers, how often it recurs and how long it lasts, built in BEAR rather than in Hearthwick.
- Runs wait out a server that stops answering, and a failed run keeps its last clean checkpoint.
- The embedder restarts itself after a GPU reset.

Settled with Scott on 2026-10-21.

- The warning loop found in the paper-v3 runs is fixed, the build frozen again as paper-v4, and every set rerun. The village of 300 on paper-v3.1 was stopped.

Settled with Scott on 2026-10-23.

- The ten-year runs flag old tales of danger abroad passed on as fresh news (SPECIFICATION-warnings.md section 13). It counts as a defect, fixed after the paper, and the paper names it as future work. The paper-v4 runs are used as they are.
