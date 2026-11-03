# Memory in BEAR: what Hearthwick needs (proposed)

Written 2026-10-10. Scott wants one BEAR specification for agents' memories and
knowledge, shared by BEAR's applications, Hearthwick's villagers among them.
BEAR's work on it so far is in its `design/items.md`. This document is
Hearthwick's part:
- section 1, what Hearthwick specifically needs, each item tied to how its
  memory works now and what the long runs showed
- section 2, draft sections for the shared specification, on how memories
  form, how they reach behaviour and how they are shared, for BEAR to
  fold in or reject
- section 3, open questions

Nothing here is built. Hearthwick's villagers keep their memories in its own
store (`KnowledgeStore` in `hearthwick/knowledge.py`), not in BEAR. Everything
else a villager does already runs through BEAR: the corpus, retrieval, markers,
generated lessons, ownership and breeding.

## 1. What Hearthwick needs

### 1.1 Many owners, many memories, one query at a time

Every decision and every line of speech asks one villager's memory. The first
long run's last save, on day 559, held 45,294 facts for 418 characters, the dead
among them. The live village held about 87,000 items by day 600.
- Selection by owner before scoring, so a query costs what one villager holds.
  BEAR has this (`Context.select_all`, 3.3 ms at 13,275 items against 32.6 for
  the hard gate, SPECIFICATION-items.md).
- Adding thousands of memories a day without rebuilding the index. BEAR has
  `Retriever.add`, `remove` and `reinforce`.

### 1.2 Kinds, with a standing for each

A memory has a kind, and the kind sets how it fades and how much it matters.
- Knowledge about the world: `hazard`, `sickness`, `rumor`, `news` and
  `opportunity`. These set knowledge tags and can be told.
- A villager's own life: `met`, `did`, `told` and `lived`. These are never told
  as news and set no knowledge tag. They reach behaviour by recall.

Hearthwick needs each kind to map to a salience, a half-life and an importance:
- A rumour or a sickness fades within a year of the run's own length, and a
  hazard within two (`news_fades` today).
- Family and lived memories hardly fade, and some matter for good: "My wife
  Katrin died in the night" should never sink below a chat about the weather.
  That needs the importance floor of `design/items-importance.md`.
- Time is in ticks, and a year is 8 or 28 days depending on the run, so
  half-lives are set per run from the year's length.

### 1.3 The same news is one memory

