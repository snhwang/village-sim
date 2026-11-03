# The long run: a detailed report

Run `20261003-093714-seed1`, the greater village with speech, left running
since 2026-10-03. This report covers its first 552 in-game days, which are 69
years of 8 days. It goes further than the paper would, and spends most of its
length on the lessons villagers wrote for themselves, and on why the check
refused most of them.

Every number here comes from two committed scripts.

```
python experiments/long_run_report.py 20261003-093714-seed1 --to-day 552
python experiments/signature_check.py 20261003-093714-seed1
```

The first writes `long_run_report.md` and `.json` in this folder. It reads the
log only to the start of day 552, so it gives the same numbers while the run
goes on. The second writes `results/signature_check.md`. Rates quoted below
are in those files too.

## Summary

- The village outlived its founders. It grew from 30 to about 215 people and
  has held there since about year 53. All 30 founders have died, and five
  generations have been born.
- The steady population is births a year times the mean lifespan, as it must
  be for a population with no lasting arrivals (5.27 births a year times 41.3
  years gives 217.6, against 215.3 people).
- Births stayed near five a year while the couples in the village went from
  8.9 to 63.0 on average. The limit was not houses or the chance of
  conception. It was how often a couple at home chose to have a child. That
  fell from 13.2% of the moments it could in the first decade to between 4.0%
  and 5.1% after, and instructions about the news and the weather were chosen
  instead.
- Villagers wrote 2,008 lessons for themselves as they grew up, and the check
  refused 1,652 of them (82.3%). Nine refusals in ten were about an argument.
- The cause was in Hearthwick, not in BEAR or the model. Hearthwick passed the
  model bare marker names, and BEAR's prompt told it not to add arguments to a
  marker shown without one. Most markers need one.
- So the check kept almost only lessons whose markers need no argument. Of 383
  such lessons it kept 329, and of 1,625 that needed one it kept 27. Lessons
  about the news (avoid a road, warn someone) were nearly all lost, and what
  survived was mostly about resting at night. Rest made 82.7% of the 62,281
  choices of a lesson.
- Showing the model each marker's signature fixes it. In a replay of 30 of the
  run's consolidations, bare names kept 22 lessons and refused 56. Signatures
  kept 78 and refused none. The fix is in the paper's build (`paper-v2.2`).

## 1. What ran

