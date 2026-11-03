# Village Sim, the paper's edition

A village of non-player characters (NPCs) run by retrieval over
natural-language instructions, with [BEAR](https://github.com/snhwang/bear)
(Behavioral Evolution And Retrieval). Each villager is an independent entity.
What it does, says and keeps comes from the instructions it can retrieve, for
its life stage, its role, its temperament, its persona and what it has
learned. Villagers talk, pass news on in their own words, act on what they
know, go to school, learn a trade, marry, and have children who inherit their
temperament. They grow old and die. A world agent sends weather, sickness,
raiders and travelers through the same retrieval.

The village it simulates is called Hearthwick, and so is the code's package
(`python -m hearthwick`).

This is the code of the paper "Non-player characters that learn, grow up, and
pass it on" (ACM Games: Research and Practice, under review).
[RUNNING_EXPERIMENTS.md](RUNNING_EXPERIMENTS.md) gives every command that made
its results, `results/` holds what the paper quotes, and
[results/paper_v4/SERVING.md](results/paper_v4/SERVING.md) records what served
its models. The design is in [DESIGN.md](DESIGN.md), and the system and its
measurements in [SPECIFICATION.md](SPECIFICATION.md).

## This edition

The simulation the paper ran had more mechanics than its runs used, each
behind a switch. Every one of the paper's runs had these switched off, and
this edition leaves them out, with their code, data, tests, viewer pages and
trials.

| Switch | What it did |
|---|---|
| `designs` | crafters drew their own designs, tried on a physics bench |
| `wants` | villagers wanted things made, or to know something |
| `search` | villagers looked things up on the web |
| `vehicles` | a wanted thing that could be driven was driven and carried loads |
| `placing` | a wanted thing went where its drawing said, worn things included |
| `looking` | a crafter was shown a picture of what it drew |
| `assessing` | assessors judged what was drawn and built |
| `natural_talk` | a longer conversation prompt with small talk |
| `living_memory` | personas without family, and family as memories |
| `bynames` | a larger pool of names, with bynames |
| `time_off` | weekends, holidays and vacations |
| `leisure` | free time, swimming and storytelling gatherings |
| `fishing` | fishing at the stream |
| `practices` | sheltering from the rain as a habit the young learned |
| `memory_gene` | a gene for how long a villager keeps news |
| `impersonal_query` | a situation described without names, for a control |

What is left behaves as the paper's code did under the paper's
configurations, byte for byte. That was checked by running the village under
the configuration of three of the paper's runs (forty days, ten years, and the
village of 300), with a scripted stand-in for the language model, from several
seeds. The events, frames, knowledge and instruction usage each run wrote, the
corpus it loaded and every prompt it sent were compared with what the paper's
commit wrote from the same start, and were the same.

A run's record from the paper still loads. Its configuration names these
switches, all off, so they stay in `SimConfig`, and a configuration with any
of them on is refused. Their command-line flags are gone.

A few traces of the left-out mechanics stay, because the paper's runs had
them and taking them out would change what the village does.

- The market's two instructions for paying for a wanted thing, and saving
  toward one, stay in the corpus, and `[!buy]` and `[!save]` stay among the
  markers a villager may write into its lessons. Nothing is ever wanted, so
  both always refuse.
- Four of the left-out folders of instructions (`search`, `talk`, `timeoff`
  and `wants`) keep only their instructions that belong to a temperament
  gene. They are never loaded into the corpus. The gene library reads them,
  and the order in which alleles first appear there decides the genes a
  visitor draws and a child is bred with.
- The record of the house going up keeps the keys a crafter's drawing and a
  wanted thing used, at their resting values.
- A lesson that names a left-out mechanic's marker is refused in the same
  words as before.
- The founders' designs (`data/structures/`) stay, since the 3D viewer draws
  the village's places from them.

The trial of a later build, which the paper's limitations report, dates word
of danger abroad by when it reached the village (`far_danger_dated`). It is
this edition with that one change added.

## License

Copyright (c) 2026 The Pennsylvania State University. Village Sim is source
available under the Open Core Ventures Source Available License (OCVSAL) 1.0,
which allows use, modification and sharing for non-production purposes. Use
in production needs a commercial agreement. See [LICENSE](LICENSE).

## What it demonstrates

One mechanism decides everything that chooses. A villager's stage, role,
temperament, situation and what it knows become context tags. BEAR retrieves
the instructions gated to those tags, and the action markers in the chosen
instruction are what the villager does. The same retrieval, over that
villager's `talking` instructions, composes the prompt for anything it says.
There is no behavior tree and no hardcoded decision anywhere.