"The well is bad" and "the water at the well turned" are one memory. Hearthwick
treats news as known already if the holder has anything from the same root
event, or anything within 0.85 cosine of it.
- Witnessing it again reinforces the memory and restarts its clock.
- Hearing it again counts in Hearthwick's own metadata but does not restart the
  clock. If hearing kept news fresh, warnings kept one another alive (the open
  run's fear loop, SPECIFICATION-talk.md section 6).
- BEAR has this as `Retriever.reinforce(ids, now, boost=0.0)`, in one batch per
  tick.

### 1.4 Every memory knows where it came from

A fact carries its root event, the memory it was retold from, who told it and
how many tellings it has passed through. "Why does Nell believe this?" must stay
answerable from the record.
- A retelling is the listener's own item, with the teller's item as its parent.
  Its words differ, since the listener rewrites what it hears through its own
  lens (`hearthwick/diffusion.py`). That is the lens result the paper reports.
- Carried tags: the subject (`person:katrin`) and `family`, never the teller,
  which would pile up down a chain of retellings.
- BEAR has parents, root and carried tags in `bear.items.respond`.

### 1.5 Memory reaches behaviour three ways

1. **Knowledge tags.** A held fact sets `knows_<kind>_<place>`, which admits
   the authored instructions gated on it, such as `knows-warn-about-blight`.
   Only salient memories should set them, through `min_salience` with the
   importance floor.
2. **Recall.** The two memories most relevant to the moment go into the
   decision's query and into speech, with news first and experiences filling
   the rest. Hearthwick also asks tagged questions, such as the family question
   or what a villager remembers of its listener. Significance should weigh
   recall, as BEAR's score already does for items.
3. **Lessons.** A villager writes lessons as it grows up, with action markers
   (`hearthwick/consolidation.py`). A lesson should be a response item: owned by
   its author, with its source memories as parents, a half-life from them and
   an importance floor if they matter. Hearthwick, not the retriever, resolves
   its markers, so an item has to be able to carry them.

### 1.6 Don't say what the listener already knows

In the second long run, Ilsa warned others about sickness more than 2,100 times
in 120 days, and 5,220 of the 5,265 facts her conversations passed on were
already held by the listener. Two causes, both in what a villager says:
- After a conversation, each side offers its top news, hazards first, whatever
  the topic and whether the listener has it. Only traveling storytellers check
  what the listener has heard (`Diffuser._to_tell`).
- A warning starts a conversation even when the listener already knows.

BEAR's importance design puts novelty at the moment of speaking, not in the
memory, and Hearthwick agrees. A villager shouldn't read the listener's mind,
though. It should go by what it remembers telling that person, or hearing from
them.
- Villagers remember their conversations ("I talked with Gorm at house 8
  about...", kind `met`), but not what they passed on. The vocabulary has a
  `told` kind that nothing records yet.
- Recording a `told` memory when news is passed on, tagged with the listener and
  the news's root, lets the speaker ask its own memory before offering it. That
  is a tagged query over one owner's items, which BEAR has.

### 1.7 Forgetting, and the dead

- A villager forgets by fading. A faded memory stops driving behaviour but is
  kept, can still be recalled and retold, and stays in the record.
- When a villager dies, its memories should leave the live index for speed and
  stay in the audit and the log for analysis.

### 1.8 Runs that can be checked

- Every memory operation in the audit's delta log, so a run's memory at any tick
  can be rebuilt and checked.
- A memory state that checkpoints and restores exactly. Hearthwick saves every
  in-game day and resumes from the save.
- Embeddings that don't depend on what else was in the batch. With a cache
  directory, BEAR's add and remove equal a rebuild exactly. Without one, a
  service embedder's vectors move by up to 0.0015.
- The paper profile unchanged. Memory as items goes behind a switch, and a run
  with it off must replay decision for decision.

## 2. Draft sections for the shared specification

### 2.1 How a memory forms

- **Perceived.** The agent witnesses something. Its kind comes from the event,
  and its salience and importance from the kind.
- **Told.** Someone tells the agent something. The agent's copy is its own item,
  with the teller's item as its parent, and its words may differ. Whether it is
  kept at all is the agent's choice.
- **Lived.** The agent's own life: a conversation, a task done, a marriage, a
  loss. Never passed on as news. Some of it matters for good.
- **Reflected.** The agent writes something from what it holds: a lesson, a
  summary or an opinion. A response item, with its sources as parents.
- **Stated by a user.** For a personal assistant: "I'm allergic to penicillin."
  Its importance comes from its category or its wording, as the importance
  design leaves open.

### 2.2 How memory reaches behaviour

- **Admission.** Salient memories set tags that admit instructions. Below the
  floor, a memory stops admitting anything but is still held.
- **Ranking.** Significance (importance as a floor on faded salience) weighs a
  memory's score. Similarity still leads.
- **Questions.** An application asks tagged questions of one owner's memory,
  selected before scoring: what do I remember of this person, of my family, of
  this place.
- **Lessons and plans.** An agent's own instructions are memories too. They
  fade with the memories behind them unless those matter for good.

### 2.3 How memory is shared

- **What may be told** is the item's audience and handling, as BEAR's content
  design defines them, enforced where the item is stored.
- **What is worth telling** is judged when speaking, from the speaker's own
  memory of the listener: what it remembers telling them, or hearing from them.
  Never from the listener's store.
- **What the listener keeps** is its own item, owned by it, with provenance back
  to the teller.
- **How far it goes** shows in the hop count and the root, so spread can be
  measured and, if an application wants, limited.

## 3. Answered in the shared specification

BEAR folded section 2 into its design for agents' memory (1476b85 in its
development repository), with the personal assistant's case added. Not built, and with Scott. Its
organising rule: a quantity that varies by observer or by moment is worked out
at query time and never stored, and everything else is stored on the item.
Salience and importance are stored. Novelty, support, spread and consensus are
worked out when asked, since they belong to a population and would go stale on
one member.

- **Where importance comes from.** A map by kind and relation, as Hearthwick
  proposed, is enough. Inferring it from wording goes behind a switch, and is
  not trusted until measured against labels written blind.
- **Support.** Worked out, not stored. Distinct sources and spread come from the
  root and hop counts Hearthwick already records. Hearthwick measures the cost
  at the live village's 87,000 items, and caches only if it is too slow.
- **Superseding.** Hearthwick asserts it, and BEAR does not guess it. BEAR's
  `supersedes` link already drops the older item from what is retrieved and
  keeps it stored, so "the blight has been cut out" can end "a blight is on the
  crop" once Hearthwick asserts the link.
- **The dead.** They fade like anyone else, by owner, not by subject. A dead
  villager's own memories leave the live index, since nobody retrieves them.
  Other villagers' memories of her stay, owned by them. A daughter's memory of
  her mother is what the importance floor is for.

A half-life per run needs no BEAR change either. It is set per item, and a
query gives the default for items without one, so 8-day and 28-day years need
only Hearthwick's map of kinds. The BEAR changes left are `adjust` and
`importance`.

## 4. What changes in Hearthwick

When the shared specification is agreed and built:
- the memory store moves into BEAR items behind a switch (the rebuild in
  SPECIFICATION-items.md). Built 2026-10-11 behind `bear_memory`
  (`hearthwick/memory.py`, section 5)
- lessons become response items (SPECIFICATION-warnings.md)
- villagers record what they told whom, and check it before offering news
  (1.6). Built 2026-10-10 behind `told_memory`, in today's store
- `news_fades` is replaced by salience and half-life on items, and checked to
  give the same knowledge tags first

## 5. Stage 2 as built (2026-10-11)

`hearthwick/memory.py`, behind `bear_memory` (`--bear-memory`), on BEAR's
development repository at 8e26162 or later.
- **One memory retriever for the village.** Each fact a villager holds is also
  a BEAR item it owns, with the class `fact`, its kind, its root and parent,
  and the tags `news` or `experience` for selecting. Decisions never see these
  items, since they don't carry BEAR's item facet.
- **Fading by kind.** An item's half-life is its kind's fading span in ticks of
  the run's year: a year for a rumour or a sickness, two for a hazard, none for
  the rest. Witnessing a fact again reinforces its item, batched until the
  next question.
- **What BEAR answers.** The knowledge tags come from the villager's news items
  above `min_salience` 0.5 when `news_fades` is on, and from all of them when
  it is off. Recall asks BEAR for news first, then experience, by similarity.
- **What Hearthwick keeps.** Its own record of each fact, for deciding what is
  the same news, for what a villager brings up in talk, and for the log.
- **Restoring a checkpoint** indexes every fact in one build.
- **Without the embedding service** the memory index uses BEAR's hash vectors,
  since BEAR fades items only in a dense index, and recall falls back to
  recency as before.

Parity was checked before anything was allowed to change:
- `tests/test_bear_memory.py` gives the same knowledge tags as Hearthwick's own
  store with fading on and off. That holds at the exact tick a fact stops
  counting, after a fact is witnessed again, for one villager against another,
  and across a checkpoint.
- `experiments/replay_fingerprint.py --ticks 144`, with the embedding service,
  gave identical decisions for a whole in-game day with and without
  `--with bear_memory`, with `news_fades` off and on (500 lines,
  90b674e3f38c32c5 in all four).

Lessons as items that fade with their news followed on 2026-10-12 (stage 3,
SPECIFICATION-warnings.md section 2). So did a gene for how long a villager
keeps news (Scott, 2026-10-12), behind `memory_gene`, which scaled the
half-life of each fading memory by the allele a villager expressed. The
paper's runs had it off, and this edition leaves it out (README). Fading in
recall, importance and superseding come next.

## 6. Lessons that last (2026-10-13)

With short warnings (SPECIFICATION-warnings.md section 10) news fades in days,
and a lesson that rests on news faded with it, since a lesson takes the
shortest span among its sources. In the fourth long run, at day 131, lessons
were chosen in 0.6% of decisions against 2.2% in the third run at a like
point, and only 29 of 66 were ever chosen, against 49. A lesson learned on
growing up dropped out of decisions within about a week.

Scott (2026-10-13): in some sims a lesson should fade unless it is
reinforced, and in others not, but in this one lessons should at least last
years. So `lasting_lessons` gives a lesson the span its news had before short
warnings, in years of the run: one for a rumour or a sickness, two for a
danger, and two for anything that can come here. A lesson resting on no
fading news does not fade, as before. The news itself keeps its days, so a
warning still passes in a week while the lesson drawn from it stays. A lesson
still strengthens whenever its news is witnessed again
(`MemoryIndex._lessons_by_source`), so one whose danger keeps coming back keeps
its strength.

It needs `fading_lessons`, which `--lasting-lessons` turns on with
`--bear-memory`. Off in the paper profile and unless asked for.

Which lessons fade and which persist could later be declared by each lesson,
as BEAR items declare the rest of what they are. For now one switch sets it
for the whole run.

## 7. What leaves the live index (2026-10-16)

By day 719 the sixth long run's village had 104 living villagers and 64,654
memories in its live index. 18% belonged to the dead, whom nobody asks
anything. 61% of the living's memories were of dangers, which under short
warnings fade below half their strength in a week, but every faded one stayed
in the index, so each lookup grew more costly every year. Restored without the
model, a daytime tick took 1.0 seconds, against 0.12 for the founders' village
of 30 on day 0, and the numerical library spread each lookup over all 28 of
WSL's threads, about eight cores busy for nothing (four threads were faster).

The shared specification already allows both changes: a dead villager's own
items leave the live index (section 5.4 of `design/agent-memory.md`), and
forgetting is fading, with BEAR's log keeping what the live index drops.

- **`forget_the_dead`.** Once a day, the memories a dead villager held leave
  the live index. Other villagers' memories of them stay, owned by them.
- **`forget_faded`.** Once a day, a memory below a twentieth of its strength
  (`FORGET_BELOW`), counted from when it was learned or last lived again,
  leaves the live index: a danger about a month after it was last lived, a
  rumour after about two weeks. It had stopped setting knowledge tags at half
  its strength, so only recall loses it. A memory of a kind that never fades
  never leaves. One lived again comes back with its clock restarted
  (`MemoryIndex.readd`). Hearing it again does not restart its clock, as before.

Nothing is deleted. Each villager's own record of every fact stays, in its
store and in the checkpoint, and a resumed run takes out again what had left,
by the same rule. BEAR removes items with `Retriever.remove`, which rebuilds the
index from what is left. With either switch on, the embedder keeps every
document's vector once computed (`ServiceEmbedder.keep_documents`), so a
rebuild reads them back rather than embedding tens of thousands again, which
would take a minute and move each vector a little with its batch.

Restored at day 721 with both on, the live index held 17,459 memories, and a
daytime tick took 0.50 seconds at about one core, against 1.0 seconds at about
eight. Long runs also take the README's thread limits now
(`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`).

Both need `bear_memory`, which their flags turn on (`--forget-the-dead`,
`--forget-faded`). Off in the paper profile and unless asked for.

## 8. Telling only what the listener has not had (2026-10-16)

In the fifth long run a lesson to mention a birth at house 13 was chosen 3,132
times, told to the same neighbours again and again. Warnings already went only
to someone without the news, by what the warner remembers sharing (told
memory), but talk did not ask.

**`novel_telling`.** A talk whose topic names a place the speaker holds news
of goes only to someone who has not had that news from the speaker
(`markers._novel`, by the same place matching warnings use). A topic that
names no place, or a place the speaker has no news of, is talk rather than
telling, and goes to anyone as before. It needs `told_memory`, which
`--novel-telling` turns on. Off in the paper profile and unless asked for.

**BEAR's change records (2026-10-17).** BEAR records every change to its
items, adds, reinforcements and each rebuild's statement of the whole set, for
its audit to write out, and only the audit takes them
(`Retriever.take_item_deltas`). Nothing in Hearthwick audits, so they piled up
for a whole run: the seventh long run's process held 12.2 GB by year 17, most
of it the live index restated at each daily trim. The sixth run grew the same
way, more slowly. A day's start now takes them from both retrievers and lets
them go. Nothing reads them, so no decision changes.

## 9. News that ended or never came (2026-10-17)

Fading takes care of news that is merely old. It does not take care of news
that turned out to be over, or false, and a lesson resting on such news
lasted years with `lasting_lessons`. In the fifth long run a lesson to warn
that "raiders are less than a day away" was chosen 2,717 times, years after
any raiders. The shared specification leaves this to the application: BEAR
records and honours what the application asserts, and never guesses
(`design/agent-memory.md` section 5.3).

**`news_ends`.** A danger wearing off is news. When a sickness passes
(`sickness_passed`) or a raided place is safe again (`danger_passed`), whoever
is near witnesses it, as when the blight is cut out (`blight_cleared`), and
it is told on like any news. An ending marks down what its holder knew of
that danger at that place from before it, and old news of a danger its holder
already knows has ended is marked down as it arrives (`knowledge.ENDINGS`).

**`false_alarms`.** Word of a danger from beyond the village that can come
here (short warnings) has a week. If by then its holder has neither seen nor
heard of it arriving, it is marked down: raiders for word of fighting, a
sickness for word of one. Wolves have no event, so word of them never comes
true. Each is judged once (`MemoryIndex.false_alarms`, `DEADLINE_DAYS`).

To mark down is to take the item's strength away with BEAR's `adjust`, and,
with fading lessons, the same for every lesson resting only on facts so
marked. BEAR's `supersedes` was the other way, but it acts only when the old
and the new item come up in one retrieval, which a lesson and its sources
never do. Marked-down facts leave the live index at the next daily trim
with `forget_faded`. A resumed run marks down again by the same rules, since
restored items start at full strength.

Both need `bear_memory`, which their flags turn on, and `false_alarms` needs
`short_warnings`. Off in the paper profile and unless asked for. Both are in
`--profile illustrative` (README section 6).

## 10. Routine memories fade, and the same talk is had once a day (2026-10-17)

The first health check of the seventh long run (`experiments/health_check.py`)
found two things a healthy village should not do.

- **The live index still grew.** With the dead's and the long-faded memories
  leaving it, it held 1,210 memories in year 0 and 13,145 in year 17, and per
  villager from 80 to 148. What stayed were the kinds that never fade: every
  talk a villager had ("I talked with Hilde at house 13"), what it did or
  told, the chances that came up, and the news of the day.
- **The same talk again and again.** An elder told the same child "a story
  from the old days" 138 times in year 8, about five times a day, and other
  pairs repeated a topic 50 to 150 times a year. `novel_telling` passes such
  topics, since they name no place and tell no news.

**`routine_fades`.** Memories of talk, of what a villager did or told, and of a
chance that came up fade over a year, and the news of the day over two
(`ROUTINE_FADE_YEARS`), short warnings or not. With `forget_faded` they leave
the live index some four half-lives on. It needs `bear_memory`, which its
flag turns on.

**`talk_once_a_day`.** The same two villagers talk about the same topic at
most once a day (`Conversations.talked_today`, `markers._fresh`). A checkpoint
falls between days, so a resume loses none of it.

Both are off in the paper profile and unless asked for, and both are in
`--profile illustrative`.

## 11. A lesson's urge ends once its goal is met (2026-10-17)

The three trial runs of `--profile illustrative` (seeds 1 to 3, ten years each,
`results/illustrative_trials/`) passed every health check but one each. Two
of those were the same fault, a villager caught in a lesson it wrote.

- Seed 1, year 6: an apprentice chose its own warning lesson 121 times in
  about eight hours, twice a tick, and warned whoever was near 114 times,
  two of the same neighbours 13 times each. Its topic named no place, so it
  was about anything the apprentice knew (`markers._about`), and someone near
  always lacked something.
- Seed 2, year 9: an elder chose its lesson to watch the stranger at the inn
  every nine or ten ticks for an afternoon, twice, following whoever sat
  there.

A limit of once a day would have stopped both, but Scott (2026-10-17): "rather
than just hard limiting lessons to once a day, for one-shot tasks, the urge to
do it should just end once they accomplish their goal unless something
reactivates it."

**`lessons_satisfied`.** A lesson is a BEAR item whose strength is its urge
(`fading_lessons`). A lesson whose every action is one-shot (`ONE_SHOT`:
telling, warning, going, following, keeping away) has met its goal once the
villager has carried it out to its end, and its strength goes to nothing
(`MemoryIndex.satisfied`, from `Simulation._finish`), so it leaves decisions.
It rests by BEAR's `Retriever.rest`, which also marks when it rested.
Something rekindles it to full strength (BEAR's `Retriever.wake`):

- the same kind of event at the same place as the news it rests on, seen or
  heard, from after that news: a new raid on the east road wakes a lesson
  about raiders there (`MemoryIndex.rekindled_by`)
- its news lived again, which already renewed it
- for a lesson resting on no news, its own situation coming round, which is
  the next day (`MemoryIndex.new_day`)

A lesson marked down because its news ended or never came rests the same way,
and wakes the same way. Work, rest, gathering and clearing are habits, not
one-shot goals, and never rest. A resumed run finds the resting lessons as
the checkpoint kept them, with BEAR's resting mark in their metadata. It needs
`fading_lessons` and a BEAR whose items rest (BEAR v0.3.0 or later). Off
in the paper profile and unless asked for. On in `--profile illustrative`.
Section 12 replaces the guess from a lesson's actions with what the lesson
declares.

The two cases were the worst of many. The health check now counts, for each
villager and day, the times it chose one of its own one-shot lessons, and
flags more than 12. All three trials flag it. Seed 1 had 93 villager-days over
12 in its ten years, seed 2 had 227 and seed 3 had 58. In seed 2 one villager
chose the same lesson 52 to 67 times a day in every year from the second.
Even seed 1's first two years reached 29 times in a day. A trial of
`lessons_satisfied` (`results/satisfied_trial/`), seed 1 for those two years,
flags nothing. No villager chose one of its one-shot lessons more than twice
in a day, and the lessons were still used, about once on each day
(`experiments/lesson_use.py`).

The third flag, seed 3's live index growing, was not a fault: per villager it
went from 69 memories to 90 between years 5 and 9, while routine news, which
leaves the index only after eight or nine years, was still nearing its level.
The health check now judges the index per villager.

## 12. A lesson declares what it answers, how often it recurs and how long it lasts (2026-10-18)

The 56-day trial of `lessons_satisfied` (`results/satisfied_trial/`) ended the
loops, but showed what was left of the guessing. Three things about a lesson
were guessed after it was written:

- **What it answers.** Its sources were the facts its words were at least
  0.5 similar to. Peder wrote "Gisla claims the grain in the mill sacks is
  bad" when Gisla had said it of the well, so no fact was close enough and the
  lesson answered nothing.
- **How often it acts again.** From its actions, and a lesson answering
  nothing woke each day. So Peder warned of bad grain on 18 of the 28 days
  after, weeks after the grain was cleared out. In the illustrative trials 37
  of 225 one-shot lessons answered nothing. A daily habit written after a
  storm would have been the opposite case, resting until the next storm.
- **How long it lasts.** As its sources do, so a lesson with none never faded.

Scott (2026-10-18): "When a lesson is written we should make sure it's clear
what event it is linked to and how often it should recur and persist." He
chose to build it in BEAR (BEAR's `design/declared-instructions.md`).

**`declared_lessons`.** The lesson writer (BEAR's `generate_with_llm`) is shown
the facts it writes from, numbered, the same facts as its formative terms. Each
lesson declares three things beside its words:

| field | what the writer chooses | what Hearthwick does with it |
|---|---|---|
| `about` | the numbers of the facts it answers, or `[]` for a general rule | its sources, the item's parents. No similarity guess |
| `recurs` | `each_time`, `each_day` or `always` (`memory.RECURRENCES`) | how it rests and wakes |
| `lasts` | `news`, `season`, `year` or `life` (`memory.LIFETIMES`) | its half-life (`MemoryIndex.lifetime_of`) |

How it rests and wakes, by `recurs` (`MemoryIndex.recurs_of`):

- `each_time`: rests once carried out, and wakes when the same kind of event
  happens again at the same place, or its news is lived again (section 11).
  One answering no news cannot wait for its event, so it recurs each day.
- `each_day`: rests once carried out, and wakes on the next day
  (`MemoryIndex.new_day`, by BEAR's `due`), never by an event, so at most once
  a day.
- `always`: a habit, and never rests.

How long it lasts, by `lasts`: `news` as the news it answers (the shortest
span among its sources), `season` a quarter of a year, `year` a year, `life`
never fading. Each is the lesson's half-life, since a lesson below half its
strength leaves decisions. A lesson declared to last as its news but
answering none lasts a season.

A declaration outside its vocabulary is ignored, and an omitted `about` falls
back to the similarity guess, so a lesson that declares nothing behaves as in
section 11. The `consolidated` event records each lesson's `about`, `recurs`
and `lasts`, and what it declared. Needs `lessons_satisfied`. Off in the paper
profile and unless asked for. On in `--profile illustrative`.

A 56-day trial (`results/declared_trial/`, seed 1, the same days as the trial
of section 11) flags nothing. All 21 lessons declared all three things: 17
recur each time their event happens and 4 each day, 18 last as their news.
Only 2 answer no news, both general rules about resting at night, and every
lesson about news cites it. No villager chose one of its lessons more than
twice in a day.
A second, of seed 2, whose earlier trial had the worst loop (one lesson
chosen 391 times in 16 days, up to 59 in a day), also flags nothing. Its 24
lessons all cite the news they answer, and none was chosen more than twice in
a day.
