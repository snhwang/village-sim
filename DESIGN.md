# Hearthwick: an evolving village of BEAR-driven characters

The design, the reasons for it, and the plan for what is not built yet.

Author S. N. Hwang. Last revised 2026-09-30. SPECIFICATION.md describes the
system as built and holds every measurement. This document says what the
system is for and where it is going. Where the build departed from the design,
section 11 says how and why.

This is the paper's edition (README). The milestones below record how the
system was built, and several name mechanics that the paper's runs had
switched off and this edition leaves out: practices, v0.2's designs, bench,
web search and wants, v0.3's talk and leisure, living memory, natural names
and the memory gene, with the scripts that measured them. Materials, money
and everything the paper's runs had on are here.

| Milestone | Status |
|---|---|
| 1. World, founders, map viewer | built 2026-09-17 |
| 2. World agent and knowledge diffusion | built 2026-09-19 to 20 |
| 3. Growth, episodic memory, consolidation, checkpoints | built 2026-09-23 |
| 3a. Practices and school: behaviour the young learn from adults | built 2026-09-26, behind `--practices` |
| 3b. Food: a granary, a crop grown and brought in by hand, fields that grow | built 2026-09-27 (section 6b) |
| 3c. Traveling storytellers: visitors who bring news and carry it away | built 2026-09-27 (section 2.2) |
| 3d. School, trades and masters: the young graduate, choose a trade, and improve | built 2026-09-27 (section 6c) |
| 4a. Births for existing couples, and an infant stage | built 2026-09-28 (section 7) |
| 4b. Couples forming, and building houses | built 2026-09-28 (SPECIFICATION section 2.7c) |
| 4d. Talking with villagers: a human as a stranger in the village | built 2026-09-28 (SPECIFICATION section 2.9b) |
| 4c. Death of old age | built 2026-09-29 (SPECIFICATION section 2.7d) |
| 5. Long multi-generation runs | the open-ended run, with the model, since 2026-10-03 (`results/long_run/runs.txt`). Year 30 and 136 villagers on 2026-10-05. Runs without the model to year 50 in `experiments/survival.py` |
| 6. Write-up | case study drafted in `paper/` |
| v0.1 | tagged 2026-09-29 at ca26ba3. The paper's builds are tagged `paper-runs` and `paper-development` |
| v0.2. A world its villagers make: designs, a physics bench, web search, wants, materials and money | specified 2026-09-29 (SPECIFICATION-v0.2.md). Steps 1 to 4 built the same day: structures drawn from designs, crafters drawing houses, the physics bench, and wants (SPECIFICATION sections 2.9d to 2.9g). The land grows when the village is full (2.9h). Step 5, materials and money, built 2026-09-30 (2.9i). What keeps a village alive: a wider fertile window, new fields, summer blight, fighting blight (2.9j). Step 6, web search, built 2026-09-30 (2.9k). Drawings placed from the plot, refused when they do nothing they claim, and mended (2.9l). Vehicles (2.9m). Where made things go, what they do there, and villagers to scale (2.9n). Posts set in the ground (2.9o). The crafter told what the bench does (2.9p). The crafter looks at what it drew (2.9q). Things made before placing re-placed (2.9r). Assessors judge what is built (2.9s) |
| v0.3. Talk and leisure | built 2026-10-04 and 05, each part behind a switch that the paper profile turns off: natural talk, news from afar, fading news and natural names (SPECIFICATION-talk.md), living memory (SPECIFICATION-items.md section 5), time off, free time, swimming, storytelling and fishing (SPECIFICATION-leisure.md), and years longer than eight days (`--days-per-year`). With every new switch off, a run matches the build before it decision for decision (`experiments/replay_fingerprint.py`) |
| v0.3. Everything a BEAR item | BEAR's side built (BEAR's `design/items.md`, stages 1 to 5) and checked on the open-ended run's facts (`experiments/items_check.py`, `experiments/items_fading_audit.py`). Hearthwick's memories became BEAR items on 2026-10-11 behind `--bear-memory` (see the next row). The rest of SPECIFICATION-items.md is not started |
| v0.3. Memory in BEAR | one BEAR specification for agents' memory, shared with other BEAR applications, with Hearthwick's requirements in SPECIFICATION-memory.md. BEAR's side built 2026-10-10 (6a63d9f in BEAR's development repository): significance that rises and falls, and an importance floor that does not fade. Hearthwick's stages: (1) villagers remember what they told whom, built 2026-10-10 behind `--told-memory` (SPECIFICATION-warnings.md section 3); (2) memories as BEAR items, built 2026-10-11 behind `--bear-memory`, giving the same knowledge tags and recall as before, decision for decision (`hearthwick/memory.py`); (3) lessons as memories that fade with their news, built 2026-10-12 behind `--fading-lessons`, superseding still to come. A gene for how long a villager keeps news, whose alleles carry a `memory_fade` marker, built the same day behind `--memory-gene` (`data/genes/memory.yaml`); (4) group facts if needed. Warnings as a word to someone within reach, not an errand, built 2026-10-11 behind `--quick-warnings` (SPECIFICATION-warnings.md section 8). Warnings that last days, and far-off news that warns only of what can come here, built 2026-10-12 behind `--short-warnings` (section 10). Lessons that last years while their news lasts days, built 2026-10-13 behind `--lasting-lessons` (SPECIFICATION-memory.md section 6). Elders who teach only while pupils need a teacher, and no idle tick between one action and the next, built 2026-10-14 behind `--teachers-by-pupils` and `--decide-again` (SPECIFICATION-warnings.md section 11). Elders with food work, and work through light rain, built the same day behind `--elders-in-fields` and `--work-in-rain` (section 12). The dead's memories and long-faded ones leaving the live index, and telling only what the listener has not had, built 2026-10-16 behind `--forget-the-dead`, `--forget-faded` and `--novel-telling` (SPECIFICATION-memory.md sections 7 and 8). News that ended or never came marked down, built 2026-10-17 behind `--news-ends` and `--false-alarms` (section 9), routine memories that fade and the same talk once a day behind `--routine-fades` and `--talk-once-a-day` (section 10), one-shot lessons that rest once carried out until something rekindles them behind `--lessons-satisfied` (section 11), lessons that declare as they are written what they answer, how often they recur and how long they last behind `--declared-lessons` (section 12, BEAR's declared instructions, from commit 1ceebc7 of its development repository, released as BEAR v0.3.0), warnings about only the fresh news that unlocked them, built 2026-10-21 behind `--fresh-warnings` (SPECIFICATION-warnings.md section 13), and everything the village should now do in `--profile illustrative` (README section 6) |

---

## 1. Aim

A village of BEAR-driven characters who talk, pass knowledge to each other, act
on what they know, grow from childhood to adulthood, and in time raise
children. The longer aim is a simple digital society of characters that just
live and interact. Knowledge flow comes first, because everything later rests
on it.

The work is a demonstration and a design argument, not a claim that BEAR beats
something. Its thesis is below.

> One set of character instructions governs what a character says, what it
> remembers, and what it does. Because the same retrieval shapes what a
> character keeps, two characters who hear the same news keep different
> versions of it and act differently. Because what a character lived through is
> consolidated into instructions it carries, what it learned as a child becomes
> part of who it is.

The same mechanism runs the world. Anything that responds differently to the
same situation is a BEAR entity, so weather, raiders and travelers are
decisions a world agent retrieves, not a script (section 2.1). Anything that
always does the same thing stays code. Every event in a run therefore traces
back to a retrieved instruction, in one format, whoever or whatever decided it.

### Positioning

| System | What it does | How Hearthwick relates |
|---|---|---|
| Generative Agents (Park et al. 2023) | memory stream with importance scoring, reflection and planning | the closest relative, and much of Hearthwick is the same idea. Both store natural-language items per character, retrieve by relevance and condition a model on them. Consolidation is close kin to reflection. Hearthwick differs in retrieving an authored corpus alongside memories, dispatching actions from markers without a model call, and letting instructions be gated and refused |
| Project Sid, AI Town | many LLM agents in a shared world | the same comparison as above. Hearthwick adds growth and, later, inheritance |
| Crusader Kings III | childhood education and events shape adult traits | here what an adult carries is written from what it actually heard, not drawn from a trait table |
| The Sims | life stages and skill levels | here a stage is earned through knowledge and experience, and advancing changes which instructions are in reach |
| Dwarf Fortress legends | procedural history | here history is what characters retell through their own lenses |

The honest summary is that the differences from memory streams are real but
narrow. They are an authored corpus, cheap and repeatable action, and the
ability to make behaviour unreachable. None is an improvement in general. The
paper (section 10) makes the full comparison.

---

## 2. The world

- Map. A 2D grid of 40 by 30 tiles, crossed by a stream with a bridge on the
  east road and a ford in the south. The `greater` village used for all
  measurements has 23 places. They are thirteen homes, the well, market, inn,
  shrine, schoolyard, mill, fields, watchpost, east road and forest edge
  (`data/villages/greater/`). That is the map as founded. Since v0.2 a
  village gains a quarry, a clay pit and a forge, and new land to the east
  when it is full (SPECIFICATION sections 2.9h and 2.9i).
- Time. One tick is ten in-game minutes and a day is 144 ticks. A villager
  decides only when idle, so it makes 20 to 30 decisions a day. A year is eight
  days, so a childhood lasts hours of simulation, not weeks.
- Resources. Food, from a granary and fields (section 6b), and since v0.2
  goods and coins (SPECIFICATION section 2.9i). Work builds skill, feeds the
  village, and yields goods a villager can sell for what it wants made.
- Events come from a world agent, not a script. Each creates ground-truth facts
  with ids, times and places. That is what makes provenance traceable.

Things that are not behaviour are simulation code. That includes ageing,
pathfinding, the clock, skill bookkeeping, needs and recovery. Every behavioural
decision goes through BEAR retrieval and action markers.

### 2.1 The world is an entity too

A world agent holds nineteen instructions of its own, in the shared corpus but
gated on `world`. It decides twice a day. At dawn it decides the sky, and then
whether anything happens. Weather happens every day, and when it shared the
day's one decision it crowded out a third of the village's news. Both decisions
read the same dawn. Applying the sky first let a morning's rain erase the dry
spell the day's event needed, and the well stopped sickening altogether. Its
context is the village's history. Its markers are world events, in a registry
disjoint from the villagers'.

```yaml
- id: world-well-sickens
  content: The well has been drawn low and warm all season. Something in
           the water turns, and those who drink it will sicken. [!sicken(well)]
  scope: {required_tags: [world, happening, dry_spell, well_busy], tags: [season_summer]}
```

The deciding is BEAR, and the happening is ordinary code. The world decides
that rain comes. The rain falls all day and gives every villager a
`weather_rain` tag. That tag changes what the villagers retrieve, so the
diligent one works through it and the easygoing one waits in the inn. BEAR
sits at both ends, with mechanism in the middle.

Weather settles at dawn. Anything that happens to someone is scheduled for an
hour when someone could be there, such as a trader between 9 and 17 or a
festival in the evening. An event nobody could witness leaves no ground truth
to trace.

What is not an entity. A thing that always does the same thing is code, not a
corpus. The well gives water and the road leads east. That is data the
villagers' retrieval reads as context. Only something that responds to history
earns a corpus.

A corollary is used as a check. An instruction that fires for everyone in every
context is a constant wearing BEAR's clothes. Every run reports how often each
instruction fired and in which contexts (`runs/<id>/usage.json`).

Later the world can evolve too. A world corpus can recombine and mutate like a
character's, which would give two coupled populations.

---

### 2.2 Visitors

A traveler used to be an event: a few villagers near the road came to hold its
news, and nobody arrived. A traveling storyteller is a person. The world
decides when one comes. The storyteller is then an entity on the same terms as
a villager, with a temperament, a persona and a lens, and it retrieves its
behaviour from the same corpus through a `visitor` tag. It stays two days at
the inn, telling the news it brought and listening, and then walks out with
whatever it kept (`hearthwick/visitors.py`, SPECIFICATION section 2.4a).

For the knowledge work this adds two things events could not. News from
outside now has a teller, so its chains start with a person whose own lens
shaped it. And news can leave. What a storyteller heard goes with it, and its
store records what the village let out. A storyteller who comes back with it,
retold elsewhere, is the natural next step and is not built.

Villagers meet a stranger through their temperaments. The curious and the
sociable go to hear it, and the suspicious keep their distance. That is the
same news reaching different people for reasons that are theirs.

## 3. Characters

The measured village has 30 villagers in 13 households, generated by
`experiments/make_village.py`. Roles are spread across six trades, and each
villager draws one allele at each of six temperament loci.

A character is a stack of layers. All but the last are BEAR instructions.

| Layer | Contents | Source | Status |
|---|---|---|---|
| Persona | who this villager is | one authored per founder | built |
| Temperament | six loci (sociability, caution, curiosity, trust, diligence, candor), one allele each | shared library, gated by `temp_<allele>` | built. A BEAR genome over six diploid genes (`data/loci.yaml`). Every founder carries two copies of each, and expresses one |
| Stage | what a child, apprentice, adult or elder does and how | shared library, gated by `stage_<s>` | built |
| Role | farmer, merchant, healer, guard, crafter, storyteller | shared library, gated by `role_<r>` | built. Assigned at generation, not chosen at adulthood |
| Lens | how this villager reframes what it hears | `absorbing` instructions from temperament, role and stage | built. Not yet updated at each stage |
| Learned | instructions written from what the villager lived through | consolidation at each advance | built |
| Store | news and experience, with provenance | witnessing, telling, living | built |

Temperament instructions are shared text. Everyone who is gregarious carries
the same gregarious instructions, so individuality is compositional rather than
bespoke, and adding a villager is cheap. It also means breeding only has to
recombine allele names.

Needs are simulation code and choices are BEAR. Energy and a social meter drain
and refill outside BEAR and only add tags (`energy_low`, `wants_company`).
Without the social meter, the first build had one villager telling another a
story 39 times in a day, including at 2am.

---

## 4. The loop

```
 world agent ──► BEAR retrieval ──► [!weather] [!sicken] [!traveler] ...
 (season, dry spell,                      │
  last harvest, history)                  ▼
                                    code makes it rain       
                                          │  witnesses hold it first-hand
                                          ▼
perceive ──► context tags ──► BEAR retrieval ──► action markers ──► world
   ▲         (stage, place, weather,   (instructions,    │             │
   │          nearby, knows_ tags,      recalled memory) ▼             │
   │          recalled memory)                                         │
   └──────────── new facts ◄──── talk / warn ◄─────────────────── outcomes
                                   │
                                   ▼
                     listener's lens reframes ──► store, reinforce or refuse
```

- Most ticks have no model call. Retrieval ranks every instruction the gates
  admit, the brain resolves their markers down the ranking, and one of the best
  four that can actually be carried out is chosen and dispatched.
- Resolve before choosing. An option that cannot happen, such as warning
  someone who already knows, must not take a place among the options. The
  brain once sampled a fixed top four and resolved afterwards, and villagers
  who knew enough stood idle because all four of their best options were
  refused. A bigger fixed pool would only postpone that, since what cannot be
  done grows with what a villager knows (SPECIFICATION.md section 2.2).
- The model is used for speaking, for reframing what a villager hears, and for
  consolidation.
- Knowledge drives action through tags. A stored fact adds
  `knows_<kind>_<place>`, so an instruction gated on knowing it becomes
  retrievable. This is the concrete link between what a character knows and
  what it does, and it is visible in the logs.

### Villager markers

| Marker | Effect | Status |
|---|---|---|
| `go` | move to a place | built |
| `wander` | walk somewhere nearby | built |
| `rest` | recover energy, for a time or until an hour | built |
| `work` | practise at a site, which builds skill. In the fields it tends or gathers the crop | built |
| `clear` | clear new ground at the edge of a place, which grows it | built (section 6b) |
| `talk` | start a conversation, which triggers diffusion | built |
| `warn` | pass on a fact to someone nearby | built |
| `avoid` | keep away from a place for a time | built |
| `follow`, `play` | a child stays near someone or plays | built |
| `depart` | a visitor leaves the village | built (section 2.2) |
| `apprentice` | a graduate takes up a trade under a master | built (section 6c) |
| `investigate` | go and look, and possibly witness | designed |
| `trade` | exchange resources | designed. Food is the first resource |
| `teach` | deliberate transfer to a child or apprentice | designed |
| `propose` | ask one's sweetheart to marry | built (SPECIFICATION section 2.7c) |
| `accept_proposal`, `decline_proposal` | answer a proposal | built (SPECIFICATION section 2.7c) |
| `fell`, `build` | a crafter fells timber, or builds a house for a waiting couple | built (SPECIFICATION section 2.7c) |

### World markers

| Marker | Effect |
|---|---|
| `weather` | rain, storm, drought or frost for the day, which tags every villager |
| `raid` | raiders arrive on an untended road, witnessed by whoever is near |
| `sicken` | a place becomes a source of illness for four days |
| `traveler` | an outsider arrives with news from beyond the village |
| `festival` | draws the village together in the evening |
| `visitor` | a traveling storyteller comes up the east road to stay a while |

The world used to decide the harvest with a `harvest` marker. The harvest is
now what the villagers bring in (section 6b). It still reaches the log as a
world event, so it is witnessed and told, and the world perceives it as
`harvest_good` or `harvest_poor`.

---

## 5. Knowledge

The diffuser passes what one villager tells another through the receiver's
lens. The mechanics are in SPECIFICATION.md section 2.5. The design choices behind them are these.

- Local, not global. Only the two sides of a conversation, or someone warned,
  receive.
- The receiver decides. Each listener retrieves its own lens and rewrites what
  it heard, or refuses it. Trust works through the lens (`absorb-trusting`,
  `absorb-suspicious`), not through a separate weight.
- Filter strength depends on stage. A child keeps what it hears nearly
  verbatim. That is the material consolidation later turns into who it
  becomes.
- The kind can change on the way. The lens returns a kind with its sentence,
  and the kind sets the `knows_` tag. So a listener who files news as a hazard
  gains behaviour the witness never had. In the measured runs a third of facts
  were refiled, mostly toward danger. Nobody designed that.
- Provenance is a chain. Every fact carries its root event, parent entry,
  teller, hop and tick, as one `bear.provenance` record per hop.
- Memory is not news. A villager's own experiences share its store but are
  never passed on and add no tag. They are recalled by relevance at each
  decision, news first.

Early observations that shaped this. With the speech model on, the same
traveler came out four ways in one early run. The guard who saw it said "A
traveler came up the east road with news from beyond the village." The
children kept it word for word. A trusting, embellishing merchant said "Garrick
mentioned a traveler coming up the east road with news from beyond the
village..." A wary, plainspoken farmer said "Wynn says Garrick spotted a
traveler on the east road..." and kept the whole chain of tellers. In a later
run one villager kept a traveler's news as "a traveler came up the east road
carrying news from beyond the village, which seems to have little bearing on
the sickness spreading from the tainted well". It related new knowledge to what
it already held, unprompted, and the next listener inherited that framing.

Designed and not built:

- Candor on the way out. An embellishing teller would exaggerate what it
  passes on, so rumours drift from both ends. Candor currently acts only on
  speech style and on the receiver's lens.
- Forgetting. Facts never recalled or reinforced within some years decay, and
  reinforced ones become common knowledge. This is how a rumour could become
  tradition across generations.
- Far-off danger dated by when it began (a known defect, found
  2026-10-23). News fades a week after its holder heard it, so months-old
  tales of danger abroad keep reaching villagers who had not heard them and
  come back as warnings, and any later raid counts as the tale coming true.
  The paper-v4 runs carry it and the paper names it as future work
  (SPECIFICATION-warnings.md section 13). The fix is built on main behind
  `--far-danger-dated` (section 14), with trials on the lab machine to come.
- "a adult" in the situation sentence (a known defect, found 2026-10-24).
  The sentence names who is nearby as "Edek, a adult", "a apprentice" or "a
  elder". It is the query every decision is retrieved by, so mending the
  article changes what villagers retrieve: it goes behind a switch in the
  next version, not into the paper's build.
- Memories that are not text, kept on disk (considered with Scott on
  2026-10-23, a later BEAR change). The embedder is a vision-language model
  (Nemotron embed "vl"), so pictures and text share one vector space, and a
  question in words could bring back a picture. Sources exist or are close:
  the crafters' drawings from designs, what a villager sees rendered from the
  world, pictures a player shows a villager, and instructions that carry
  pictures. An image memory's vector costs no more than a sentence's, but the
  image is 100 KB to 1 MB against about 100 bytes of text, so it cannot stay
  in RAM or in a checkpoint. Long lives and large villages point the same way.
  A village now holds everything in RAM: at day 101 of the paper-v4 long
  runs, about 3,700 memories and 860 MB per process, most of it Python and
  the corpus. Fading keeps the live index level, at 70 to 90 memories a
  villager from year 3 of the paper-v3 ten-year runs, but Hearthwick's own
  record of every memory grows with people and years, and a thousand
  villagers over centuries would reach millions. Core BEAR (1ceebc7) has no
  store that memories live in. A corpus is loaded and saved whole, embeddings
  can be cached on disk, and the ChromaDB backend writes an index that BEAR
  rebuilds from the in-memory corpus. The design keeps the live index in RAM
  and the archive, with any image or audio, in a database file on disk
  (LanceDB, or SQLite with a vector extension), changed item by item and read
  back when an old memory is needed. It belongs in BEAR as a storage backend,
  not in Hearthwick, and waits until after the paper.

---

## 6. Growth

Built in milestone 3. The tracks, gates and consolidation steps are specified
in SPECIFICATION.md sections 2.7 and 2.8. The design intent is below.

Four stages, and advancing requires a minimum age and thresholds on three
tracks. Each track is shaped to resist the obvious way of gaming it.
Knowledge counts distinct events, so hearing a rumour six times is one thing
known. Skill rises from practice the villager chose. Experience has diminishing
returns within a kind, so grinding one activity does not advance.

No forced promotion. A villager that reaches the age without the rest stays
where it is, keeps ageing, and can die there. Late bloomers
and characters who never grow up are part of the story. This has consequences
to design for.

- Population viability. Once only adults can partner, gates set too high will
  shrink the village. Log the share of each birth cohort reaching each stage,
  and tune so most characters, not all, reach adulthood.
- Staying stuck must be explainable. Every refusal logs which tracks fell
  short (built).
- Stage at death is recorded and shown in the family tree (milestone 4).

### What happens at an advance

| Step | Status |
|---|---|
| Swap the stage tag, so new stage instructions come into reach | built |
| Consolidate the villager's most reinforced news, then experience, into up to three instructions through `bear.evolution.generate_with_llm`, checked against what the simulation can execute, tied to where it is set, and gated to that villager | built |
| Update the lens with new interests (apprentice) or role (adult) | designed |
| Choose a role at adulthood from the highest skill, and blend its instructions with learned ones using `marker_blend` so markers survive | designed. `marker_blend` is in BEAR |
| Rewrite the persona to reflect who the villager has become | designed |

Consolidation is where the corpus itself grows. The first rehearsals show it
working and show its faults. A child who heard of a traveler wrote itself an
instruction to share the news and chose it 25 times. A lesson about staying
indoors in a storm was chosen 153 times, always in bad weather. A lesson about
the inn was used at home, because nothing tied it to the inn. Lessons are now
tied to where they are set. A place the lesson puts the villager in is a hard
gate, and a place it only mentions is a soft tag.

The long run showed a larger fault. The model was shown bare marker names and
told not to add arguments to a marker shown without one, so it guessed them or
left them out, and the check refused more than four lessons in five. What got
through was nearly all `[!rest]`, which needs no argument. Lessons about the
news, which need a place to avoid or someone to warn, were almost never kept.
Since 2026-10-09 the model is shown each marker's signature, and only the
markers of mechanics the run has on (results/long_run/REPORT.md).

---

## 6a. Practices: behaviour the young learn

Temperament is inherited. Some behaviour should not be. Sheltering from the
rain is something adults already do and children have to acquire, and so is
any practice a village has worked out. With `--practices`:

- A practice is an instruction carrying `metadata.practice`. It leaves the
  shared corpus, and each founder past childhood gets its own copy, gated to
  itself and to the practice's situation (rain, daytime). Children start with
  none.
- A child acquires one through exposures. It sees an adult carry it out
  nearby, is told of it at the end of a conversation while it applies (in the
  rain, not over breakfast on a dry day), or has a lesson at school. Two
  exposures make a habit. Counting one lesson as enough taught every child on
  the first dry morning, before watching or telling could matter.
- School runs in the morning at the schoolyard. Children go there and elders
  teach there (`data/instructions/culture/school.yaml`). Each child gets one
  practice lesson and one piece of news a day.
- New behaviour is written through a lens, as memory is. The learner rewrites
  the practice from its teacher's version, through the same `absorbing` lens it
  hears news through, using `bear.culture.adopt`. The action
  markers are pinned through the rewrite, so the behaviour is conserved and
  only the wording, and what the learner notices about when it applies, change.
  A wary, embellishing child wrote "a danger you refuse to take". A suspicious
  one hedged that it only knew it from being told.
- Each copy records who it was learned from, how and when, so a practice has a
  lineage across generations, as news has.

Without `--practices` a run is identical to one from before practices existed,
checked decision by decision. New actions still come only through
consolidation, which is governed synthesis, never through passing a practice on.

Knowing a practice is not doing it. Children who had learned to shelter chose
it in about 3% of their rainy decisions, because a child's own instructions,
following a parent or playing, outrank it. With `--practice-reinforcement`, a
held practice grows stronger each day it comes up again, seen, told, taught or
used, along a learning curve towards a ceiling below known dangers. That is
habit, and it is what turns a lesson into behaviour. The first version let a
crowd at the inn reinforce each villager once for every other, and every
practice hit its ceiling on the first rainy day. It now counts once a day.

## 6b. Food: work that matters

Work used to be one habit among many, and nothing depended on it. In the
headline run of the last measurement, adults and elders spent 14% of dry
working hours at work. Their most frequent choice in those hours was "You are
exhausted, go home and rest" (129 of 688 decisions), though nobody in that run
was ever tired, and going to work in the morning came tenth (27)
(`experiments/food_economy.py`). A village needs to eat, and feeding it should
take work that someone chooses to do.

The design keeps BEAR's division. Food is physics, like energy and weather
(`hearthwick/food.py`). The response to it is retrieval. Villagers see the
food situation as tags, and instructions they retrieve decide what they do.

- One granary. Everyone eats from it every day, an adult one unit and a child
  half.
- A crop that only grows with work. Tending in spring and summer grows it, up
  to what the fields can hold. Nothing grows by itself.
- A harvest that takes hands. In autumn, work in the fields gathers the crop.
  What is still standing at winter is lost, so a large crop needs more people
  than the farmers alone.
- The harvest is reckoned, not decided. The world used to choose good or poor.
  Now the village brought in what it brought in, and the world perceives the
  result.
- Fields that grow. When even a full crop cannot feed the village for a year,
  adults clear new ground in winter. It is slow, it changes the map, and it
  stops when there is no dry land left.
- Hunger costs energy, not lives. Death is of old age only.

The numbers are set so that the greater village is short. Its founding fields
hold 198 a year, and it eats 224. A good year needs the farmers tending
steadily and most of the village at the harvest, and a good decade needs more
ground. The hamlet has room to spare. That difference is deliberate: a
village's size decides whether food is a problem, not a constant.

Three faults surfaced as soon as food mattered, and each was in the corpus or
the handlers rather than in the economy (SPECIFICATION section 7, faults 39 to
41). The tired instructions applied to the rested. A villager could decide to
go where it already stood. Farmers who heard of the blight kept away from the
fields they needed to save. Now a farmer's answer to the blight is its own
instruction, which is the same knowledge leading to different behaviour by
role.

The time scale is short. A year is eight days, so a ten-day run has one
harvest. Hunger after a poor harvest, clearing, and a better second year need
runs of about thirty days (milestone 5).

## 6c. School, trades and masters

Growing up used to give a villager no place in the village's work. A child who
became an apprentice had no master, and an apprentice who became an adult had
no trade. The design now follows a young villager from school to a trade.

School and apprenticeship are one mechanism at two stages: a placement, which
is a learner, a place and a teacher. A child is a pupil at the schoolyard, an
apprentice works at its master's workplace, and an adult practises its trade.
School runs in every run, as the first placement. Graduating needs the hours
at school as well as the child gate. Qualifying needs skill in one's own
trade, where before skill anywhere would do.

Choosing a trade is retrieval, so it is a BEAR decision like any other. Each
trade is an instruction, and what a graduate leans toward is in soft tags: a
parent's trade, where it has spent its time, what the village lacks, and its
temperament. None of these decides. They tilt the ranking, and a graduate
samples among what it can do, so a farmer's child is likelier to farm and free
not to. Finding a master is the handler's job, and a trade with no free master
is refused, which feasibility re-ranking already handles.

Skill now matters. It grows faster beside one's master, and it scales what
work yields, so experienced farmers carry the harvest and helpers from other
trades do less. Founders begin with the practice their years would have given
them. Only the fields yield anything yet. The other trades' work would need
their own economies (SPECIFICATION section 2.7a).

## 7. Offspring (milestone 4)

Built: births for couples who already exist (SPECIFICATION section 2.7b). A
couple at home together may choose, by retrieval, to try for a child, and the
handler lets it only when they can support one. They must be of age, the
granary not low, the house not full, and their last child at least a year old.
A try succeeds with a chance, once a day at most, so births are spread out as
they would be in a village rather than arriving on the first evening. There is
no pregnancy. The child appears at home, bred from both parents, and starts as
an infant who becomes a child at two.

Built on 2026-09-28: couples forming and building houses (SPECIFICATION section
2.7c). Built on 2026-09-29: death of old age, a lifespan drawn at birth
(SPECIFICATION section 2.7d). Sickness and raids do not shorten it yet.

- Partnership. Affinity grows from shared life, conversations and time near
  each other, never from traits, so mate choice is not selection on genes. A
  man and a woman, at most 6 years apart and not close kin, court, and one
  proposes. The other answers through its own instructions. A new couple
  moves into an empty home, or waits in a family home while the crafters,
  who are the village's builders, fell timber and build them one.
- Genetics. Hearthwick uses BEAR's genetics as they are, with no parallel
  method (`hearthwick/genome.py` only connects them to the `temp_` tags). The
  six genes are declared once, in `data/loci.yaml` as a `LocusRegistry`, all
  diploid. An allele is whatever instructions carry that gene's
  `gene_category` and share a `temp_<allele>` gate, so a gene has as many
  alleles as the library holds and a new one is written, not declared. A
  villager's genotype is a corpus of its alleles' instructions. A child is made
  with `bear.evolution.breed` in locus mode (`bear.genetics.breeding_config`),
  which passes one copy of each gene from each parent and keeps each copy's
  gate and situation. `bear.evolution.express` decides what it expresses, and
  that decides its tags. Children born in the village are bred this way
  (`genome.bred`).
- Founders carry two copies of every gene (`genotype` in founders.yaml). A
  founder's genome is bred with `breed` from two gametes, one copy of each
  gene apiece, so the copies carry BEAR's "a" and "b" labels
  (`hearthwick/genome.py`, `diploid`). What it expresses is its temperament,
  and loading refuses a file where the two disagree.
- Dominance is BEAR's `metadata.dominance` score, 2.0 on every
  instruction of a dominant allele and the default 1.0 otherwise. The dominant
  alleles are gregarious, wary, inquisitive, trusting, easygoing and
  plainspoken. They are the order the founder families fit. Children showing
  a trait their parents lack are all explained by recessive alleles in those
  parents, except two children in the greater village, who were given the
  recessive trait instead (Bryn became reserved, Hilde28 suspicious). No order
  fits every generated family, because the traits were drawn before there
  were genes. Ties would express both alleles, which a villager's tags cannot
  say, so `phenotype` refuses them. A blend mode, where tied alleles are
  merged rather than both expressed, needed `marker_blend` to pass its tests,
  because blending must not destroy markers. BEAR fixed those tests and
  added strict repair in e2b7283 of its development repository, which Hearthwick has run on since 5ebfbb1
  (2026-09-30). No blend mode is built, and ties are still refused. The genetics is a component here,
  not a result, and the behavioural-genetics paper is cited for it.
- `experiments/make_village.py` draws the copies (`genotypes`) on a random
  stream of their own, so regenerating a village changes no other draw.
- A child's store starts empty. Everything cultural arrives through `follow`,
  `play`, overhearing, conversation, school and practices (section 6a).
  Nothing learned is ever written into a genome. What a child inherits is its
  parents' allele copies, and what it learns stays its own.
- Parents, offspring, school and learning form a second channel for knowledge,
  across generations rather than across the village. Part of it runs already.
  Children learn practices by watching adults, by being told, and at the
  schoolyard, where `elder-teach` and `child-school` bring them together. A
  child born in the village joins that channel when it reaches school age.
- Provenance of identity. Every instruction an adult carries is labelled
  authored (stage, role, temperament) or learned (with source facts). Learned
  instructions already carry `layer: learned` and their sources. Genetic is
  added with breeding. The paper can then show what share of each adult came
  from each.
- Finite lifespan. Each villager draws a lifespan at birth (starting range 35
  to 50 in-game years), and sickness and raids can shorten it. Death is
  simulation code, not a BEAR decision. The villager's store is removed and
  survives only in what others kept.
- Founders start at mixed ages, so deaths and elder transitions happen within a
  25-year run and not only in the third generation.
- Names come from a list kept apart from the founders' names, so a child never
  shares a founder's name. Taking names from grandparents is not built.

Checkpoints must carry genomes and family links from the start, or a restart
loses the offspring whose genomes were not saved.

---

## 8. Figures

Built, from `experiments/figures.py` and `experiments/knowledge_flow.py`. None
is assembled by hand, so a figure cannot disagree with its run.

- `fig1_provenance.png`. One event and how it reached the village, with the
  sentence each villager holds.
- `fig2_spread.png`. How many villagers held each event's news over time.
- `fig3_usage.png`. Which instructions were chosen, with those reachable only
  through knowledge in the accent colour.
- `fig4_counterfactual.png`. The action counterfactual by locus.
- `fig5_lens.png`. The absorption counterfactual by locus, against both floors.
- `fig6_drift.png`. Distance from the first-hand wording against tellings.
- `memories.md`. The same news as each villager kept it, with stage, role and
  temperament beside it.

The palette is a validated categorical set (`#2a78d6`, `#eb6834`, `#1baf7a`,
`#4a3aa7` on `#fcfcfb`) that passes the lightness, chroma, colour-vision and
normal-vision checks.

Planned for milestones 4 and 5:

- Growth trajectories. Knowledge, skill and experience over time per villager,
  with stage changes marked, including a late bloomer.
- Sibling divergence. Two siblings with the same parents and different
  childhoods, their learned instructions traced back to what they heard.
- Composition of adults. The share of instructions that are genetic, authored
  and learned, by generation.
- Rumour to tradition. A first-generation rumour held by third-generation
  villagers with no living link to its origin.
- One event traced end to end, from the world's decision through every
  retrieval that followed.

---

## 9. Long runs (milestone 5)

Three seeds, each about 25 in-game years (200 days, three generations).

Budget, from measurement. A ten-day run of thirty villagers takes seven to ten
minutes, about 500 seconds on average, with around 900 model calls. At that
rate a 25-year run is roughly three hours per seed, before births add villagers
and consolidation adds calls. Cost follows conversation, not headcount, so it
moves with anything that changes how much villagers talk. A fault that sent
warnings to people who already knew doubled it. A thirty-day rehearsal with
growth on, on the earlier build, took about 51 minutes across one stop and
resume. This is an extrapolation, and the population will change it.

Runs of this length will be interrupted. Checkpoints are built for that
(SPECIFICATION.md section 2.9). The thirty-day rehearsal was stopped by SIGINT
partway and resumed into one continuous log.

---

## 10. Implementation

### Modules

| Module | Does |
|---|---|
| `sim.py` | the tick loop, world events, witnessing, growth checks, run and stop |
| `brain.py` | a villager's decision, tags, situation text and recall |
| `markers.py` | villager and world marker handlers and name resolution |
| `world_agent.py` | the world's context, recovery and daily decision |
| `food.py` | the granary, the crop, the harvest, and what villagers can see of them |
| `knowledge.py` | facts, stores, witness templates and recall |
| `diffusion.py` | offers, the lens, deduplication and provenance |
| `conversation.py` | turns, speech, and remembering who you talked with |
| `growth.py` | the three tracks and the gates |
| `consolidation.py` | writing, checking and gating learned instructions |
| `checkpoint.py` | saving and restoring a run |
| `events.py` | the event and frame logs, including resume |
| `llm.py`, `embedder.py` | model and embedding clients |
| `server.py` | the live and replay viewer |

### Reused from earlier BEAR projects

| Need | From |
|---|---|
| async brain beside the simulation | `pet_sim` |
| grid, ticks, proximity, fast path without a model | `evolutionary_ecosystem` |
| marker dispatch | `bear.MarkerRegistry` |
| genetics and instruction generation | `bear.evolution` |
| owner gating in one shared corpus | `bear.ownership`, built in BEAR from Hearthwick's pattern (2026-09-27) |

Pitfalls found in the borrowed code, all avoided here:

- Offspring lost on restart. Hearthwick checkpoints all state.
- A chronicler that consumed formatted strings. Hearthwick logs structured
  JSONL.
- A marker named in a prompt but not handled by the parser. Marker lists come
  from the registry, and learned markers are checked against it.
- A slow model call stalled a whole tick. The brain is asynchronous and never
  awaits a model inside the physics tick.

### Event log

`runs/<id>/events.jsonl` holds one JSON event per line, and `frames.jsonl`
holds positions, activity, stage and age per tick. Event types are `roster`,
`day_start`, `decision`, `avoid`, `conversation_start`, `utterance`,
`conversation_end`, `world_event`, `lens`, `diffusion`, `knowledge_stored`,
`knowledge_duplicate`, `growth_held_back`, `stage_change`, `consolidated`,
`consolidation_refused`, `checkpoint` and `resumed`. Every figure and every
number in the paper is built from these logs alone. The viewer replays a run
from them too.

---

## 11. How the build departed from the design

| Designed | Built | Why |
|---|---|---|
| affordance tags from a closed list (`danger:east_road`) emitted by the reframing step | `knows_<kind>_<place>`, from the kind the lens returns | one tag format for all knowledge, and the kind turned out to be where the behavioural change happens |
| trust weighting through an affinity manager | trust acts through the lens | one mechanism rather than two, and measurable by the same counterfactual |
| five seeded facts on day 0 | nothing is seeded, and every fact comes from a world event | seeded facts have no witness, place or time, so their provenance is fiction |
| a lexical store for CPU runs | the shared dense embedder, with BM25 for development only | soft tags require dense vectors (rule 6) |
| every situational condition as a hard gate | graded conditions are soft tags, absolutes stay hard | with hard gates, similarity decided only half of all actions |
| witnessing near the event, then village-wide | weather and festivals village-wide, everything else the five nearest awake | both extremes failed (SPECIFICATION.md faults 13 and 14) |
| gates of K 8, 20, 40 and E 5, 15, 40 | K 3, 6, 12 and E 4, 10, 25, with a skill of 2 for adulthood | the design values were starting points to tune, and these are the current ones |
| consolidation with thinking on | the same model through `bear.evolution`'s generator | kept one model and one client, as decided in section 12 |
| actions, turn-taking and speech effects on the instructions | still Python constants | not yet needed for knowledge flow |
| live instruction editing in the viewer | not built | deferred |

---

## 12. Decisions

Decided:

- A standalone repository, not a BEAR example. The project is
  potentially large.
- Elders are included. Lifespan is finite (section 7).
- A 2D map viewer, live and replayed, from milestone 1.
- One local model for every model job, the same for every villager, so
  personality differences come from instructions and not from a mix of models.
- No forced promotion.
- Knowledge flow is demonstrated first, before generations.
- One allele of each gene is dominant, chosen to fit the founder families.
  Blending would use BEAR's `marker_blend`.
- Every measurement is paired and within-run. No across-run ablation is
  reported as a result.
- Long runs must be stoppable and resumable, for reboots, power cuts and
  sharing the machine.
- Code will be released with the paper, under a licence.

One question is still open. Which licence should the code carry? It should
fit the BEAR commercialisation plan and the provisional patent.

---

## 13. Models

| Job | Volume | Model |
|---|---|---|
| movement, work, routine actions | most ticks | none. Markers are dispatched directly |
| speech | high | Qwen3.8-27B, thinking off |
| reframing what a villager hears | high | Qwen3.8-27B, thinking off |
| consolidation | a few per advance | Qwen3.8-27B through `bear.evolution` |
| retrieval and fact vectors | every decision and fact | Nemotron embed, 2048-d |

Qwen3.8-27B (NVFP4) is served by SGLang on port 8355 (vLLM until 2026-10-13), with four requests in
flight. The embedder is on port 8360. Both are served from
`serving/`. Every request carries temperature 0.8, top-p 0.95
and top-k 20, the values the September runs got. They sent only the
temperature then, and the server filled in the rest from the model card until
2026-10-12.

The reasons for this choice still hold.

- A model that is too small fails the demonstration. In the earlier knowledge
  diffusion work, smaller models could not express role differences. If every
  reframing reads alike, the central result shows nothing. Small models also
  break output formats.
- A frontier model everywhere is unaffordable at this volume and too slow for a
  live map.
- Consolidation is rare and decisive. If rehearsals show weak consolidation, a
  stronger model can take over that one job cheaply.
- One model is pinned for all paper runs, and each run's metadata records it.

A small model is kept only as a development stand-in, never for paper runs.