The world is an entity on the same terms. Weather, raiders and travelers are
decisions a world agent retrieves from its own corpus in response to the
village's history, not a schedule. The deciding is BEAR, and the raining is physics.

Anything that always does the same thing is deliberately *not* BEAR: the clock,
pathfinding, energy, aging, and places whose nature never varies. An instruction
that fires in every context is a constant in disguise, and each run reports
instruction usage so those can be found and removed.

## Setup

Python 3.11 or later (tested with 3.12 and 3.14), on Linux, macOS, or Windows
with or without WSL. With [uv](https://docs.astral.sh/uv/), in the
repository's folder, run these.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Or with plain pip, in an activated virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

This installs everything, BEAR v0.3.0 included, which is the BEAR the paper's
runs recorded. BEAR brings sentence-transformers and so PyTorch, which on Linux
comes built for NVIDIA GPUs and takes several gigabytes. For the smaller
CPU-only build, add `--torch-backend cpu` to the uv command, or
`--extra-index-url https://download.pytorch.org/whl/cpu` to pip's. The commands below write
`$PY` for the virtual environment's interpreter, `.venv/bin/python`, or
`.venv\Scripts\python.exe` on Windows.

## Choosing the models

Village Sim needs a language model, for speech, for rewording what a villager
hears and for writing new instructions, and an embedder, for retrieval.
Neither is bundled. Pick one of each.

**Language model**

| Option | How |
|---|---|
| The paper's model on your own GPU | [serving/](serving/README.md), then the default `--llm-url http://localhost:8355/v1` |
| Any OpenAI-compatible server: LM Studio, vLLM, or a cloud provider's endpoint | `--llm-url <url>/v1 --model <name>`, and `--llm-key-env <NAME>` if it needs a key |
| Ollama | `--llm-url http://localhost:11434 --model <name>`, without `/v1`, so BEAR's own Ollama backend can turn thinking off |
| Anthropic, OpenAI or Gemini directly | `--llm-provider anthropic --model <name>`, with the key in `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`, `GOOGLE_API_KEY`) |
| None | `--no-llm`. Villagers talk without lines and keep what they hear word for word |

**Embedder**

| Option | How |
|---|---|
| The paper's embedder, as a service on a GPU or a CPU | [serving/](serving/README.md), then the default `--embedder service` (port 8360) |
| OpenAI's embeddings API | `--embedder bear --embed-model openai:text-embedding-3-small`, with `OPENAI_API_KEY` |
| A server that speaks that API (Ollama, LM Studio, vLLM) | the same, with `OPENAI_BASE_URL` naming it, such as `http://localhost:11434/v1`, and its model's name after `openai:` |
| A local model through sentence-transformers | `--embedder bear --embed-model BAAI/bge-base-en-v1.5` |
| None, for development only | `--embedder bm25 --threshold 0`, which degrades retrieval badly |

Anthropic has no embeddings API, so with Claude for speech choose any
embedder above.

- **Without a good GPU**, use a hosted language model, and either OpenAI's
  embeddings or the paper's embedder on the CPU. On a recent AMD processor
  the embedder takes about a tenth of a second a sentence
  ([serving/README.md](serving/README.md)).
- **Keys** go in the environment or in `.env` at the top of the repository,
  which git ignores, never on the command line. A run records only that a key
  was set.
- **A run stops** if its embedder does not answer, rather than carrying on
  with degraded retrieval. Only `--embedder bm25` runs without one.
- **Another model makes another village.** The similarity threshold (0.15)
  and the cutoff for "the same news" (cosine 0.85) were set for the paper's
  embedder. With another, rerun the retrieval ablation
  (`experiments/retrieval_ablation.py`) to choose a threshold. Results to
  compare with the paper's need the paper's models.
- **What a village asks of them.** The paper's village of thirty made about
  80 language-model calls an in-game day (3,209 over forty days), each about
  700 tokens in and at most 80 out, and about 1,300 embedding calls. Talking
  with villagers adds more.

### Without a good GPU

A village runs on hosted models with nothing served at home. Put the keys in
`.env`, one `NAME=value` a line, and name both models on the command line.
Claude speaks here, and OpenAI's embeddings do the retrieving.

```bash
$PY -m hearthwick run --days 10 --village greater --profile illustrative --threshold 0.15 \
    --llm-provider anthropic --model <a Claude model> \
    --embedder bear --embed-model openai:text-embedding-3-small
```

