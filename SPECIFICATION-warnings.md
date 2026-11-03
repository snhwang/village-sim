# Warnings that fade, and tell something new (proposed)

Proposed 2026-10-10, and revised the same day to go through BEAR's
significance, from the second long run (`results/long_run_v2`). Not
built. It goes behind its own switch, off in the paper profile, and is not
turned on in a run already going.

## 1. What goes wrong

Since consolidation shows the model marker signatures (dae4771), villagers keep
their lessons about the news, and a lesson to warn others now acts. In the
second long run, Ilsa wrote herself this on becoming an apprentice on day 5:

> The traveler on the east road spoke of sickness spreading through the valley. Go to the inn and warn the storyteller and any others there that the danger is closer than they think. [!warn(target=nearby, topic=sickness in the valley)]

By day 124 she had chosen it more than 2,100 times, about 18 times a day,
warning 40 people and Gorm alone 277 times. Of the facts her conversations
passed on, 23 were new to the listener and 5,220 were already held. A first
count, to be redone by the check in section 5.

Two things are missing:
- **Time.** The lesson is not tied to the news it came from, so it lasts as
  long as she does. The news was a `sickness` fact, which `news_fades` (section
  6 of SPECIFICATION-talk.md) stops from driving behaviour a year after it was
  learned or last witnessed. About three in four of her warnings came after
  that year, if she never witnessed the sickness again.
- **Whether there is anything to tell.** Nothing in a warning asks whether the
  listener already knows. The authored warnings have the same gap.
  `knows-warn-about-blight` is among the instructions that most often win the
  moments a couple could have chosen a child, in both long runs
  (results/long_run/REPORT.md, section 3).

## 2. A lesson is a memory with a significance