The greater village of 30 founders, seed 1, with 8-day years. Speech came from
Qwen3.8-27B (the paper's checkpoint) served on a DGX Spark through the fleet
gateway (`runs.txt` in this folder). Death, money, land, materials and blight
fighting were on. Designs, wants, web search, vehicles, assessing,
looking at drawings and placing were off. This is not the paper's profile,
which also turns off death, money and materials.

It ran on two builds. It started on Hearthwick 548f388 with BEAR f9b509c. On
2026-10-05 it was stopped at tick 34899 (day 242, year 30) and resumed on
1a3aff8, which fixes a crash in the embedding client's cache. The resume kept
the run's switches and restored 122 learned instructions. Anything that
changes at year 30 could be the new build rather than the village.

Three faults found since are in both builds:
- BEAR's threshold backfill restored instructions the threshold had set aside
  (fixed in BEAR 226c659).
- The instructions of switched-off mechanics were still loaded and ranked, so
  they took candidate places they could never use (fixed in c378c7f).
- Consolidation showed the model bare marker names and offered the markers of
  switched-off mechanics (fixed in dae4771, section 5).

## 2. The village

| | |
|---|---|
| people at the start, and now | 30 and 219 |
| births, deaths, marriages | 328, 139, 150 |
| founders alive | none of 30 |
| born by generation, first to fifth | 66, 86, 113, 60, 3 |
| age at death, mean and median | 41.4 and 41.2 years |

The village grew fastest between years 18 and 24, from 76 people to 127. From
year 53 its people at a year's start have stayed within 5% of their mean over
the last ten years (216.4), so the report takes years 53 to 68 as its steady
state.

Over the steady years, with intervals from batch means (section 6):
- 215.3 people at a year's start (209.6 to 221.1)
- 5.27 births a year (0.81 to 9.72)
- 4.67 deaths a year (2.92 to 6.41)
- a mean age at death of 41.3 years, for the 72 who died then

For a steady population with no lasting arrivals, the number alive is births a
year times the mean lifespan (Little's law). Here that is 5.27 times 41.3, or
217.6, against 215.3 people. So the plateau follows from two rates. Lifespan is
set by the mortality code. Births are the subject of section 3. The births
interval is wide because the steady phase has only three five-year batches.
More years of the run would narrow it.

The granary grew over the run. It held 282.6 at the end of year 0 and 966.9
at the end of year 68.

## 3. Why births stayed near five a year

A couple has a child through an instruction, `family-have-child`, which carries
`[!have_child]`. It is admitted only in daytime, to a fertile adult whose
partner is home with it (`daytime`, `fertile`, `partner_home`). If it is
chosen, the handler still refuses if the granary is low, the house has no room
for another child, their last child is under a year old, or the couple has
already tried that day (`hearthwick/family.py`). A try then succeeds one time
in five.

The report follows every moment the instruction could have been chosen, from
the decision log.

| years | couples | could choose a child | chose | chose, per moment | tried | born |
|---|---|---|---|---|---|---|
| 0-9 | 8.9 | 2,182 | 287 | 13.2% | 161 | 38 |
| 10-19 | 19.9 | 5,611 | 285 | 5.1% | 184 | 32 |
| 30-39 | 40.5 | 9,710 | 401 | 4.1% | 245 | 53 |
| 60-69 | 63.0 | 10,843 | 470 | 4.3% | 276 | 44 |

The couples went from 8.9 to 63.0 and the moments a child could be chosen
from 2,182 to 10,843 a decade. The choices did not keep up. The instruction
was among the logged candidates every time, and lost.

What was chosen instead, most often, were the knowledge-gated news
instructions (`knows-warn-about-blight`, `knows-avoid-raided-road`,
`knows-warn-about-road`) and `weather-shelter-from-storm`, with `elder-teach`
for elders and the merchant's and healer's role instructions. The fall after
the first decade fits the village's news piling up, since each piece a villager knows
admits more of those instructions. That is an inference from what was chosen,
not yet a measured cause. Replaying the same decisions without the news
instructions would test it (section 6).

The other steps were not the limit:
- Conception was 328 in 1,615 tries, 20.3% (18.4% to 22.2%, resampling the
  120 couples), as set.
- Between 56.1% and 64.6% of choices became tries in each decade. The
  handler refused the rest, and the log does not keep its reasons.
- Houses were not short. All 81 couples who married without a house got one,
  after a median of 0.1 years.

So my earlier account, that couples tried only when they could support a
child, was incomplete. The handler's checks do refuse a share of choices, but
the larger limit is the choice itself.

Births per family, over 86 families: 16 had one child, 14 two, 14 three,
13 four, 9 five, 6 each six, seven and eight, and one each nine and ten. The
paper reports births per family only (the ALife paper, DOI
10.5281/zenodo.19866690, holds the genetics), and this report reads no
genotype.

## 4. Trades

Children born in the run took 303 apprenticeships. With intervals from
resampling the 76 families:
- 132 (43.6%, 36.5% to 50.2%) took a parent's trade.
- 63 (20.8%, 15.6% to 26.1%) trained under a parent.
- The trades taken were farmer 99, guard 75, merchant 71, healer 39, crafter
  18 and storyteller 1.

When a master died, the apprentices were given a new one. Of the 68
apprentices whose master died (47 masters in all), 66 were placed.

Villagers made 1,501 sales, for 34,441 coins. The world sent 453 changes of
weather, 151 sicknesses, 119 travelers, 69 harvests, 64 festivals, 53 visitors
and 2 raids.

## 5. The lessons villagers wrote

### How a lesson is written and checked

When a villager reaches a new stage (apprentice, adult, elder), Hearthwick
hands its most reinforced facts, news first, and its last decision to BEAR's
generator (`bear.evolution.generate_with_llm`). The model writes up to three
instructions, each carrying one or two action markers from a list Hearthwick
gives. Hearthwick then checks every marker (`consolidation.executable`):
- the marker is one the village implements
- every argument is one its handler reads
- a required argument is there (`go` needs `to`, `avoid` needs `place`,
  `warn` and `talk` need `target`)
- a place or a person it names exists

A lesson that passes is gated to its author, to night if it is about the
night, to daytime if it moves the villager, and to a place it is set in. A
lesson that fails would never act. A marker the handler cannot read does
nothing and reports nothing, so the check refuses it rather than let it take
a place in every ranking.

### What they wrote about

Mostly the news, and the night. The facts handed over were the village's
rumors (raiders past the forest, the lord's men counting heads, wolves at the
high pastures, a washed-out ford, dear grain) and the births each villager had
heard of. One refused lesson, drawn at random by the report, was written by
Brit200 on becoming an adult.

> The grain is dead and the roads are choked with raiders, so the price of food has tripled. Do not attempt to move goods through the bandit-choked forest or the flooded low road. If you hear of a fair drawing merchants to the east road, know that our carts are prime targets. [!avoid(site=east_road)] [!avoid(site=low_road)]

It is a sensible lesson, refused because `avoid` reads `place`, not `site`.

### Why most were refused

There were 1,043 stage changes. In 326 consolidations at least one lesson was
kept, and in 347 every lesson was refused. Of 2,008 lessons, 356 were kept and
1,652 refused. The check names only the first fault it finds.

| why | lessons | share of refusals |
|---|---|---|
| wrong argument name | 1,219 | 73.8% |
| required argument missing | 279 | 16.9% |
| names someone not in the village | 97 | 5.9% |
| names a place not in the village | 43 | 2.6% |
| no action marker it could read | 9 | 0.5% |
| a marker the village does not have | 5 | 0.3% |

The wrong names were guesses. The commonest were `avoid(site=…)` 494 times,
`go(site=…)` 109, `warn(ticks=…)` 93, `avoid(road=…)` 92 and
`avoid(location=…)` 42. `site` and `ticks` are what `work` reads, and the
model borrowed them for other markers (the next section says from where).

The missing ones were mostly whom to warn or talk to. `warn` came without a
target 133 times, `avoid` without a place 68 times and `talk` without a target
43 times.

Of the names that are no one, the commonest were "villagers" (31), "village"
(15), "elders" (6) and "neighbors" (3). The model meant groups, and the
village has no marker that addresses one. Of the places that are
nowhere, the commonest were "pasture" (7), "high_pastures" (6) and "road" (5).
The news speaks of high pastures the map does not have.

Both lessons the report draws from the nine without a readable marker put two
markers in one bracket, as in `[!avoid(road=east), !warn(topic=road_blocked)]`. The five unknown markers were
inventions: `hide` (twice), `wait`, `check` and `knows`.

### The cause

Hearthwick gave BEAR the marker list as bare names (`go`, `avoid`, `warn`).
BEAR shows the list to the model verbatim, after this sentence of its prompt.

> The ONLY valid inline action markers are listed below. Use markers ONLY from this list, written exactly as shown. Do not invent new marker names, and do not add arguments to markers shown without one:

BEAR's own documentation asks for signatures, such as
`[!approach(nearest|id=X|item=food)]`. The model also saw six style examples,
the first six instructions in the corpus that carry a marker. In the run's
build they all carried arguments: `[!take_up(trade=assessor)]`,
`[!assess(ticks=6)]` twice, `[!apprentice(trade=assessor)]` and
`[!work(site=schoolyard, ticks=12)]` twice (`assessing.yaml` and `school.yaml`
at 548f388, which loaded every instruction whatever the switches).

So the model had two instructions that could not both be followed. When it
left an argument out, the check refused the lesson for a missing argument.
When it put one in, it had to guess the name. The guesses match the
examples. `site=` and `ticks=` are in them, and villagers wrote lessons with
`[!assess]` 18 times in a run with assessing off. The three of those this
report shows all copy the example's `ticks=6`.

### What got through

Since the fault was about arguments, the check sorted lessons by their markers
rather than by their sense.

| lessons whose markers | kept | refused | share kept |
|---|---|---|---|
| need no argument | 329 | 54 | 85.9% |
| need an argument | 27 | 1,598 | 1.7% |

By marker, `avoid` was kept 0 times in 856, `warn` 3 in 576, `go` 1 in 151 and
`talk` 3 in 134. `rest`, which needs nothing, was in 281 of the 356 lessons
kept. The villagers' lessons about the dangers they heard of were nearly all
lost, and their lessons about where to sleep were kept.

The kept lessons were used. Of 356, 326 were ever among a decision's logged
candidates and 288 were chosen at least once. They were chosen 62,281 times in
1,017,044 decisions (6.1%), a share that rose from 2.2% in the first decade to
between 6.5% and 6.8% from year 30. By marker, those choices were rest 82.7%,
work 11.8%, wander 3.4%, warn 1.3% and talk 1.2%.

The most chosen read like a snapshot of the moment they were written, turned
into a rule. The coverage gap handed to the model is the villager's last
decision, and the most chosen lessons restate it. The most chosen of all, by Brit140,
was chosen 3,831 times in 3,976 chances.

> It is night and dark. Brit140 is at the watchpost. Do not leave your post to seek out Gunne131 or Hakon130; the darkness and the nearby fighting make it too risky to move. Rest only when the watch is relieved. [!rest(ticks=1)]

The few news lessons that got through did act. The three kept lessons
carrying `warn` were chosen 794 times.

### Lessons that could never act

The run's build also offered the model the markers of mechanics this run had
switched off, and the check did not know the run's switches. Villagers wrote
151 lessons with such markers (search 63, drive 61, assess 18, want 7,
give_up 6), and 15 were kept. Each could be ranked, and none could act with
its mechanic off. One, by Jory159, was a candidate 1,346 times and never
chosen.

> Word travels that grain is so dear in the market towns that stealing a cartload brings a king's ransom. With the roads jammed and thieves bolder, you must assess the risk before moving. Look over the path and the people, and decide if the road is safe or if you must avoid it. [!assess(ticks=6)]

### The fix, and its check

Since dae4771 (`paper-v2.2`):
- Each marker is offered as a signature, with the arguments its handler reads,
  the places a place argument may name and what a person argument accepts.
  For the paper profile, `go` is shown as
  `[!go(to=<a place: home, own, east_road, fields, ...>)] (to is required)`.
- Only the markers of mechanics the run has on are offered. The paper profile
  offers 18.
- The check refuses a marker of a switched-off mechanic.

`experiments/signature_check.py` replays a sample of a run's consolidations
through the model twice, once with each prompt, and checks every lesson the
same way. For 30 consolidations of this run, with the paper profile's 18
markers and the model on 8355, the replay gave these counts.

| shown as | kept | refused |
|---|---|---|
| bare names | 22 | 56 |
| signatures | 78 | 0 |

With bare names the refusals were the same as in the run: `avoid(site=…)`,
`warn` without a target, and "neighbors" or "village" as a target. A replay is
not the run itself, so what villagers write under the fix, and how they use it,
remains to be seen in the reruns.

## 6. Getting by with one seed

One long run cannot give a spread between seeds. It can still give honest
intervals from inside the run, and this report uses three such methods:
- Batch means for yearly rates in the steady state. The years are cut into
  consecutive batches of five, and the interval comes from the spread of the
  batch means, which allows for one year leaning on the next. Population is
  strongly correlated year to year (lag-1 autocorrelation 0.57), and births
  barely (0.13).
- Resampling the units that share a fate. Tries are resampled by couple and
  apprenticeships by family, since one couple's tries are not independent.
- Following a mechanism through the log. The births funnel in section 3 uses
  every decision in the run, not a sample.

Three more would answer causal questions without new seeds:
- Replaying logged decisions with one thing changed, as the paper's
  counterfactual does. Removing the news instructions from the have-child
  moments would test section 3's inference.
- Event studies. The run had 151 sicknesses, 119 travelers and 53 visitors,
  each a before and after.
- Short forks from a checkpoint, each with its own seed, to show how far the
  village's state at one moment decides what follows.

## 7. Limits

- One seed, on builds with the three faults in section 1. The faults touch the
  rankings and what villagers learned, so the funnel and the lesson figures
  belong to this build. Lifespan and conception rest on code and are likely to
  hold. The birth rate, and so the population's level, depends on the
  rankings, as section 3 shows.
- Two builds, with a change at year 30.
- Eight-day years, where the paper now uses 28.
- Not the paper's profile.
- The model ran on a different engine and different hardware from 8355, with
  the same weights and settings.
- The run is still going. This report stops at day 552.

Two questions are left to other work. Pooled births belong with the genetics
boundary, so the paper would report births per family. Whether news outlives
the villagers who heard it is fact survival, which belongs to the Parlor paper.

## 8. Next

The long run should be repeated on the fixed build after the paper's reruns,
with the same switches as this one, so the two can be compared. When this run
is stopped (SIGINT to its process), the Spark's agent should be told, so it
can release the model lane.