To keep the paper's embedder, run it on the CPU as
[serving/README.md](serving/README.md) describes, leave out `--embedder` and
`--embed-model`, and name only the hosted language model. The threshold of
0.15 was chosen for the paper's embedder. With another, it is only a starting
point, and the retrieval ablation is how to choose one.

## Reproducing the paper

[RUNNING_EXPERIMENTS.md](RUNNING_EXPERIMENTS.md) gives every step as the
paper's runs were made, with the time each took. In short, with the paper's
models served from `serving/`, these make the three sets of runs.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# The six measured runs and every analysis of them, about seven hours
DAYS=40 DAYS_PER_YEAR=28 PROFILE=illustrative THRESHOLD=0.15 bash experiments/reproduce.sh
# A ten-year run, for each of seeds 1 to 3, about twelve hours
$PY -m hearthwick run --profile illustrative --threshold 0.15 --days 280 \
    --seed 1 --village greater --checkpoint-every 1
# The village of 300, about an hour and a half
$PY -m hearthwick run --profile illustrative --threshold 0.15 --days 10 \
    --seed 1 --village town300 --llm-concurrency 8
```

A new set of runs will not give identical numbers. The runs sample speech at
temperature 0.8, and the model server is not bitwise deterministic, so expect
the same findings with nearby values. `paper/check_numbers.py` checks every
number the paper quotes against the run logs, which are the paper's data
archive. It needs the logs in `runs/`, the results in `results/`, and the
paper's LaTeX beside this repository.

```bash
$PY paper/check_numbers.py --paper submission
```

To analyse the recorded runs again without making new ones, give
`reproduce.sh` their ids.

```bash
RUNS="$(cat results/paper_runs.txt)" DAYS_PER_YEAR=28 PROFILE=illustrative \
    THRESHOLD=0.15 bash experiments/reproduce.sh
```

The scripts behind each result, as the paper's appendix lists them, are in
`experiments/`. The ten-year runs are read by `long_run_report.py`,
`health_check.py`, `lesson_use.py` and `warning_ages.py`, the village of 300
by `scale.py`, and the paper's figures are drawn by `figures.py`,
`case_figures.py`, `long_runs_figure.py`, `pipeline_figure.py` and
`capture_3d.py`.

## Running

A village is two programs. The simulation runs headless and saves checkpoints,
whether or not anyone is watching. The viewer is separate and only reads the
run's log files, so you can open it, close it or stop it at any time without
touching the village.

### 1. Start the models

With the paper's models on your own machine, start them as
[serving/README.md](serving/README.md) describes, and check that both answer.

```bash
curl -s localhost:8355/v1/models | head -c 100; echo
curl -s localhost:8360/health; echo
```

With hosted models there is nothing to start. Add their flags from
"Choosing the models" to the commands below.

### 2. Run a village

```bash
$PY -m hearthwick run --days 40 --village greater --profile illustrative --threshold 0.15 \
    --checkpoint-every 1
```

- `--days` is in-game days. Under `--profile illustrative` a year is 28 days.
- `--village greater` is the 30-villager village every measurement uses.
- `--profile illustrative` sets every switch as the paper's runs had it
  (section 5 below). Without a profile, a switch takes the command line's
  default.
- Villagers grow up. Children go to school, graduate and choose a trade,
  apprentices qualify, and each writes its own lessons as it advances.
  Unpartnered adults court, and a man and a woman who grow fond enough may
  marry. The crafters build a house for a couple with nowhere of their own.
  Couples of age can have children when they can support them, and a newborn
  starts as an infant. `--no-growth` keeps everyone at the stage they started,
  though children can still be born.
- `--checkpoint-every 1` saves the whole state once an in-game day.

The run prints its id, for example `20260926-091500-seed0`. Its files go to
`runs/<run_id>/`. With the speech model on, a village moves at about three
ticks a second, so an in-game day takes about a minute and ten days about eight
minutes.

To stop it, press Ctrl-C, or shut the machine down. It finishes the tick in
progress, saves, and exits. To continue after a stop, a reboot or a power cut,
resume it by its id.

```bash
$PY -m hearthwick run --resume <run_id>
```

The id is all a resume needs. The village, growth and every other setting come
from the run's own record, and so do its length and checkpoint interval. Pass
`--days` to make it run longer. A resumed run appends to the same log, so a run
stopped six times is still one record.

### 3. Watch it

In a second terminal, start the viewer whenever you want to look.

```bash
$PY -m hearthwick view
```

Then open http://localhost:8010/3d in a browser. It follows the run being
written now.

| Control | What it does |
|---|---|
| Run menu | "Latest run" follows the live one. A ● marks runs being written now, and any older run can be chosen |
| Live | jump to what is happening now |
| From start | replay the chosen run from its first tick, at the Replay speed. A replay that catches up with a live run carries on live |
| Drag, scroll | orbit and zoom |
| Click a villager | its stage, role, temperament, persona, its last decision with what BEAR retrieved, and its conversations, what it said and what was said to it |
| Follow selected | keep the camera on the chosen villager |
| All names | show every name. Otherwise a name shows on hover |

A traveling storyteller wears a red cloak, and the feed says what news it
brought and how much it took away when it left.

The header also shows the granary, with how many days of food it holds and
the crop standing in the fields against what they can hold. It turns red when
the village has run out. When villagers clear new ground, the fields grow on
the map.

A link can say what to show. For example
`http://localhost:8010/3d?run=<run_id>&start=begin&from=180&rate=4&who=freya`
replays a run from tick 180 at four ticks a second with Freya selected. The 3D
page loads three.js from jsDelivr, so the browser needs internet access. The
older 2D map is at http://localhost:8010/, and takes `?run=<run_id>&select=<id>`.