Scott, 2026-10-10: memories go through BEAR, and each has a significance that
gives it priority, adjusted by several factors, time among them. BEAR's items
already work this way (BEAR's design/items.md, section 4):
- An item has a base `salience` from 0 to 1, set by whoever writes it.
- It has a half-life. Its effective salience, `s × 0.5 ** ((now − reinforced) /
  half_life)`, multiplies its retrieval score, so a fading memory sinks while
  similarity still leads.
- `min_salience` drops an item below a floor before scoring, so a faded one
  stops acting while it is still held.
- `reinforce` restarts the clock and may raise the salience.
- A response is an item made from the items retrieved for it
  (`bear.items.respond`). The design names "an instruction an agent writes"
  among them, which is what a lesson is.

So a lesson becomes a response item.
- **Owner.** The villager who wrote it, as now.
- **Parents.** The facts it rests on: of those handed to the model, the ones
  whose text is close to the lesson's (by the embedder, above a floor set from
  the long runs' lessons).
- **Significance.** Taken from its parents, so a lesson from a family event
  weighs more than one from a rumour. BEAR's design gives 1.0 for a family
  event, 0.6 for news and 0.4 for a rumour as examples. The values are
  Hearthwick's to set.
- **Half-life.** The shortest among its parents of a fading kind: a year for a
  rumour or a sickness, two for a hazard, in the run's own years. A lesson whose
  parents do not fade, such as one about where to sleep, has none.
- **Reinforced** when one of its parents is witnessed again, which brings back a
  warning about news that has come back. Hearing it again does not.

The factors that move a lesson's significance:
- time, through the half-life
- reinforcement, when its news is witnessed again
- importance, a floor that does not fade, for a lesson whose sources matter
  for good (`design/items-importance.md`), such as one written from a death in
  the family

Usefulness is not one of them. An earlier draft lowered a lesson whose warnings
told nobody anything new. BEAR's design for importance argues against it,
and Hearthwick agrees. The lesson may be the most important thing the villager
holds, and lowering it would also stop the villager acting on it herself.
Repeating what everyone knows is a problem of speaking, so section 3 handles it
where the villager speaks, and the lesson's standing is left alone.

This needs Hearthwick's memories to be BEAR items first, since a lesson's
parents must be items. That is the rebuild in SPECIFICATION-items.md, whose BEAR
side is built. A lesson is one slice of it. The shared memory
specification in BEAR is where the rest is settled
(SPECIFICATION-memory.md has Hearthwick's part).

In BEAR, designed and not built, both with Scott:
- `adjust` raises or lowers salience, by a factor (`scale=`) or an amount
  (`delta=`), without counting as recency, recorded in the audit with before
  and after (ca8810d in BEAR's development repository). Scott wants
  significance to move both ways. `reinforce` stays its own act, since it says
  the thing happened again.
- `importance`, a floor under faded salience that does not decay, set rather
  than nudged (0d43dfe in BEAR's development repository).

BEAR's advice for any adjustment Hearthwick makes:
- scale rather than subtract, since a fixed amount shrinks with the fade
- keep a floor above zero, or a lesson can never come back
- adjust once a day in one batch from counted statistics, never per event
- adjust only the ids named, never a lesson's parents

The BEAR changes need Scott's approval,
since Hearthwick uses BEAR's mechanisms rather than building its own.

**Built 2026-10-12 behind `fading_lessons`** (`--fading-lessons`, which turns
on `bear_memory`), on BEAR's development repository at 8e26162 or later:
- **Sources.** A lesson rests on the facts it was written from whose text is
  at least 0.5 similar to its own (`memory.lesson_sources`). Measured on the
  second long run's lessons: a lesson about news is 0.6 to 0.69 from its
  source and about 0.3 from the rest, and a lesson about where to sleep is
  0.4 or less from everything, so it rests on nothing and never fades.
- **The item.** `memory.as_lesson` makes it with BEAR's `item`, its sources as
  parents and the shortest fading span among them as its half-life. Its own
  gates stay hard gates beside BEAR's item facet and owner tag. It is not
  made with `respond`, which would make it demand its parents' class `fact`.
- **Decisions** open the item facet in `gate_tags`, so the query's words are
  unchanged, and pass the clock with `min_salience` 0.5. A lesson sinks as
  its news ages and drops out one half-life after the news was learned or
  last witnessed.
- **Witnessing a source again** reinforces the lesson too, at the next
  question asked of memory.
- **Importance** is not used yet. Lessons from a villager's own life rest on
  memories that do not fade, so they do not fade either.
- The consolidated event records each lesson's sources and half-life.

With it off, and with `bear_memory` alone, a run is unchanged decision for
decision (`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5).

## 3. Don't say what the listener already knows

The fault is in what a villager says, in two places:
- After any conversation, each side offers its top news, hazards first,
  whatever the topic and whether the listener has it. Only traveling
  storytellers check what the listener has heard (`Diffuser._to_tell`).
- A warning starts a conversation even when the listener already knows.

A villager shouldn't read the listener's mind. It goes by what it remembers
telling that person, or hearing from them.
- When a villager passes news on, it records a `told` memory, tagged with the
  listener and the news's root. The kind exists in the vocabulary, and nothing
  records it yet.
- Before offering news, the speaker asks its own memory whether it has told
  this listener about this root, or heard it from them. If so, it offers
  something else, or nothing.
- A warning is feasible only if the speaker has news on the topic it hasn't
  told the target. `target=nearby` picks the nearest person it hasn't told. A
  warning that isn't feasible is passed over, and the next candidate is chosen,
  as when the house is too full for a child.

This applies to authored and learned warnings, and to the news offered after
any conversation. Talk itself is left alone, since talking about what both
know is still conversation. This part needs no BEAR change.

**Built 2026-10-10 behind `told_memory`** (`--told-memory`). The record is
`Diffuser.told`, kept per villager rather than as memory entries, since it
is a count of who heard what, not something a villager recalls or retells,
and it is saved with each checkpoint. A storyteller, which used to check
what its listener had heard, goes by the record too. The `listener` target
of a talk marker does the same. With the switch off, a run is unchanged
decision for decision (`experiments/replay_fingerprint.py`).
`experiments/told_memory_check.py` counts what conversations pass on with
it off and on, without the model (results/told_memory_check.md). Over one
in-game year of the paper-profile village, the share of facts passed on that
the listener already held was the same either way, about 92%. Facts new to the
listener rose from 223 to 485, but so did everything passed on (2,732 to
5,784), and warnings rose from 467 to 2,373.

The reason is the rule itself. The old check let a warner read the listener's
store, so it never warned someone who already knew. A villager with told
memory knows only what it has told or heard, and most listeners had heard the
news from someone else. That is the cost of not reading minds. It is why a
warning has to be cheap (section 8), and why how often a villager warns needs
fading as well (section 2).

An earlier version of the check, committed in 63b6e1a, reported 62% fewer
repeats. It was wrong: without the model, everything conversations passed on
waited for the end of the run, so it measured the rule on the end-of-run
village. The check now lets that finish every tick, as a run with the model
does (f2568aa).

## 4. What it should change

- Ilsa's lesson would have stopped about a year after she heard the news, and
  before that she would have warned only people she hadn't told.
- Warnings become rarer, and the moments they took go to work, children and
  talk.
- What each warning passes on is mostly new, so news should still spread, and
  may spread further, since a warning seeks out someone not yet told.

## 5. How to check it before a long run

- A replay of the second long run's logged decisions, from its checkpoints,
  with the switch on and off: how many warnings would be passed over, and what
  would be chosen instead. No model calls.
- Short forks from one checkpoint of the second long run, a few seeds each way,
  for what the replay cannot show: how far news spreads, and births a year.
- Measures: warnings per villager-day, the share of facts told that were new to
  the listener, how far each piece of news reached and how fast, and the rate
  of choosing a child.

## 6. Switches

`told_memory` (section 3) is built. The lesson as a memory (section 2) comes
with the items rebuild, under its own switch. Both are off in `SimConfig` and
in `PROFILES["paper"]`, and listed in `ADDABLE`. Unlike the talk and leisure
switches, which are on by default from the command line and were left on when
the second long run was first started, both are off from the command line
too, and turned on with a flag (`--told-memory`), so a run gets them only when
asked.

## 7. Open questions

- **Witnessed tellings** (2026-10-11). A villager could also
  remember what it saw being told to someone, by anyone within earshot. It is
  still the villager's own memory and never reads another's, and it covers the
  third-party tellings that make a warner repeat what a listener heard
  elsewhere. It sits between told memory and reading the listener's store.
- **Is the redundancy a finding?** About 92% of what villagers pass on, the
  listener already holds, with or without told memory. Real gossip is
  repetitive, and a village that passed on only new facts would be less
  plausible. Quick warnings and fading bound its cost without hiding it.
- **Checks of per-tick state should check the tick finished.** A no-model
  step never yields to the event loop, so a measurement that does not let the
  tick's work finish reads the end-of-run village and looks like data.
- Should hearing news from many people keep it fresh, as witnessing does? Now
  only witnessing does, so a rumour nobody sees again fades however often it is
  retold.
- Should the authored warnings move to significance too, which would replace
  `news_fades`?
- Are a year for rumours and sickness, and two for a hazard, the right spans?
- Should a speaker hold back news it has told someone only for a while, so it
  can remind them later, or for good?

## 8. How much a villager does to tell: proximity and urgency (proposed 2026-10-11)

In the second long run a warning took up most of a villager's day. A warner
might walk up to 18 ticks to reach its listener, then talk for up to 9, and the
listener stopped work for the whole conversation. By year 10 warnings were 45%
of all decisions and fieldwork 1.1%, the harvest fell short of the village's
need, and the granary was empty at every year's end from year 7
(results/long_run_v2/long_run_report.md, read to day 308). Scott: a
villager should be able to warn and work in the same day, and how much it does
to tell should depend on how important the news is. A forest fire moving toward
the village is told in a dedicated way.

**Urgency is worked out when a villager decides, never stored**, by the rule of
BEAR's design for agents' memory, since it depends on the moment and on who
is listening. It comes from:
- the importance of the news's kind, stored on the memory: a danger to life
  (raiders, fire) high, sickness lower, ordinary news and opportunity low, a
  rumour lowest
- how fresh it is, which is the memory's faded significance now (stage 2)
- how near the danger is: here in the village, or from afar (`afar_news`), and
  whether it is still going on in the world (`trouble_at_<place>`)
- who is at risk: a listener whose home or work is where the danger is

**Three levels of effort:**
1. **Urgent: raise the alarm.** It goes ahead of work. The villager tells
   everyone within earshot at once, then goes to find those at risk, such as
   its family or whoever works where the danger is, and their work stops while
   they hear it. Each telling is recorded in told memory.
2. **Ordinary news: a quick word.** Told only to someone already within the
   radius villagers count as near, in one tick, and nobody stops working.
3. **Old, faded or far-off news: no warning at all.** It comes up only in
   ordinary conversation.

**Level 2 is built** (2026-10-11, behind `quick_warnings`, `--quick-warnings`).
A warning goes only to someone awake within the radius villagers count as
near, and `Diffuser.tell` passes the warner's news on the topic in the same
tick, through the listener's lens as in a conversation, with no conversation
started, so neither stops what it is doing. It is logged as `warned`. With the
switch off a run is unchanged decision for decision.
`experiments/warning_check.py` compares fields worked, the harvest and the
granary with warnings as before and quick (results/warning_check.md). Over
two in-game years without the model, quick warnings cut conversations from
2,356 to 868 while as much was passed on (9,803 facts against 9,099). Fields
worked, the harvest and the granary differed within one seed's noise, and no
arm went hungry. Without the model a conversation lasts 2 to 4 ticks, not the
longer exchanges the model holds, so warnings never cost there what they cost
in the second long run. Whether quick warnings give the fields back their time
is a question for a run with the model.
Levels 1 and 3 wait on the importance of each kind.

The thresholds between the levels are set from the long runs, not guessed. The
world has no fire yet. Raiders reaching the village are its nearest kind of
urgent danger, and any new danger the world gains fits the same scheme.

## 9. A day with work in it (proposed 2026-10-11)

A villager has no sense of the work it still owes a day. Each time it is free it
chooses afresh from all it could do, so a run of warnings can fill a day. With
BEAR's decision checks (`bear.checks`, built 2026-10-04 with Hearthwick agreeing
to be its second consumer), each need asks its own question, and only the
instructions that answer it can win it. The most urgent check decides.
- **Work due.** A villager with a trade owes so many hours a working day, set by
  trade and stage, starting from what its trade's instructions already imply.
  While work is due in working hours, the work check decides.
- **Telling.** A separate check, firing when the villager holds fresh news that
  someone near has not had from it (told memory). Below work while work is due,
  so it fits breaks, meals, evenings, or a quick word on the way.
- **Danger.** Above work, for the urgent news of section 8.

So a farmer works its hours and still warns its neighbours the same day, and an
alarm still stops the fields.

**Order of building:** quick-word warnings and urgency levels (section 8), then
lessons as memories (section 2, stage 3), then work due through checks. Each
goes behind its own switch, off in the paper profile, and the second long run is
followed by a third with all of them on.

## 10. Warnings last days, and far-off news warns only of what can come here (built 2026-10-12)

Scott, 2026-10-12: a warning should not persist for years, and news of a place
far away should not be a warning unless it is about something that can move to
the village. In the third long run's first six years, 54% of the 36,649
decisions to warn were `knows-warn-about-road`. What quick warnings passed on
came mostly from storytellers' tales (20,978 facts) and travellers' news
(8,594), against 1,404 from the three raids the village actually saw
(results/long_run_v3/long_run_report.md, read to day 168). With `afar_news`
off, a tale of fighting beyond the forest was held as a hazard on the east
road, and a hazard took two years to fade, while a storyteller came 17 times
in those six years.

Both rules are properties of the news as fading BEAR items, behind
`short_warnings` (`--short-warnings`, which turns on `bear_memory`):
- **Days, not years.** What a kind of news makes a villager do fades with a
  half-life in days (`memory.FADE_DAYS`): a danger or a sickness about a week,
  a season at 28-day years, and a rumour three days. The memory stays, and only
  sinks in recall. Witnessing it again renews it.
- **What can come here.** A storyteller's tale or a traveller's word about
  raiders, a sickness going round or wolves (`knowledge.CAN_COME_TOPICS`) is
  tagged `can_come` where it is first heard, and the tag passes on with every
  retelling. Held as from afar (`afar_news`), such news sets
  `knows_danger_coming` and fades as a danger does, whatever kind it was given.
  Far-off news of anything else, a fair, a washed-out road, dear grain, sets
  only a `knows_<kind>_afar` tag, which warns nobody.
- **One mild warning.** `knows_danger_coming` admits one instruction,
  `coming-pass-the-word` (`data/instructions/coming/`, loaded only with the
  switch). It sits at priority 50, below the trades' work, so it is a word to
  whoever is near and never a reason to leave the fields. A danger that does
  arrive is witnessed in the village, and the ordinary warnings take over.

The far-off half needs `afar_news`, which a new run has unless
`--no-afar-news`. With the switch off a run is unchanged decision for decision
(`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5).

## 11. Time in the day: teachers by pupils, and no idle tick between actions (built 2026-10-14)

Warnings and lessons looked as if they filled the day, but the shares quoted
until now were of decisions, and a quick warning lasts one ten-minute tick
while a spell of work lasts twelve. Measured in hours instead, from the
frames, the fifth long run's adults, apprentices and elders spent their
waking hours (6:00 to 22:00) in year 7 working 28%, walking 20%, resting or
sheltering 20%, idle 19% and talking 14%, much as in the third and fourth runs.
Warnings took about a third of the idle ticks, about an hour a day. Two
things took far more.

- **Teaching.** 79% of all work time was at the schoolyard, nearly all of it
  `elder-teach`, against 13% in the fields. That instruction asks only that the
  villager be an elder by day, never whether there are pupils, and it outranks
  the field instructions. By year 7 the village had 15 elders and 4 children.
- **A tick between actions.** About 60% of idle ticks, about 11% of waking
  hours, came after an action ended partway through a tick. The villager
  waited for the next tick's decisions, since deciding comes before acting in
  a tick's order. A one-tick action, such as a quick warning, left its whole
  tick idle the same way.

Scott (2026-10-14): "The elders should do more than teach. One teacher should
be able to handle 10-20 students. We should definitely choose another action
if there is still time in the day."

**`teachers_by_pupils`.** The teaching instruction gains the gate
`pupils_waiting` (`corpus.teach_by_pupils`), which the brain sets on an elder by
day only while the school has fewer teachers than its children need: one for
each `pupils_per_teacher` (15, the middle of Scott's ten to twenty). A teacher
is anyone teaching at the schoolyard or on the way there, so elders deciding
in one tick see each other's choice. An elder who is not needed is offered
everything else an elder can do.

**`decide_again`.** After everyone has acted, a villager whose action ended in
that tick takes up its next one in it too: the next it had queued, or a fresh
decision. Once a tick, so actions that each end at once cannot loop, and not
for a villager whose decision that tick gave it nothing to do. A quick
warning then costs no time at all. It is a word on the way to the next thing.

Both are off in the paper profile and unless asked for (`--teachers-by-pupils`,
`--pupils-per-teacher`, `--decide-again`). With both off a run is unchanged
decision for decision (`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5).
In a test morning of the greater village, the grown villagers' idle frames
went from 19 of 936 to none with `decide_again`.

**What they do and don't do.** Two in-game days of the fifth long run's
switches without the model, in four variants (neither, each alone, both),
showed the switches doing what they are for and not, alone, putting more
time into work.
- `teachers_by_pupils` cut elders' choices of teaching from 27 to 6. But the
  elders it freed had nothing productive to take up: the field help
  (`food-help-tend`) is for adults only. Their waking time at work fell from
  51% to 22%, and went to walking, sheltering and the shrine.
- `decide_again` took idle time to about nothing. The tick it saved went to
  whatever won the next decision, most often walking or sheltering.
- In every variant the most chosen adult instruction by day was
  `weather-wait-out-rain` (92 to 150 choices in two days). It is gated on any
  rain, outranks most work at priority 58, and sends the villager to the inn
  for four ticks, again and again while it rains. Afternoon breaks for the
  easygoing and midday breaks for apprentices come next.

So what keeps villagers from the fields is what they choose, not the length
of the day: sheltering from any rain, breaks, and elders with no work but
teaching. The next changes are in the instructions: elders able to help in
the fields, and shelter only from a storm or for the easygoing.

## 12. Elders in the fields, and work through light rain (built 2026-10-14)

Section 11's trials found the elders freed from teaching with no food work
to take up, and sheltering from any rain the most chosen adult instruction by
day. Scott (2026-10-14) agreed both should change.

**`elders_in_fields`.** Elders get the food work adults have, in lighter
spells at the same priorities (`data/instructions/elderwork/`, loaded only
with the switch): helping with the harvest (6 ticks against an adult's 12),
bringing it in when the granary will not last (8 against 18), and helping to
tend a crop that is behind (6 against 12).

**`work_in_rain`.** Sheltering from rain (`weather-wait-out-rain`) needs the
easygoing allele rather than preferring it (`corpus.rain_for_the_easygoing`).
The diligent already had their own instruction to work through rain, and a
storm still sends everyone indoors.

Sixteen in-game days of the fifth long run's switches without the model,
through spring, summer and the start of the harvest:

| | none of the four | the three content switches | all four (with `decide_again`) |
|---|---|---|---|
| elders' ticks of field work | 90 | 1,132 | 1,036 |
| adults' ticks of field work | 4,110 | 4,106 | 4,452 |
| tending, all season | 3,086 | 3,527 | 3,851 |
| crop at its peak | 954 | 1,040 | 1,040 |
| harvest in by day 16 | 192 | 406 | 372 |
| granary at day 16 | 367 | 581 | 545 |
| adults' waking hours idle | 18% | 18% | 3% |

The crop reached the fields' capacity (1,039.5, from 99 tiles) two days before
the harvest with the switches on, and never with them off. Past that point
the size of the fields limits food, not the hands working them, so a growing
village needs its ground cleared (`food-clear-ground`, adults in winter while
`fields_small`).

Both are off in the paper profile and unless asked for (`--elders-in-fields`,
`--work-in-rain`). With all four of sections 11 and 12 off, a run is unchanged
decision for decision (`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5).

## 13. A warning is about the fresh news that unlocked it (built 2026-10-21)

**What went wrong.** The paper-v3 runs (`--profile illustrative`, tag
paper-v3.1) passed their health checks except one. Seed 3's ten-year run
flagged a grown villager stuck in one place. That villager, Bryn, warned
neighbours 126 times in about 110 ticks near day 261. Bryn passed on old news
in those warnings: a tale from the east road 58 times, the well's sickness 53
times, a visitor on the east road 28 times. The listeners already had 181 of
the facts offered, kept 44 and refused 20.

The cause was in every run. A warning instruction is unlocked by a fresh
`knows_` tag, a danger heard of within about a week (section 10). But who had
something to learn, and what went with the warning, were judged from
everything the warner had ever held. The topic narrowed that only by the
place it names, and `coming-pass-the-word` names none, so it narrowed nothing.
With told memory (section 3) each warning passed on two facts the warner had
not yet shared with that listener, so a warner who had heard twenty things
about the east road could warn each neighbour ten times.

| | six forty-day runs | three ten-year runs |
|---|---|---|
| villager-days with over 20 warnings, per run | 39 to 125 | 832 to 997 |
| most warnings by one villager in a day | 54 to 107 | 91 to 134 |
| most times one warner warned one listener in a day | 11 to 25 | 29 to 58 |

In the six forty-day runs, 49,926 of 196,604 decisions chose one of the four
authored warnings (`knows-warn-about-road`, `-well`, `-blight`,
`coming-pass-the-word`). Lessons a villager wrote chose a warning only 2 times
in seed 3's forty-day run and 158 times in its ten-year run.

**The rule** (`fresh_warnings`, `--fresh-warnings`, which turns on
`told_memory`, `quick_warnings` and `bear_memory`):
- **About the news that unlocked it.** A warning is about the warner's news
  that BEAR still holds above half its strength (`MemoryIndex.salient`, the
  same question that sets the `knows_` tags) and that the instruction answers.
  For an authored warning that is the news setting a `knows_` tag it is gated
  on, so news of its kind and place. For a lesson it is the news the lesson
  was written from, or, resting on none, the news its topic names
  (`Brain._warn_news`).
- **Nothing fresh, no warning.** With no such news the warning resolves to
  nothing, and the villager does something else.
- **Only that news, once to each listener.** The warning names the events it
  is about (`news` in the action), and `Diffuser.tell` passes on only those.
  A listener the warner has already told of every one of them, or heard them
  from, is not warned again.
- **Told as it is given.** What a warning passes on is chosen, and both
  remember it as told, when the warning is given (`Diffuser.warning`), not
  once the listener's lens has run. A quick warning ends partway through its
  tick, and the warner decides again in that tick (`decide_again`, section
  11). The first trial (79cc1d4) remembered the telling only once the offers
  ran, so the listener still looked untold, and the second warning to it
  carried nothing. 14 to 18% of its warnings carried nothing, nearly all
  of them this second one.

The health check (`experiments/health_check.py`) flags the same warner,
listener and topic more than three times in a day, and a year in which more
than 5% of warnings carried nothing. One villager's warnings in a day are
reported but not flagged, since the rule bounds them by its neighbours and
the fresh events it knows of. Off in the paper profile and unless asked for,
on in the illustrative profile.

**Trials** (`results/fresh_trial/runs.txt`), seeds 1 to 3 of the
illustrative profile for 56 days, against the paper-v3 ten-year runs of the
same seeds read to day 56:

| | paper-v3 | first trial (79cc1d4) | second trial (a81ec0f) |
|---|---|---|---|
| most times one warner warned one listener of one thing in a day | 12 to 25 | 2 to 5 | 2 to 3 |
| warnings that carried nothing, share of a year's | 1.1 to 7.1% | 13.9 to 17.5% | 0.1 to 0.4% |
| most warnings by one villager in a day | 47 to 61 | 27 to 59 | 24 to 42 |
| health check flags, per run | 1 or 2 | 1 or 2 | 0 |

The second trial's busiest day, edda's on day 23 of seed 1, was 42 warnings
to 23 listeners about 5 events at most 4.2 days old, none told to the same
listener twice and none carrying nothing.

With every switch off a run is unchanged decision for decision
(`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5). With the
illustrative profile's switches but this one, 720 ticks without the model
match paper-v3.1 line for line (07afb8cafa199122). With it on as well, the
same 720 ticks make the same choices with the same targets, and each of
their 144 warnings names one event.

**Known defect: old tales stay fresh** (found 2026-10-23 in the paper-v4
ten-year runs, to be fixed after the paper). News is fresh for a week from
when its holder heard it (section 10), not from when its event began. A
storyteller's tale of danger abroad therefore lives on as long as someone
has not yet heard it, and a growing village always has someone. On day 177
of seed 1, nils passed on a tale first told on day 46. The rule that marks
down far-off danger that never came (`false_alarms`) makes it worse. It
counts any raid or sickness after the tale began, however much later, as
its coming, so once one has happened an old tale of fighting is never
marked down. In the three ten-year runs, 15.7 to 21.6% of the events
`coming-pass-the-word` passed on were over a week old, and 6.2 to 12.1%
over four weeks, though 99.5% or more had been learned by their warner
within the week (`experiments/warning_ages.py`). A warner who has just heard many such tales warns each
neighbour of them two at a time, up to 5 times a day for one listener, so
each run's health check flags the same warning to the same listener (24, 6
and 2 listener-days in ten years, against 27,948 to 44,673 warnings). Scott
(2026-10-23) counts it a defect, to be fixed later and named in the paper as
future work, and the paper-v4 runs are used as they are
(`results/long_runs_v4/runs.txt`). The likely fix dates far-off danger by
when it began, for fading and for false alarms alike, with a deadline that
counts only an arrival within the week after the event. It is built behind
`far_danger_dated` (section 14).

## 14. Word of danger abroad dated by when it reached the village (built 2026-10-23)

The fix for section 13's known defect, built on main after the paper-v4
freeze with Scott's go-ahead, so the paper's build does not have it. It is
tried on the Radiology AI Lab machine (`rtx-lab`) while the paper's batches
finish at home. Behind `far_danger_dated` (`--far-danger-dated`, which turns
on `short_warnings` and `bear_memory`):
- **Fading from the event.** Word of a danger abroad that can come here
  (tagged `can_come`, section 10) starts its clock when it reached the
  village, the tick in its root, not when each villager heard it
  (`MemoryIndex.dated`). A tale heard a week or more after it arrived has
  already faded below half its strength, so it sets no
  `knows_danger_coming`, and no warning carries it. The storyteller who
  brings the same word again lives it again, which restarts its clock as
  before, and every copy told on from the renewed telling carries its date
  (`Diffuser.offer`). A copy told before the renewal stays old. The same
  date decides when a memory leaves the live index (`forget_faded`).
- **False alarms judged by the event.** With `false_alarms`, word of danger
  abroad is judged a week after it reached the village, and only a raid or
  sickness within that week bears it out. Before, any later one did,
  however late, so a single raid kept every older tale of fighting alive.

Dangers in the village (the well, the blight, raiders on the road) keep
their clocks as before. They have their own endings (`news_ends`), and one
that lives again restarts its old fact's clock without a new root.

Off in the paper profile and unless asked for, on in the illustrative
profile on main. The measure is `experiments/warning_ages.py`: how old the
events in warnings are, and how long their warners had held them.

With every switch off a run is unchanged decision for decision
(`replay_fingerprint.py --ticks 144`, 90b674e3f38c32c5). With the
illustrative profile's switches but this one, 720 ticks without the model
match paper-v4 line for line (9add2b03a5f099d2), and with it on as well
they are the same again, since no tale grows old in five days. The trial is
`results/dated_trial/runs.txt`.

The trial passed on 2026-10-24. In its three ten-year runs, 2.0, 0.0 and 0.6%
of the events `coming-pass-the-word` passed on were over a week old (15.7 to
21.6% in the paper-v4 runs), no warner warned one listener of one topic more
than three times in a day (up to 5 before), and every health check was clean.
Scott, 2026-10-25: the paper keeps the paper-v4 runs and reports the trial in
its limitations as a later build that improves how news ages, tested only in
those runs. More runs follow as compute allows. `paper/check_numbers.py` checks
the paper's figures from `warning_ages.py` outputs for all nine paper-v4 runs
(`results/paper_v4/ages`, `results/long_runs_v4/ages`) and from the trial's.