The viewer needs no model services. To look at a finished run without starting
a village, run only this step and pick the run from the menu.

### 4. Talk with the villagers

`view` only watches. To talk with villagers, run the village inside the server
instead, with the model services up.

```bash
$PY -m hearthwick serve --village greater --profile illustrative --speed 2
```

Open http://localhost:8010/3d, click a villager, and press **Talk to ...**. You
are a stranger in the village, not one of the villagers. The villager answers
in character, from its speech instructions and what it knows that bears on
what you said. The world stands still while you talk. When you press
**Leave**, the villager decides what to keep of what you said, through its own
lens, as after any conversation, and the panel says what it kept and in what
words. It may pass it on, and your news can be traced as it spreads, since its
root is `player:<conversation>`.

One conversation at a time, and a conversation that goes quiet for five
minutes is ended. With a viewer open, the village runs at `--speed` ticks a
second. With nobody watching, it runs flat out unless given an `--idle-speed`.
Without `--checkpoint-every` it ends with the server.

### 5. The illustrative village

`--profile illustrative` is the village of the paper's runs. It sets every
switch, so a run does not depend on the command line's defaults. It has
28-day years, quick warnings that last days, told memory, memories as BEAR
items with lessons that last years, elders who teach only while pupils need
them and otherwise help in the fields, work through light rain, no idle tick
between actions, the dead's and long-faded memories leaving the live index,
telling only what the listener has not had, ended or unfounded news marked
down, routine memories that fade, the same talk at most once a day, lessons
that rest once their goal is met until something rekindles them, each
declaring as it is written what it answers, how often it recurs and how long
it lasts, and warnings about only the fresh news that unlocked them. Each
switch is described where it is set (`hearthwick/config.py`) and in the
specification it names. `$PY -m hearthwick run --help` lists every option,
and `--profile paper` turns off everything added since the paper's first case
study, in September.

`experiments/health_check.py <run_id> --log <its log>` reads a run and flags
anything a healthy village should not do. That covers unanswered model calls,
errors, villagers idle or stuck, long stretches of an empty granary, news told
again and again, a villager acting on one of its lessons again and again in a
day, a live memory index growing without end, years without births, and
deaths before old age. `experiments/lesson_use.py <run_id>` lists each lesson
that rests, with what it declared and how often it was used.

A run waits out a model server or embedding service that stops answering, for
up to 30 minutes (`SimConfig.server_wait_minutes`), and records each outage.
A run that fails keeps its last checkpoint taken between ticks, and resumes
from it (SPECIFICATION.md section 2.10). On a long run, set
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`, or a village of
a hundred spreads every memory lookup over every core
(SPECIFICATION-memory.md section 7). The logs grow by roughly 400 MB a day of
wall clock. Check `du -sh runs/<run_id>` now and then.

### Other ways to run

```bash
# Village and viewer in one process, 2D map at http://localhost:8010/.
# Convenient for a quick look. It has no checkpoints and ends with the server.
$PY -m hearthwick serve --profile illustrative

# Without the services. --no-llm turns speech off, so villagers talk without
# lines and keep what they hear word for word. --embedder bm25 --threshold 0
# retrieves without the embedding service, which degrades behaviour.
$PY -m hearthwick run --days 2 --no-llm --embedder bm25 --threshold 0

# Whether a change leaves a run as it was. It writes 72 ticks of seed 0
# without the model, every decision, to compare two checkouts with cmp.
$PY experiments/replay_fingerprint.py . --out new.jsonl
```

### A larger village

The paper's runs have 30 villagers. Its village of 300, in 130 households on
an 80 by 60 map, is in `data/villages/town300` and runs the same way. One run
of ten days, as in the paper, and its report, are these.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
$PY -m hearthwick run --village town300 --profile illustrative --threshold 0.15 \
    --seed 1 --days 10 --checkpoint-every 1 --llm-concurrency 8
$PY experiments/scale.py runs/<run_id>
```

On the paper's machine it took 85 minutes and 11,480 model calls.
`experiments/scale.py` writes `results/scale.md` and `.json`, with the wall
clock, calls, decisions and how far news reached. `experiments/make_village.py`
generated both of the paper's villages.

### The model servers

Speech goes by default to an OpenAI-compatible server at
`http://localhost:8355/v1`, which `serving/` starts with the paper's model,
Qwen3.8-27B on SGLang with DFlash speculative decoding. It serves the model as
`Qwen3.8-27B` with `--reasoning-parser qwen3`, so thinking arrives in
`reasoning_content` and never as dialogue. Village Sim asks for real output
only (`thinking=False`, `reasoning_fallback=False`), so an empty reply is
counted as a failed line rather than spoken. Add `--llm-key-env <NAME>` if
the server needs a key.

Every request sends its sampling values, temperature 0.8, top-p 0.95 and
top-k 20 (`llm_temperature`, `llm_top_p`, `llm_top_k`), so a run samples the
same whatever the server's defaults. A run recorded before 2026-10-12 resumes
sending only the temperature, as it did then.

Other endpoints are given the same way.

```bash
--llm-url http://localhost:1234/v1 --model qwen/qwen3.8-27b   # LM Studio
--llm-url http://localhost:11434 --model qwen3.8:27b          # Ollama (native backend)
```

An Ollama URL (port 11434) uses BEAR's native Ollama backend, because Ollama's
OpenAI-compatible endpoint ignores the thinking parameters and returns nothing
to say.

Running Village Sim in WSL against a server on Windows (or the reverse) needs a
reachable address. `localhost` works with WSL mirrored networking. Otherwise
pass the host's IP to `--llm-url`.

Retrieval uses the embedding service (`serving/`, port 8360) by default,
because situational tags are soft and the query decides among them. Other
embedders are in "Choosing the models". `--embedder bm25` works without one
but degrades behaviour
(SPECIFICATION.md section 6.5). Every run writes `runs/<run_id>/` with
`meta.json`, `events.jsonl`, `frames.jsonl`, `usage.json` and, with
checkpoints on, `checkpoint.json`. `usage.json` reports how often similarity,
rather than priority, decided.

## Layout

| Path | Contents |
|---|---|
| `data/world/village.yaml`, `data/villages/` | The hand-written map, and the paper's two villages (`greater`, `town300`) |
| `data/characters/founders.yaml` | The hand-written village's founding villagers |
| `data/instructions/` | The instruction corpus, by folder, for stages, roles, temperament (one file per gene), knowledge, school, trades, family, food, the market, the world and more |
| `data/loci.yaml` | The temperament genes |
| `data/goods.yaml`, `hearthwick/goods.py` | Goods, where each comes from, prices |
| `data/structures/`, `hearthwick/designs.py` | The founders' designs the 3D viewer draws |
| `hearthwick/brain.py` | Context tags, retrieval, action selection, speech guidance |
| `hearthwick/markers.py` | Action marker handlers (`go`, `work`, `talk`, ...) |
| `hearthwick/sim.py` | Tick loop, activities, needs |
| `hearthwick/diffusion.py`, `knowledge.py`, `memory.py` | News, lenses, and memories as BEAR items |
| `hearthwick/conversation.py`, `grounding.py` | Conversations and speech prompts |
| `hearthwick/consolidation.py` | Lessons a villager writes for itself |
| `hearthwick/building.py`, `economy.py`, `land.py` | Houses, purses and the market, and the land growing |
| `hearthwick/server.py`, `follow.py`, `client/` | Live and replay viewers, 2D and 3D |
| `hearthwick/player.py` | Talking with villagers as a stranger |
| `runs/<run_id>/` | Per-run `meta.json`, `events.jsonl`, `frames.jsonl` (git-ignored) |
| `serving/` | The paper's language model and embedder, served yourself, with Docker on a GPU or the embedder on a CPU |
| `experiments/`, `paper/` | Every analysis, figure and check of the paper's numbers |
| `results/` | The outputs the paper quotes, and what served its models (`results/paper_v4/SERVING.md`) |

## Tests

```bash
$PY -m pytest
```

They need no model and no embedding service.
