# Hearthwick: a specification

A village of retrieval-governed agents, and what it was built to measure.

Milestones 1 to 3 are built and measured. Milestone 3 is growth, episodic
memory and consolidation. Births (milestone 4a), couples forming, with
houses built for them (4b), and death of old age (4c) are built. Last revised
2026-09-29.
The numbers in section 6 come from six ten-day runs of the build before births
and couples (`20260927-190041-seed1` to `-195852-seed6`, listed in
`results/paper_runs.txt`), with BEAR's development repository at `9c76dcd`. They include the food
economy, traveling storytellers, school and trades, and growing up.
`paper/check_numbers.py` recomputes each one from the logs.

This is the working specification. It says what the system is, how each part
works, what has been measured, and what the measurements can and cannot
support. It is written to be turned into a paper, so it records failures as
carefully as results. Several of the more useful findings here are things that
turned out to be wrong. DESIGN.md holds the reasoning behind the design and the
plan for what is not built yet.

In the paper's edition, the sections on mechanics its runs had switched off
(practices, the crafters' drawings and the bench, wants, web search,
vehicles, placing, looking and assessing) are cut to a line each, and their
numbers kept, since other documents cite them. SPECIFICATION-talk.md,
SPECIFICATION-items.md and SPECIFICATION-v0.2.md say at their top which of
their parts are left out.

---

## 1. The claim

Most simulated characters share one policy and differ by parameters. A
behaviour tree is written once and every agent walks it. A memory-stream agent
retrieves from its own memories, but it reasons with a prompt its neighbours
also use. In both, individuality is a value passed to shared machinery.

Hearthwick tries the other arrangement. A villager is a set of retrievable
instructions, and two villagers differ because different instructions are
retrievable for them. There is no policy above the corpus. The same retrieval
step decides what a villager does, how it speaks, and what it keeps of what it
hears.

The question is whether that produces individual behaviour, or shared
machinery wearing different labels. Section 6 answers it in two halves. One is
whether temperament changes what a villager does. The other is whether it
changes what a villager keeps.

This is not a claim to run a village better than a behaviour tree does. A tree
is cheaper, faster and more predictable. The claim is narrower. It is about
what it takes for characters to be governed individually, and what that buys.

It is also not a claim to differ from memory streams more than it does. Both
store natural-language items per character, retrieve them by relevance, and
condition a language model on what was retrieved. Consolidation is close kin to
reflection. Three differences are real. Hearthwick also retrieves an authored
corpus that nobody experienced. Actions are dispatched from markers with no
model call. An instruction can be made unreachable by a hard gate and refused
by its handler. The paper (section 10) sets this out in full.

---

## 2. Architecture

### 2.1 The retrieval substrate

Hearthwick is built on BEAR. It uses these pieces.

| Piece | Role here |
|---|---|
| `Corpus` | every instruction in the village, in one flat pool |
| `Instruction` | id, type, priority, content, scope, metadata |
| `ScopeCondition` | `required_tags` (all must be present, a hard gate) and `tags` (any, a soft preference) |
| `Retriever` | dense or BM25 scoring of instructions against a query and context |
| `MarkerRegistry` | turns `[!verb(args)]` in instruction text into resolved actions |
| `parse_actions`, `parse_kv_args` | find markers and read their arguments |
| `bear.provenance` | one record per hop, so any fact's history can be answered |
| `bear.evolution` | `generate_with_llm`, which writes new instructions at consolidation |
| `bear.ownership` | owner gating in the shared corpus: `own` for personas, practice copies and learned instructions, `violations` for the isolation sweep |

One corpus and one retriever serve every villager and the world. They are
separated by tag, not by separate corpora. Villager instructions are gated on
character, stage, role and temperament. World instructions are gated on
`world`, which no villager context carries. Neither side can retrieve the
other's.

The authored corpus has 145 instructions, and 106 of them carry an action
marker. The runs in section 6 used 140 and 101, before the infant and family
instructions. Grouped by the gate that admits them, they are as follows.

| Group | Count | Gated on |
|---|---|---|
| stage | 43 | `stage_infant` to `stage_elder` |
| speech | 28 | `talking` |
| world | 18 | `world` |
| lens | 11 | `absorbing` |
| food | 9 | `harvest_ripe`, `crop_behind`, `season_winter` with `fields_small`, or blight news (section 2.8b) |
| knowledge | 9 | `knows_<kind>_<place>` |
| temperament | 8 | `temp_<allele>` |
| trade | 6 | `graduating` (section 2.7a) |
| visitor | 6 | `visitor`, or `near_stranger` for villagers (section 2.4a) |
| role | 4 | `role_<role>` |
| school | 2 | `stage_child` or `stage_elder`, in the morning (section 2.7a) |
| family | 1 | `fertile` and `partner_home` (section 2.7b) |

Each villager also has one persona. Learned instructions are added at run time
by consolidation (section 2.8).

### 2.2 The decision

An idle villager decides. The step is the same every time.

1. Context tags. They come from the villager's own state. They cover stage,
   role, the six temperament alleles, time of day, place, energy, who is
   nearby, what it is avoiding, the weather, and one tag per kind of news it
   holds. Tags are sorted, because they are embedded with the query and their
   order would otherwise move scores.
2. Situation text. One or two sentences describe where the villager is and
   what is around it. The two entries from its own store that bear most on the
   moment are appended (section 2.6). This text is the query.
3. Retrieve. Instructions are scored against the query. An instruction whose
   `required_tags` are not all present cannot be returned at any score.
   `scope.tags` raise the score of instructions that fit, without excluding
   those that do not. The dense threshold is 0.15. Since 226c659 in BEAR's development repository it
   sets aside a candidate below it whose soft tags all fail, gated or not.
   Before, BEAR put such a candidate back at a score of priority alone, which
   decided 11.5% of the paper's September decisions
   (`experiments/run_spread.py`).
   `SimConfig.restore_below_threshold` brings the old behavior back. It has no
   command-line flag, and a run recorded before it existed resumes with it on.
   Every instruction the gates admit is ranked, not a fixed top few.
4. Re-rank by feasibility. Retrieval ranks by relevance. A second stage
   ranks by whether an instruction can be carried out now, which depends on the
   live world rather than on the text. Down the ranking, each instruction that
   carries a marker has its markers resolved by the registry against the
   villager's situation. One that resolves to nothing is refused and set aside.
   This stops once four (`choice_pool`) have resolved. It is a re-ranker in
   BEAR's sense, which admits any scoring, ranking or re-ranking stage, written
   for this simulation because feasibility is a property of its world.
5. Choose. Among those four, one is sampled by softmax over final score
   (`choice_temperature` 0.02, and strict argmax at 0).
6. Act. Its resolved actions become the villager's current activity.

The decision records the top twelve candidates, the four it chose among, and
every candidate refused above them, so a villager whose best options could not
be carried out is visible in the log.

Resolving before choosing matters, and it was first done the other way round.
The brain took the top four marker-bearing candidates, sampled one, and only
then resolved it, giving up when all four refused. As a villager learns, more
of its best candidates are refused: a warning when everyone near already
knows, an avoidance already in force. Late in a run all four could be refused,
and the villager stood idle tick after tick while a practical option ranked
fifth (section 7, fault 34). A larger fixed pool only postpones this, because
the number of refused candidates grows with what a villager knows. Resolving
down the whole ranking is the only order in which refused candidates can never
crowd out one that could happen. The world agent ranks all its admissible
instructions the same way.

The refusal rule does real work. Section 3 states it as a rule.

### 2.3 Action vocabulary

Villager markers, and the arguments each handler reads, are listed below.

| Marker | Arguments |
|---|---|
| `go` | `to` |
| `wander` | none |
| `rest` | `until`, `ticks` |
| `work` | `site`, `ticks` |
| `clear` | `place`, `ticks` |
| `talk` | `target`, `topic` |
| `avoid` | `place`, `ticks` |
| `warn` | `target`, `topic` |
| `follow` | `target`, `ticks` |
| `play` | `target`, `ticks` |
| `depart` | none. A visitor leaves the village. Refused for anyone who lives here |
| `apprentice` | `trade`. A graduate takes up a trade under a master. Refused when no master of it is free |
| `have_child` | none. A couple at home tries for a child. Refused unless they can support one (section 2.7b) |

Arguments can also be given by position, in the order listed. The first
argument of `go`, `work`, `clear`, `talk`, `avoid`, `warn`, `follow` and `play`
is required, and without it the marker resolves to nothing.

Several markers are refused when carrying them out would change nothing, so
the re-ranking stage passes them over.

- A warning is refused unless someone nearby lacks news about the place its
  topic names.
- `go` is refused when the villager is already there (section 7, fault 40).
- `avoid` is refused for the villager's own workplace. Nobody keeps away from
  their work (fault 41).
- `clear` is refused when the place has no room left to grow into.

Places and people can be named symbolically. The place aliases are `home`,
`own`, `mentor`, `usual_place`, `quiet_place`, `unvisited_place` and
`random_home`. The person aliases are `nearby`, `nearby_child`, `nearby_adult`,
`parent`, `partner` and `stranger` (the nearest visitor). Anything else must be a real place id or a real
villager id.

World markers live in a separate registry, so neither entity can use the
other's verbs. They are `weather`, `raid`, `sicken`, `traveler`, `festival` and
`visitor`. The world used to decide the harvest too. The harvest is now what
the villagers bring in (section 2.8b), and it reaches the log as a world event
so that it is witnessed and told like any other.

### 2.4 The world is an entity too

The world is not a scheduler. It is an agent with the same decision step, run
twice a day. At dawn it decides the sky, and then it decides whether anything
happens. Each decision carries one focus tag, `sky` or `happening`, and each
world instruction requires one, so the split is made before retrieval. Both
decisions read the same dawn, and only then does either take effect. When the
two shared one decision, weather took about a third of all days, and weather is
never told. Its context is the village's own history. That covers the season,
days since rain, the last harvest, whether sickness is about, whether the last
traveler's news is still fresh, and how many villagers walked the east road,
drew from the well or worked the fields yesterday.

Its markers are events. The deciding is BEAR. The raining is ordinary code in
`sim.py`, and villagers then respond to the weather through their own
retrieval. The world samples among its best candidates by softmax
(`world_choice_temperature` 0.03), so different seeds produce different
histories.

Four properties keep this honest. All four were wrong at some point (section
7).

- Every world marker is refused while its effect is already in force. The well
  cannot sicken twice running, and the weather cannot change to what it already
  is.
- Every effect wears off. Sickness passes after four days and a hazard after
  five. News counts as fresh for two days. Without recovery each event is a
  one-way door, and the set of things the world can do shrinks every day.
- Perception is proportional. The road counts as watched when 30% of the
  village walked it, the well as busy at 40%, and the fields as worked at 20%.
  Written as absolute counts sized for ten villagers, these all saturated at
  thirty, and the world's context became a constant.
- A precondition is a hard gate and a reason is a soft tag. Raiders need
  `road_untended`. A lean year makes them likelier but is not required.

The world can legitimately decide nothing. If the news is still fresh and
nothing else is admitted, every candidate is refused and the day is quiet. A
festival is refused for two days after the last one, as a traveler is while its
news is fresh. Refused candidates are logged, so a world that has run out of options
can be told apart from one that chose.

### 2.4a Traveling storytellers

A traveler is an event. A few villagers near the road hold its news, and
nobody arrives. A traveling storyteller is an entity (`hearthwick/visitors.py`).

- The world decides when one comes, with `[!visitor(storyteller)]` in
  `world-traveling-storyteller`. The handler refuses it while a visitor is
  here and for three days after one has gone. An arrival counts as fresh news,
  so no traveler is sent while the storyteller is new.
- The storyteller walks in at the far end of the east road and lodges at the
  inn, its home while it stays. It is an adult storyteller with a temperament
  drawn as a founder's is, two copies of every gene, and a persona of its own.
  Its persona instruction joins the shared corpus, gated to it.
- It arrives holding three pieces of news from beyond the village, as its own
  first-hand facts, each with a root of its own (`tale:east_road:<tick>-<n>`).
  Every chain they start traces back to it.
- It behaves through retrieval like anyone else. Its `visitor` tag admits
  instructions to tell its news to whoever is near, and to go to the market or
  the well when nobody is. It also gets the ordinary adult and storyteller
  instructions, including evenings at the inn and the storyteller's lens.
- Villagers see a stranger nearby as `near_stranger`. Curious, sociable or
  trusting villagers are drawn to go and hear it, and a suspicious one keeps
  to its own door (`villager-wary-of-the-stranger`, part of the trust gene).
- Nobody talks for nothing. The target `stranger` resolves only to a visitor
  holding news the villager lacks, and `listener`, which the storyteller uses,
  only to a villager lacking some of the storyteller's news. Before this, one
  storyteller had 87 conversations with 14 villagers, who chose to seek it out
  117 times.
- A storyteller tells what it brought first, a tale the listener has not
  heard. Every villager brings up hazards first, and once a storyteller had
  heard of the blight, the blight crowded out its tales. Two of one
  storyteller's three tales reached nobody. With both rules, in the same seed,
  its three tales reached 26, 17 and 27 villagers in 31 conversations.
- After two days `leaving` appears, and `visitor-leave` (priority 95) walks it
  out along the east road and `[!depart]`s. It is then no longer alive in the
  village. What it heard here goes with it. Its store stays in the record, and
  `visitor_departed` lists the village news it took. One still here a day
  after it meant to leave is sent on without a decision, so that nothing keeps
  a visitor for ever. That is the only step not decided by retrieval.
- A visitor is not in any founders file, so it is logged as a roster event on
  arrival and checkpointed with its profile. Analyses read every roster event,
  and `knowledge_flow.py` counts only residents as villagers.

`experiments/visitors.py` reports what each storyteller carried, how far it
spread, whom it talked with, and what it took away.

### 2.5 Knowledge

A `Fact` is one thing one villager holds, in that villager's own words.

```
id, holder, text, kind, place, root, parent, teller, hop, tick, reinforced, vector
```

`root` is the world event it descends from. `parent` is the entry it was
rewritten from. `teller` is who said it, or `None` when witnessed first-hand.
`hop` counts tellings since the event.

Witnessing. When a world event fires, whoever saw it holds it first-hand, at
hop 0 with no teller. The sentence comes from a template keyed on the event
and its detail. A storm and a frost are therefore different news, a sickened
well and sickened fields are different news, and ordinary rain is not news at
all. Weather and festivals reach the whole village and never diffuse, since
nobody has to be told it snowed. For every other event the witnesses are the
five nearest villagers who are awake. An event therefore always has a witness
and never has the whole village. Both failures on either side of that choice
happened (section 7, faults 13 and 14).

Telling. When a conversation ends, each side offers the other up to two facts.
Each offer goes through these steps.

1. If the receiver already holds something descended from the same `root`, it
   is the same news. The existing fact is reinforced and nothing is stored.
2. Otherwise the receiver retrieves its own lens. That is the instructions
   gated on `absorbing` for its temperament, role and stage, filtered from
   everything the gates admit (it was the top 24, which lost two instructions
   in 2 of the paper's 675 lenses; speech guidance changed the same way). The speech model rewrites the incoming sentence through
   that lens, or refuses it. The lens can also change the fact's kind.
3. The rewrite is embedded and compared with everything the receiver holds.
   Above 0.85 cosine it is the same news in other words, and it reinforces
   rather than duplicates.
4. What survives is stored with a provenance record for the hop.

Step 1 does almost all of the work (section 6.2). Recognising repeated news is
an identifier comparison, not a semantic one.

Children are the deliberate exception. Their filter is weak, so they keep what
they were told nearly verbatim.

Knowledge becomes behaviour through tags. Storing a fact adds
`knows_<kind>_<place>` to its holder's context. That makes instructions gated
on knowing it retrievable for the first time. A villager that learns the well
is bad can now retrieve an instruction to avoid it. Nothing else changes. The
villager's reachable behaviour simply grew. Because the tag carries the kind,
a listener who files a traveler's news as a hazard gains behaviour the witness
never had.

### 2.6 Episodic memory and recall

A villager also remembers its own life. Experiences share the store with news,
under three kinds (`met`, `did`, `told`). When a conversation ends, both sides
store "I talked with {name} at {place} about {topic}" as `met`. Experience is
never offered to anyone else, and it adds no `knows_` tag. It is memory, not
news.

At each decision the villager recalls two entries (`memory_recall`). They are
scored by cosine against the embedded situation. News is recalled before
experience, because a villager accumulates far more afternoons than news, and
ranking everything together would fill recall with who it chatted to. When no
vector is available, recall falls back to recency. The recalled sentences are
appended to the situation text after "Knows", so they shape the query.

### 2.7 Growth

A villager's stage can advance. This is on by default, and `--no-growth`
turns it off. It was off by default until trades gave growing up somewhere to
go. Advancing needs a minimum age
and thresholds on three tracks. There is no forced promotion. A villager that
reaches the age without the rest stays where it is, and each daily check that
holds it back logs which tracks fell short (`growth_held_back`).

| Track | What counts |
|---|---|
| knowledge | distinct root events held. Hearing the same rumour six times is one thing known |
| skill | practice at one site, one level per 120 ticks of work, capped at 5 |
| experience | for each kind lived through, 1 + log2(n). Grinding one activity gives diminishing returns |

| Transition | Min age (years) | Knowledge | Experience | Skill |
|---|---|---|---|---|
| infant to child | 2 | 0 | 0 | none |
| child to apprentice | 4 | 3 | 4 | school level 1 |
| apprentice to adult | 7 | 6 | 10 | level 2 in its own trade |
| adult to elder | 20 | 12 | 25 | none |

A year is eight in-game days. Advancing swaps the stage tag, which makes a
different part of the corpus retrievable. That is the whole mechanism of
growing up. Each advance logs `stage_change` with the tracks at that moment.

### 2.7a School, trades and masters

School and apprenticeship are one mechanism at two stages
(`hearthwick/trades.py`). A placement is a learner, a place and a teacher.

| Stage | Placement | To move on |
|---|---|---|
| child | a pupil at the schoolyard, where an elder teaches in the morning | graduate: the child gate, including school level 1 (20 hours) |
| apprentice | at its master's workplace, in the trade it chose | qualify: level 2 at its trade's workplace |
| adult | practising the trade, as its role | keeps improving with work |

School runs in every run. Children go in the mornings (`child-school`), an
elder teaches (`elder-teach`), and each child is taught a piece of news a day
(`hearthwick/school.py`). School used to exist only with `--practices`, which
this edition leaves out.

A graduate carries `graduating` until it chooses a trade, and the choice is
retrieval. Each trade has an instruction (`data/instructions/trades`) carrying
`[!apprentice(trade=...)]`. Its soft tags are what a graduate might lean
toward: a parent in the trade (`parent_<trade>`), where it has already spent
time (`skill_<place>`), what the village lacks (`needed_<trade>`, fewer
practitioners than the trade's share of the working village, and farming when
food is low or the fields are too small), and temperament (bold toward guard,
inquisitive toward healer, embellishing toward storyteller). The handler finds
the master the graduate is fondest of, among those with room for another, and
at most two apprentices each. Fondness is courtship's measure between any two
villagers, grown by conversations and time spent near each other, so a child
who spends its afternoons at the mill seeks out the miller. With no fondness to
go on, a parent in the trade comes first, then the practitioner with the fewest
apprentices. Choosing by fondness was added on 2026-09-28, after the measured
runs of section 6, which used the parent-first order alone. A trade with no free master is
refused, and re-ranking passes to the graduate's next choice. `apprenticed`
records the trade, the master and the fondness between them, and
`took_up_trade` the qualification, when the
trade becomes the new adult's role.

Skill is practice at a place, in levels. It counts double while an apprentice
works beside its master. It scales what work yields: half the base rate at
level 0, the base rate at level 2 or 3, and half again at level 5. So far only
the fields yield anything. Founders begin with the practice their years would
have given them. An adult starts at level 2 in its trade at 11 years and rises
a level every three, and an elder is at level 5. An apprentice has worked
beside its master since six, and a child has been at school since three.

`experiments/trades.py` reports who graduated, how each graduate ranked the
trades and what it chose, who took whom on, and who qualified.

### 2.7b Families

Couples who already exist can have children (`hearthwick/family.py`). There
is no pregnancy. A child appears at home when its parents succeed.

- Deciding is retrieval. An adult sees `fertile` when it is 11 to 20 years old
  (11 to 40, elders too, with the wider window of section 2.9j)
  and `partner_home` when it and its partner are both at home. Then
  `family-have-child`, carrying `[!have_child]`, can win like any instruction,
  most readily in the evening and for sociable villagers.
- The handler refuses unless the couple can support a child. Both must be of
  age and home together, the granary must not be low, the house must hold
  fewer than three infants and children, their youngest child must be at
  least a year old, and they must not have tried already that day. The same
  check runs again when the action is carried out, because both partners can
  decide in the same tick (section 7, fault 47).
- Trying is not always conceiving. A couple tries at most once a day, and a
  try succeeds with a chance of 0.2, drawn from a stream seeded by the couple
  and the day. Deciding to try is a BEAR decision. Only the outcome is chance.
  In a year of 28 days the chance is 0.062 a try, so a year has the odds of
  an eight-day year (`conception_chance`). Since the draw depends only on the
  run's seed, the couple and the day, runs on one seed share their luck: the
  same couple trying on the same day gets the same answer. Every long run on
  seed 1 had no births in year 8. In that year four founding couples have no
  winning day at all, and the others tried on none of theirs, in 25 to 30
  tries. A year without a child happens about one year in six at these odds.
  That is chance, not the village's ages, and another seed puts its lean
  years elsewhere.
- The child's two copies of every gene are bred from its parents' with
  BEAR's `breed`, one copy from each, and what it expresses is its
  temperament. Nothing it or its parents learned is in its genome. It gets a
  name, a persona and an empty store, lives in its parents' home, and joins
  the corpus, the logs and checkpoints the way a visitor does. Whoever is home
  witnesses the birth, and it is told as news.
- An infant eats a quarter of an adult's share. It stays home or near a
  parent, is never told news, taught at school or counted a witness, and
  becomes a child at two without consolidating anything.

`experiments/family.py` lists each birth with its day, parents and the
temperament the child expresses, and counts decisions, tries and
conceptions. It reports births family by family and pools nothing. Whether
children resemble their parents is a question for the behavioural-genetics
paper (Hwang, "Genes written in natural language: Inheritance and selection in
an artificial ecosystem", doi:10.5281/zenodo.19866690), not this one.

### 2.7c Couples and houses

Couples form between a man and a woman, by the choice of both
(`hearthwick/courtship.py`). A couple needs a home, and a home has to be built
by someone who knows how (`hearthwick/building.py`). Designed on 2026-09-28
and built the same day. The numbers are reasonable guesses, to be tuned after
the first runs.

**Affinity comes from shared life, not from traits.** Two villagers grow fond
of each other by spending time together. Affinity rises by 1 for each
conversation between them and by 0.25 for each in-game hour they spend near
each other, both awake. It decays by a tenth each day, so it reflects recent
contact. It is the same in both directions. Temperament still matters, but
through behaviour. A sociable villager meets more people, and a reserved one
fewer. Attraction is deliberately not computed from temperament or genes,
because mate choice that depends on genes is selection, which belongs to the
behavioural-genetics paper (section 2.7b).

**Who can court.** Two unpartnered adults, a man and a woman, residents not
visitors, at most 6 years apart, and not close kin (no shared parent, and not
parent and child). With the wider fertile window elders may court too
(section 2.9j), and the courting instructions are gated on `marriageable`.

**Courting, proposing and answering are retrieval.**

- The eligible villager a villager is fondest of is its sweetheart once
  affinity reaches 6. It then sees `courting`, and `sweetheart_near` when the
  sweetheart is close and awake. `family-seek-sweetheart` leads it to find the
  sweetheart and talk (`talk(target=sweetheart)`), which raises affinity
  further.
- At affinity 10 it also sees `fond_enough`. With the sweetheart near,
  `family-propose` then carries `[!propose]`. The handler refuses below
  affinity 10, if the sweetheart is not near and awake, if a proposal already
  stands for either of them or from either of them, or if the same person
  declined this one in the last four days.
- The one proposed to sees `proposed_to` and decides through its own
  instructions, `[!accept_proposal]` or `[!decline_proposal]`, of high priority
  so the answer comes soon. It also sees `prefers_another` when it is fonder of
  someone else, which admits a decline that outranks acceptance. It sees
  `hardly_knows_asker` while its affinity with the asker is below 15, which
  admits another decline, for not knowing the asker well enough. That one
  leans toward suspicious, reserved and wary villagers. A proposal not
  answered within a day lapses.
- What an instruction states as true is a hard gate (section 3, rule 1). The
  first 20-day trial (`20260928-015620-seed1`, a build before this change,
  read by `experiments/couples.py`) gated the proposal only on `courting` and
  the "not ready" answer only on `proposed_to`. With the sweetheart near, the
  proposal, at priority 62, ranked fifth to ninth in 143 of 178 decisions
  (four are chosen among), and was refused 15 times for fondness below 10. The "not ready" answer was open to villagers fond of the asker for days.
  Two proposals were made and both were declined as not ready, while Maren and
  Sten reached affinity 18.6. The proposal now needs `fond_enough` and has
  priority 72, and the "not ready" answer needs `hardly_knows_asker`.
- Every rule is checked again when the action is carried out, since both
  sides can act in the same tick. Recording a proposal or an answer happens
  then, not in the handler, so resolving stays free of effects
  (`tests/test_marker_purity.py` covers the new handlers).
- A couple agreeing to marry is witnessed by the few nearest awake villagers,
  the couple among them, and told as news.

**Where a new couple lives.** In an empty home if there is one. Otherwise in
whichever of their two homes has fewer other people in it. If that home still
has others living there, parents or siblings, the couple waits for a house of
their own, and the village needs one.

**Building a house.** Crafters are the village's builders, and for now they
do all of it, felling the timber and building. Only a crafter sees the
building tags, apprentices to a crafter included:

- `house_needed` while any couple waits for a house,
- `building_site` once a house has been started,
- `timber_short` while the store holds less timber than finishing the house
  needs, and
- `timber_ready` while it holds enough to work with.

`crafter-fell-timber` carries `[!fell]`. The crafter goes to the forest edge,
and each tick of work there adds half a unit of timber to the village store,
scaled by skill. The handler refuses when no house is needed or there is
timber enough. `crafter-start-house` and `crafter-build-house` carry
`[!build]`. The first crafter to build lays out a free 3x3 plot, clear of every
place by a tile and as near the other homes as possible, which becomes a site
on the map. After that every crafter builds at the same site. Each tick of
work there turns timber into progress, scaled by skill, and stops when the
timber runs out. A house takes 30 timber and 180 ticks of work at the base
rate (30 worker-hours). The handler refuses with no timber, or with no site
and no free plot. One house is built at a time. A crafter stops felling once
the store holds timber enough, and stops building when the house is up or the
timber is gone (section 3, rule 2). Before that rule, five crafters felling at
once took the store to 44 timber for a house that needs 30, in the second
trial run (`20260928-020856-seed1`).

Since section 2.9i, with materials on, the store is goods of each kind, and a
house takes what its design is made of, 30 clay for a cottage. The crafters
dig clay and cut stone as they fell timber, and `timber_ready` means there is
enough of every good. Without materials all of this stands as written.

A crafter's skill is its craft, practised at the mill, so felling and building
count as practice there and are scaled by that skill. An apprentice crafter
can qualify by building.

When the house is finished, the site becomes a home. The couple who have
waited longest move in with their infants and children, and the house is
news. The map changes during a run, so the viewer and `follow.world_for`
replay `place_added` and `place_removed` as they replay the fields growing,
and checkpoints save the built places, the timber, the site and its progress,
and every couple, affinity and standing proposal. A dawn `building` event
records the timber, progress and waiting couples while a house is needed.
Since 2026-09-29 each frame also carries it, as `b` (`Building.status`),
while a house is needed or going up. That gives the viewer its progress
between dawns, and a page opened mid-build sees it at once.

**What the design had that was not built.** Other adults lending a hand at the
site, as at harvest. The site drawn as foundations, then a frame, then a
house. The viewer shows corner posts and a stack of timber.

**What this measures.** `experiments/couples.py` reports, run by run, every
proposal with its day, fondness and answer, where each couple lived and
whether it waited, and every house with the day it was finished and for whom.
It counts how often each courtship and building instruction was chosen and
refused. It reports nothing by temperament or genes.

### 2.7d Death of old age

Built on 2026-09-29 (`hearthwick/mortality.py`), as DESIGN.md section 7
planned it. Until then nobody died, so a village left running only grew.

- **A lifespan is drawn at birth**, between 35 and 50 in-game years, from the
  run's seed and the villager's id. The same villager gets the same span every
  time it is asked for, so a checkpoint carries nothing new. A villager dies at
  the first midnight past its span. The founders' elders are 26 to 32, and no
  generated founder is older than 34, so nobody starts past its span and the
  first deaths come some years into a run. Visitors do not die here.
- **Death is simulation code, not a decision.** The villager is gone from the
  frames and does nothing more. Its store stays in the run's record, for
  provenance, but nobody can hear it, so what it knew lives on only in what
  others kept.
- **A partner is widowed, not unmarried.** `partner` still names the one who
  died, so the survivor's life facts say "Your partner, Mabel, has died."
  A partner who has died leaves the survivor free to court and marry again
  (`courtship.free`).
- **Apprentices find another master.** Each goes to the master of its trade
  it is fondest of, among those with room (`new_master`). With none free it
  practises on alone, without the speed-up of working beside a master, and
  still qualifies when its skill is enough.
- **The death is news.** Its household knows by morning, or the nearest
  villagers if it lived alone: "Mabel died in the night.", root
  `death:<id>`, witnessed at hop 0 and passed on like any other news.
- `died` records the age, stage, role, partner and where the apprentices went.
  Checkpoints count deaths. `--no-mortality` turns it off, and a run recorded
  before it existed resumes without it, so it stays the run it was.

**What the design had that was not built.** Sickness and raids shortening a
life. A funeral, and mourning as a tag that changes what the bereaved do for a
while. Removing the dead villager's store outright.

**What this does to the measured runs.** Nothing. The six runs of section 6
and the forty-day development run were made before it and nobody died in them.

### 2.8 Consolidation

Advancing also triggers consolidation, unless `--no-consolidate` is given. The
villager's most reinforced facts are handed to `bear.evolution`'s
`generate_with_llm`, news first and experience after, as the recurring terms.
Its last decision is handed over as the coverage gap. The model writes up to
three instructions (`consolidate_count`), restricted to the villager markers.

The markers are offered as signatures, with the arguments each handler reads
and the places a place argument may name (`signature` in
`hearthwick/consolidation.py`), and only those of mechanics the run has on
(`offered_markers`). Until 2026-10-09 the model was shown bare marker names,
and told not to add arguments to a marker shown without one. By day 551 of
the long run, 1,652 of the 2,008 lessons villagers wrote had been refused, and
1,498 of those failed on an argument (a guessed `site=`, or none at all), so
nearly every lesson kept was one whose markers need no argument, such as
`[!rest]` (results/long_run/long_run_report.md). A replay of a run's
consolidations with both prompts is in results/signature_check.md.
The check now also refuses a marker of a switched-off mechanic, whose handler
would never act.

Each generated instruction goes through four steps before it is kept.

1. It is checked against what the simulation can execute, the same way the
   handlers read it. The check covers each marker's name and the names of its
   arguments, with positional arguments taken in the order each handler reads
   them. It refuses a marker missing the argument its handler cannot act
   without (a `work` with no site, a `talk` with no target). It also checks
   that each place or villager named exists. Names are first rewritten as ids,
   so "Edek" becomes `edek` and the place called "house 13" becomes `home_13`.
   An instruction that fails is refused with the reason and logged.
2. It is gated to its villager alone with `char_<id>`. An instruction about the
   night gets `time_night`. One that moves the villager otherwise gets
   `daytime`, so sleep never depends on the embedder.
3. It is tied to where it is set. A place a sentence puts the villager in
   ("You are at the inn") becomes a hard gate (`at_inn`), because a premise is
   a precondition. Any other place the prose names becomes a soft tag. A place
   a marker sends the villager to or away from is neither, so "keep away from
   the fields" applies wherever the villager is.
4. Its priority is lifted by 25 and clamped to 46 to 58. That is the
   temperament band, below the knowledge-gated instructions (67 to 78).
   Generation returns 10 to 35 on its own, which is below every authored band,
   and learned instructions were then never chosen.

This is the only place the corpus itself grows. Everywhere else a villager's
reach changes because a tag made an authored instruction retrievable. Here a
villager gains an instruction nobody wrote. The event (`consolidated`) records
the instructions, the facts and gaps they came from, and anything refused.

### 2.8a Practices

Sheltering from the rain was a practice adults held and the young learned, by
watching, by being told, or at school, each in its own words through
`bear.culture.adopt` (`practices`, `practice_reinforcement`). The paper's runs
had it off, and this edition leaves it out (README). School stays (section
2.7a), and the practice's instruction, `weather-wait-out-rain`, is shared by
everyone, as it was in the paper's runs.

### 2.8b Food

The village eats from one granary (`hearthwick/food.py`). This is physics, like
energy and weather. Nothing in it decides what anyone does. The unit is one
adult's food for a day, and a child eats half. Thirty villagers eat 28 a day
and 224 in an eight-day year.

- The crop grows only with work. In spring and summer, each tick a villager
  works in the fields adds to the standing crop, up to what the fields hold (2
  per plot). Two worker-hours a plot reach that.
- The harvest takes hands. In autumn, each tick of work in the fields gathers
  0.25 into the granary. A full crop from the founding fields needs about
  eleven people on each of the two autumn days, more than there are farmers.
- Whatever is still standing when winter comes is lost. On the first morning
  of winter the harvest is reckoned. It is good if it brought in 80% of a
  year's food, and it becomes a `harvest` world event, witnessed near the
  fields and told like other news. The harvest festival follows a good one.
- Frost takes half the standing crop, and a blight in the fields 15% a day.
- The founding fields hold 198, less than the greater village eats in a year.
  The hamlet eats 72 and has room to spare.
- Villagers can clear new ground. Each 60 worker-ticks of `clear` adds one
  strip along the edge of the fields, on dry ground at least a tile from any
  other place. The map changes, a `place_grown` event records it, and the
  fields' size is checkpointed.
- The granary starts with seven days of food, enough to reach the first
  harvest. With it empty, villagers tire half as fast again and rest restores
  half as much. Nobody dies of hunger. Death is of old age only (section 2.7d).

Villagers see all of this as context tags, and instructions decide the rest.
`season_<season>` is always present. `harvest_ripe` means autumn with crop
standing, and `crop_behind` means spring or summer with the crop under 80% of
where steady tending would have it. `food_low` means the granary will not last
until the next harvest is in, `hungry` means it is empty, and `fields_small`
means even a full crop would not feed the village for a year. The food
instructions (`data/instructions/food/food.yaml`) answer these. Farmers bring
in the harvest at priority 74 and tend a crop that is behind at 68. Any adult
helps with the harvest at 63, or at 71 when food is low, and helps tend at 61.
Apprentices and children lend a hand at harvest. Adults clear ground in winter
when the fields are too small (67). A farmer who hears of the blight goes to
cut it out (72), where everyone else keeps away. A daily `food` event logs the
granary, the crop, the fields and yesterday's field workers.
`experiments/food_economy.py` reads them.

### 2.9 Checkpoints

Long runs must survive reboots, power cuts and someone wanting the GPU back.
`--checkpoint-every DAYS` writes `runs/<id>/checkpoint.json`, and
`--resume RUN_ID` continues from it. SIGINT and SIGTERM stop the run cleanly at
the end of the tick. With checkpoints on, a final one is written then.

- What is saved is every piece of state the simulation mutates. That is the
  clock, each villager, what the world remembers, every store, scheduled world
  events, and learned instructions. The map, the authored corpus and the
  retrieval index are rebuilt instead.
- Before saving, open conversations are ended and in-flight rewording is
  awaited. Without this, knowledge being absorbed at the moment of the save was
  lost (159 facts became 134).
- The write goes to a temporary file that then replaces the old one, so a
  power cut mid-write leaves the previous checkpoint intact.
- Fact vectors are recomputed on load. The embedder's model id is recorded,
  and a resume against a different model is refused, since vectors from two
  models share a space only by coincidence.
- A resumed run appends to the same event and frame logs and records the
  resumption in `meta.json`. A run stopped six times is one continuous record.
- A resume needs only the run id. The run's settings come from its own
  `meta.json`, and so do its length and checkpoint interval, which are recorded
  as its plan when it starts. Only paths and service connections come from the
  command line, because they belong to the machine. Resumes once rebuilt the
  village from the command line, and the printed hint named only `--days`, so
  following it would have resumed a `greater`-village run on the default map.
- A checkpoint records how long the event and frame logs were when it was
  taken, and a resume cuts them back to that. A run killed outright, by a
  reboot or a crash, has logged ticks past its last checkpoint, and resuming
  would have logged them twice. Added 2026-09-29, and only for checkpoints
  written since. A checkpoint restored into another run's log leaves that log
  alone.

### 2.9a Watching a run

A run can be watched in the browser while it runs, or replayed afterwards,
without the viewer touching it. `python -m hearthwick view` serves a 3D viewer
at `/3d` (and the 2D map at `/`) that reads the run's `frames.jsonl` and
`events.jsonl` as they grow (`hearthwick/follow.py`, the `/ws/follow`
websocket). The simulation flushes both every tick. A run counts as live while
its frames are being written and it has not recorded finishing. The viewer
draws each move along a dry route, since a frame records only where a villager
ended the tick, and a straight line between two frames can cross the stream
where the real path used the bridge (`client/route.js`).

Added on 2026-09-29, at Scott's request, while watching remotely:

- **Notices** over the scene say what the village has just done. They appear
  when a couple marries and needs a house, when a crafter marks out a plot,
  with each dawn's report on the house going up, and when a house is
  finished and the couple moves in. They fade after 14 seconds, four at
  most. They come from events as they arrive, not from the history a page
  loads with.
- **A Building section** in the side panel shows the house going up. It says
  for whom, the timber in hand against what the rest of the work needs, and
  the work done, as bars, and names who is felling and who is building now,
  each clickable. It reads the frames' `b`. A run from before frames carried
  that is pieced together from its events, the couples waiting, the plot on
  the map and the dawn reports, without the bars between dawns.

### 2.9b Talking with villagers

Built on 2026-09-28 (`hearthwick/player.py`). A human can talk with the
villagers of a village the server runs (`hearthwick serve`), through the 3D
viewer's talk panel and three endpoints, `/api/talk/start`, `/api/talk/say`
and `/api/talk/end`.

- **The human is a stranger, not a villager taken over.** Every villager stays
  an independent entity whose words come from its own instructions and
  knowledge. What the human says enters the village as news with the human as
  its source.
- **The world stands still while the human talks.** The server stops stepping,
  and keeps the frames file fresh so a viewer does not take the pause for the
  run's end. With a viewer open, the village runs at the server's `--speed`,
  and with nobody watching, at its `--idle-speed`, or flat out without one
  (section 2.9c).
- **The villager answers in character.** Its prompt has its speech guidance, as
  in any conversation, and the three things it holds that bear most on what it
  was just told or asked, so it answers from what it knows.
- **Every conversation stands on the same foundation** (`hearthwick/grounding.py`),
  between villagers as well as with a human. It carries the facts of the
  villager's life from the simulation's state (partner, children, parents or
  that they live elsewhere, household, master, workplace), the village's places
  and the people it can name, what it knows that bears on the moment, and rules
  of conduct: answer what was said, put no words in anyone's mouth, name only
  real people and places, and say "I don't know" rather than invent. The speech
  instructions it retrieved are framed as its character, to show where they
  fit and not in every line. The first trial conversations showed why. Mabel's
  parents were "buried or busy", Sten quoted an "Old Marta" and a "northern
  road" that do not exist, and "who told you?" and the rain turned up in nearly
  every line, because each trait instruction read as a standing order. The
  suspicious allele's speech instruction now reacts to being told something
  ("When someone tells you something, you wonder..."). Added 2026-09-28. The
  measured runs of section 6 spoke from their speech instructions alone.
- **The villager decides what to keep.** When the human leaves, what they said
  is one fact with a root of its own (`player:<conversation>`), offered to the
  villager's lens like any other. The villager also remembers having met a
  stranger. What it keeps it holds at one remove, told by the stranger, and it
  may pass it on.
- One conversation at a time, and one quiet for five minutes is ended.

A run with a human in it is not a measured run. The analyses of section 6 do
not count the human's news anyway, since it has no first-hand account to
measure drift from.

### 2.9c A village left running

Built on 2026-09-29, so a village can live on with room left for other work,
and visitors to the remote viewer can find it going and talk with it.
`hearthwick serve` gained three options.

- `--idle-speed` is the pace, in ticks a second, while nobody watches. It was
  flat out, which suits a batch run but keeps the speech model and a core busy
  for a village nobody is looking at. At 0.5 an in-game day takes about five
  minutes and a year about forty.
- `--checkpoint-every DAYS` saves the village as it goes, as `run` does, and
  once more when the server is stopped (Ctrl-C or SIGTERM). The tick in
  progress finishes first, and a stranger talking is let go, so what they
  said is kept.
- `--resume RUN_ID` carries a saved village on in its own log, with its
  settings from its own record.

What it costs. A thirty-villager day logs about 1.1 MB of events and 0.2 MB
of frames, so at 0.5 ticks a second the logs grow by about 400 MB a day of
wall clock, and more as the village grows. Replaying such a run from the start
loads the whole log, which will not do after a few days. Watching it live does
not. No run has gone past forty in-game days, so what a long run does to
memory, retrieval and the size of the village is not known yet.

### 2.9d Structures drawn from designs

Built on 2026-09-29, as step 1 of v0.2 (SPECIFICATION-v0.2.md section 1).
Every building in the 3D viewer was code, one function per kind of place. The
mill, the well and the homes are now designs, data the viewer draws and runs
(`data/structures/designs`, `hearthwick/designs.py`). Places without a design
are still drawn by code.

- **A design** is parts, joints, movements, triggers and claims. A part is a
  shape (box, cylinder, cone, sphere or wheel) with a size, a position, a
  rotation, a material and a parent, and may repeat round an axis, as the
  mill's four sails do. A joint lets a part turn (hinge) or slide against its
  parent. A movement spins, swings, slides or opens a joint while its trigger
  holds, easing in and out. What a design may contain is
  `data/structures/vocabulary.yaml`, and materials, for now only how they
  look, are `data/materials.yaml`.
- **The validator** refuses a design that uses anything outside the
  vocabulary, breaks a limit (40 parts counting repeats, a footprint of 5 by
  5, a height of 12, spin of 120 turns a minute), names a missing parent or
  material, has a part as its own ancestor, or moves a joint it lacks or with
  a trigger the world does not have. Each refusal comes with its reason, for
  the villagers who will design next. A loop of parents first hung it, found
  by its tests, and the checks that walk up through parents now wait until
  the parts form a tree.
- **Triggers.** The world's are always, day, night, rain and storm, which the
  viewer knows from the clock and the weather. A place's are worked (someone
  works there) and occupied (someone awake is there). Only the simulation
  knows those, so each frame carries them as `s`, for the places whose design
  waits on one. The windmill's sails turn while someone works at the mill,
  where they used to turn always. In the forty-day run someone worked there in
  68% of frames. The well's windlass turns while someone is at the well, which
  was 35% of frames. The cottages do not move, and every home is drawn from
  the cottage design in its own shades of plaster and roof tile.
- **In this edition.** Place states came with `designs`, which the paper's
  runs had off and this edition leaves out (README). The frames carry none,
  so the windmill's sails and the well's windlass stand still. The viewer
  draws the designs for any run, however old, since drawing changes nothing
  the run did.

Checked by `tests/test_designs.py`, and by rendering the viewer headless, on
2026-09-29, to see that the mill, the well and the cottages draw as before.

### 2.9e Villagers draw houses

A crafter drew the house for a couple waiting, through the model, as a design
the validator checked (`designs`). The paper's runs had it off, and this
edition leaves it out (README).

### 2.9f The physics bench

Each drawing was tried in MuJoCo, to see whether it stood, moved as its joints
said and did what it claimed (`designs`). The paper's runs had it off, and
this edition leaves it out (README).

### 2.9g Wants

Villagers formed wants of their own, to have something made or to know
something, which the crafters drew and built (`wants`). The paper's runs had
it off, and this edition leaves it out (README). Two traces stay. The market's
instructions for paying for a wanted thing and saving toward one stay in the
corpus, never retrieved, and `[!buy]` and `[!save]` always refuse (section
2.9i). The instructions of `data/instructions/wants/` that belong to a
temperament gene stay there for the gene library, and are never loaded
(README).

### 2.9h The land grows

Built on 2026-09-29, in `hearthwick/land.py`, decided by Scott the same day.
The greater village is 40 by 30 tiles. After about 230 days of the live
village its fields covered the southwest, houses stood in every gap, and two
plots of 3 by 3 were left, with none larger. A village that cannot build
stops: couples wait for ever and wanted things are refused.

- **When.** Only where something is started (`Building.start`), when no
  clear plot is left for a house or a wanted thing. The land never grows on a
  guess. Read-only checks, such as whether a crafter can start building or
  whether a drawing has room, ask `Land.room`, which says yes whenever the
  land could grow.
- **How.** The map gains a strip of open land along its east edge, 10 tiles
  wide (`GROW_BY`), wide enough for any plot. A road that ran to the old edge
  runs on to the new one. The forest and the stream stay where they were. The
  new ground is open grass, walkable at once, and the next plot is the one
  nearest the houses, as always.
- **Recorded.** Each growth is logged as `land_grown` with the new width and
  the roads extended, so a replay draws the map as it was at every moment.
  Checkpoints keep the width and the roads.
- **Switches.** On by default. `--no-land-growth` and `--profile paper` turn
  it off. A run recorded before it existed keeps its map, and `--with land`
  takes it up.
- **Owners.** A place built for a want records whose it is (`Place.owner`),
  as SPECIFICATION-v0.2.md section 1.4 asks. The 3D viewer labels each such
  structure with its name and owner, so a wanted thing is not taken for a
  house, and it redraws the ground when the land grows. A structure built
  before places carried owners gets its owner from `structure_built` in a
  replay.

**What building it found.** A conversation held at a building site can
outlast the site, which is removed when what stands on it is finished. Ending
it looked the site up, the step failed, and the live village paused at tick
33161. Wanted things finish far more often than houses, which made it likely.
Places are now looked up by `World.name_of`, which falls back to "the
village", and an activity or an avoidance whose place is gone ends at once.

Tested by `tests/test_land.py`: new land is open and the road runs on to it,
a house with no plot left is built on new land, without the switch the map
keeps its size, a drawing is not refused for room the land can make, the grown
land survives a checkpoint, a replay is drawn on the land as it grew, a
structure knows whose it is, a conversation outlasts its site, and old runs
and the paper keep the map as it was.

### 2.9i Materials and money

Built on 2026-09-30, as step 5 of v0.2 (SPECIFICATION-v0.2.md sections 4.2
and 4.3), in `hearthwick/goods.py` and `hearthwick/economy.py`, with the
goods in `data/goods.yaml`. Scott decided that a villager pays for what it
wants made and that houses stay the village's, so money never keeps a couple
from a home.

- **Goods.** Timber from the forest edge, stone and ore from a quarry, clay
  from a clay pit, iron made at a forge from ore and timber, and glass and
  cloth, which only the road brings. Each has a set price. What work yields
  to sell is goods too, by place and whoever does it: grain in the fields,
  flour at the mill, herbs at the shrine. The granary is untouched, since this
  is the share of a day's work a villager may sell for itself.
- **What a house takes.** With designs a thing took goods in proportion to
  the materials of its parts. Without them, as in the paper's runs and in this
  edition, a house is a cottage of 30 timber, so it is short of timber alone,
  and the crafters' instructions to cut stone, dig clay and ore, smelt iron
  and fetch from the road are never retrieved.
- **The places.** A village without them gains the quarry near the forest,
  the clay pit near the fields and the forge near the mill. They are placed
  when a run begins or takes materials up, on new land if need be (section
  2.9h), and drawn from designs of their own. The forge's bellows work while
  someone smelts there.
- **The crafters.** The village's stock is goods of each kind. The crafters
  see what the thing going up is short of (`timber_short`, `stone_short`,
  `clay_short`, `iron_short`, and `ore_short` or `ore_ready`). They fell
  timber, cut stone (`[!gather(what=stone, for=building)]`), dig clay and
  ore, and smelt iron (`[!smelt]`). Goods only the road brings are short to
  the merchants (`glass_short`, `cloth_short`), who walk out to the carts on
  the east road and fetch them (`[!fetch(what=glass)]`). `timber_ready` keeps
  its name, which learned and owned instructions carry, and now means there
  is enough of every good to build with. Houses are built this way, and cost
  nobody anything.
- **Money.** When money begins every villager living has 10 coins, and a
  child born later has none. A tick of work in the fields, at the mill or at
  the shrine yields what is made there. A villager carrying goods worth 3
  coins or more sees
  `carrying_goods`, and `[!sell]` takes them to the market. The merchant is the
  market. It buys at the set price less a tenth, the cut, which the living
  merchants share, and what it buys goes out by the road. A watch, a tale or a
  lesson yields nothing to sell, and a merchant lives on the cut and on any
  work it does. In stand-in days a merchant and a crafter worked the fields
  beside a farmer, which is why yields go by place and not by trade.
- **Paying for a want.** With wants, a drawn thing waited for its owner to
  pay for what it was made of (`want_unpaid`, `[!buy]`, `[!save]`). Wants are
  not in this edition, so coins only accumulate. The market's two
  instructions for it stay in the corpus, never retrieved, and `[!buy]` and
  `[!save]` always refuse, so the corpus and the lesson prompt are the paper's
  runs' own.
- **Death.** A villager's coins and goods go to its partner, or else are
  shared among its living children, or else go out along the road
  (`inherited`).
- **Recorded.** `purses_opened`, `sold` and `inherited`, and each
  villager's coins and goods' worth in the frames each in-game hour (`m`).
  Checkpoints keep purses, what each carries, and the stock.
- **The viewer.** A villager's panel shows its purse. The Building panel shows
  what the house going up still needs, with a bar. Sales and inheritances are
  lines in the feed. The new work has marks of its own.
- **Switches.** Both on by default. `--no-materials` adds none of the places,
  and `--no-money` opens no purses. `--profile paper` turns both off. A run
  recorded before them has neither, and `--with materials` and `--with money`
  take them up.

Tested by `tests/test_economy.py`. Without materials no places are added,
the places are added near their kind and only once, a house takes timber
alone and the crafters fell it and build it for nothing, purses open for
everyone living, work at a place yields what is made there whoever does it
and a watch yields nothing, goods sell less the cut, nothing is bought or
saved for, what a villager had goes to its heirs, money and goods survive a
checkpoint, the frames carry the purses, and old runs, the paper profile and
`--no-money` have none of it.

### 2.9j Keeping a village alive

Built on 2026-09-30, decided by Scott the same day, after the live village
(`20260929-142728-seed0`) was found dying out. On day 332 fourteen villagers
were left, aged 26 to 48, and no child had been born since about day 149. The
last children had grown through the fertile years, 11 to 20, while the
granary was too low to allow a birth, and nobody older could have a child.
The granary had fallen from between 100 and 330 to empty. A blight had struck
the fields every six or seven days all run, lasting four days and taking 15%
of the standing crop each day. More than thirty villagers had brought crops
in against it, but fourteen, three of them farmers, could not. The fields
filled their corner of the map and had nowhere to grow.

- **A wider fertile window** (`SimConfig.fertility`). Children may be had
  from 11 to 40, and elders count, since adults become elders at 20. With
  lifespans of 35 to 50 this is generous, and it was chosen because it is what
  saves this village. Under it two of the fourteen couples could have
  children at once, and a single man could court one of three single women.
  Up to 30, nobody could have. `--narrow-fertility` keeps 11 to 20.
  With the wide window elders may court and marry too, as Scott asked, so an
  unmarried or widowed elder can still become a parent. The instructions to
  court and to have a child are gated on `marriageable` and `fertile`, which
  carry the stage, not on `stage_adult`. As first deployed they were still
  gated on `stage_adult`, so no elder could have a child whatever the window
  said, and the live village's one possible couple, both elders, could not.
  That was found the same day.
- **Fields on new ground.** When no field can grow, clearing breaks a new
  field of 4 by 4 on free ground near the fields, on new land if the land may
  grow (section 2.9h). Every field is of kind `fields` and they grow one crop
  together, its size their tiles together. Work in the fields goes to
  whichever field has fewest hands, and every field is farming practice. Tied
  to land growth, so without it the fields stop where they are, as before.
- **Blight only in summer.** The blight's instruction says the crop "has stood
  wet and warm too long", yet only rain the day before was required, so it
  came in any season. Summer is now required, as the words say. This changes
  the world's instructions for every run, the paper profile's included. The
  paper's own results stand pinned to their tags.
- **Fighting a blight together** (`SimConfig.blight_fighting`, Scott's idea).
  A villager who knows of the blight may go and cut the rot out
  (`knows-fight-blight`, carrying `[!fight_blight]`), which the bold, the
  diligent and farmers lean toward, while the wary keep away as before. Each
  tick of anyone's work there counts, and 72 of them (three villagers for four
  hours) end the blight at once (`blight_ended`). Those near see it and hold it
  as news ("The blight has been cut out of the fields"), and those who fought
  remember doing it together. Work done is kept until the blight passes. The
  handler refuses when there is no blight, for children and visitors, and when
  the switch is off. `--no-blight-fighting` turns it off.
- **Richer fields** (`SimConfig.richer_fields`, Scott's call). A tile holds
  half as much again, tending grows the crop that much faster, and a tick of
  harvest brings in that much more (`food.RICH_FIELDS`). In the live village,
  even with a dozen hands in the fields, harvests covered 70 to 110% of a
  year's food, and twice they reached what the fields could hold. So every
  poor year left the granary low and refused births. As the hands fell to two,
  the harvests fell to a quarter of what the village ate. `--plain-fields`
  keeps the old yield.
- **Switches.** `fertility`, `blight_fighting` and `richer_fields` are on for
  new runs, off in `--profile paper` and for runs recorded before them, and
  `--with` takes them up.
- **Measured** by running the greater village without the model for
  decades under several sets of rules and seeds, with its people, births,
  deaths and granary year by year (`results/survival.md`). The script is not
  in this edition, since no result of the paper comes from it.

Tested by `tests/test_survival.py`: the wide window takes in elders to 40, an
older couple is not refused for age with it, elders court and have children
with it and not without, new ground is broken when no field
can grow and not without land growth, work goes to the field with fewest
hands, a new field survives a checkpoint, blight is summer's only, only those
old enough fight a blight and only while there is one, not without the switch,
enough hands cut it out, work half done is kept until it passes, and old runs
and the paper keep the old rules.

### 2.9k Web search

Villagers looked things up on the web, by temperament, through a lens and a
check (`search`). The paper's runs had it off, and this edition leaves it out
(README).

### 2.9l Drawings that work, and mending them

A drawing was placed from its plot and refused when it did nothing it claimed,
and a refused one could be mended (`designs`). The paper's runs had it off,
and this edition leaves it out (README).

### 2.9m Vehicles

A wanted thing the bench drove became a vehicle its owner drove and loaded
(`vehicles`). The paper's runs had it off, and this edition leaves it out
(README).

### 2.9n Where made things go, and to scale

A drawing said where its thing goes and what it does there, and clothes were
worn (`placing`). The paper's runs had it off, and this edition leaves it out
(README).

### 2.9o Set in the ground

Posts and frames set in the ground on the bench (`designs`). The paper's runs
had it off, and this edition leaves it out (README).

### 2.9p The crafter is told what the bench does

The drawing prompt said what the bench tests (`designs`). The paper's runs had
it off, and this edition leaves it out (README).

### 2.9q The crafter looks at what it drew

A crafter was shown a picture of its drawing, and of a refused one it mended
(`looking`). The paper's runs had it off, and this edition leaves it out
(README).

### 2.9r Things made before placing are re-placed

Things built before placing were moved where their makers said they belong
(`placing`). The paper's runs had it off, and this edition leaves it out
(README).

### 2.9s Assessors

Assessors, a trade an adult could take up, judged drawings before they were
built and things that stood (`assessing`). The paper's runs had it off, and
this edition leaves it out (README).

### 2.9t Which model draws

A comparison of language models drawing the same wants (`designs`, `wants`).
It used none of the paper's runs, and its scripts are not in this edition.
What it found stays in `results/draw_compare.md`.

### 2.9u Grown personas, and conversations as turns

Found on 2026-10-02, after the live village moved to Gemma 4 E2B on local
Ollama (`--llm-url http://localhost:11434 --model gemma4:e2b`). Scott saw
Jorun277 described as a baby while walking down the street, and a chat with
Per297 went in circles: "You are the guard at the watchpost." "You are not
the guard at the watchpost." Gemma held a reasonable conversation when Scott
talked with it directly, so the setup was at fault.

**Personas.** A child born in the village was given the persona "X is a baby,
born to A and B" and kept it. The persona is an instruction the villager
carries, read by the model whenever it speaks, so the village's grown
villagers, by then most of its 212, were told they were babies in every
conversation, and the viewer's panel showed it. With `grown_personas`, a
villager born here is described as it is now (`family.persona_now`): its
stage and trade, whose child it is, its temperament in the words a visitor's
persona uses (`character.TRAIT_PHRASES`), who taught it and whom it married,
by name rather than pronoun. It is rewritten when it changes stage, takes up
an apprenticeship or marries, and for everyone born here when a run resumes.
Each rewrite replaces its persona instruction and is logged as `persona`. The
run's record keeps it, with `stage_change`, `took_up_trade` and `apprenticed`,
so a viewer arriving later sees each villager as it is (hearthwick/follow.py),
and the panel shows an apprentice's trade ("learning to be a guard"). Founders
keep the personas they were written with, and visitors theirs. For example:
"Per297 is a guard of the village, son of Liv198 and Gunne205. Per297 keeps to
themselves, is not easily frightened, asks questions, wants to know who says
so, works without being asked, and improves a story in the telling. Bertil201
taught Per297 the trade."

**Turns.** A conversation reached the model as a transcript inside one user
message ("Conversation so far: Stranger: ... Per297: ... Your next line:"). A
small model lost track of who had said what and echoed the stranger's words
back as its own. Replaying Scott's lines through Gemma E2B with the same
instructions, the transcript gave "You are just taking a stroll" and "I do
not know who you are" over and over, and the same lines sent as turns gave
"Where are you going?", "Why are you here?", "I am at the watchpost." With
`chat_turns`, each line is its own message, the speaker's own lines as the
model's, for a stranger's chat (hearthwick/player.py) and for villagers
talking with each other (hearthwick/conversation.py). The place, the time and
the topic move into the system prompt. Without the switch both prompts are
exactly as before.

Within a conversation a villager has every line said so far. Between
conversations it keeps what it made of one (that it talked with someone,
and any news it kept, in its own words), not the words themselves.

Both are switches, on for new runs, off for `--profile paper` and for a run
recorded before them, taken up with `--with grown_personas --with chat_turns`.

Tested by `tests/test_personas.py` (a villager born here described as it is
now, its instruction replaced and the change logged, founders and a run
without the switch untouched, everyone refreshed on resume, a viewer arriving
later sees it, old runs and the paper keep the old personas) and
`tests/test_chat_turns.py` (a stranger answered turn by turn, villagers too,
both as before without the switch, old runs and the paper keep the
transcript).

### 2.9v Visitors' names

Asked for on 2026-10-02, after Ivar283 greeted Scott by his wife's name: a
visitor should have a name, kept against its account. The live village sits
behind Cloudflare Access, which tells the server who is visiting
(`Cf-Access-Authenticated-User-Email`). Before a visitor's first chat the page
asks "What should the villagers call you?", and the name is kept against that
account in `runs/accounts.json` (hearthwick/accounts.py), keyed by a salted
hash, never by the email. Reached without the login, as on localhost, the
page sends a random token it keeps in the browser instead. A name is letters,
with spaces, hyphens or apostrophes between them, at most 24, and not a
villager's name.

A named visitor is talked to and remembered by name (hearthwick/player.py):
the villager is told "Scott, who is from outside the village, has come up to
talk with you", and "You have talked with Scott before" if it remembers doing
so; each of the visitor's lines reaches the model as "Scott: ..."; afterwards
the villager remembers "I talked with Scott, who is from outside the village,
at the well", and what it keeps of what Scott said, Scott told it. The
visitor's lines are logged with `visitor`, and the viewer shows the name.
A visitor without a name is a stranger, as before. In Ivar283's prompt, sixty
replies with the name given once or on every line never misnamed Scott nor
copied a name prefix.

Tested by `tests/test_accounts.py` (a salted hash of the account, the login
before the browser's token, the name kept and the email never, what will not
do for a name, the page's question and answer, and a named visitor talked to,
recognised and remembered by name).

### 2.9w The design viewer

A page that showed every design in 3D, and generated looks for things
(`/designs`). It is not in this edition. The 3D viewer still draws the
founders' places from their designs (section 2.9d).

### 2.10 Infrastructure

| Service | Port | Used for |
|---|---|---|
| SGLang (vLLM until 2026-10-13), Qwen3.8-27B NVFP4 | 8355 | speech, the reframing lens, consolidation |
| Nemotron embed (2048-d) | 8360 | instruction and fact vectors |

Both run from this repository's `serving/` folder under docker compose
profiles. Speech and the lens ask for real output only (`thinking=False`,
`reasoning_fallback=False`). A reasoning model otherwise spends a short budget
thinking, and a villager can end up speaking the model's reasoning aloud.
Consolidation talks to the same model through `bear.evolution`, not through
the capped speech path.

Every request sends top-p 0.95 and top-k 20 as well as its temperature
(`llm_top_p`, `llm_top_k`). Speech and the lens sample at 0.8, and
`bear.evolution` sets its own 0.4. The September runs sent only the
temperature, and the server filled in top-p and top-k from Qwen3.8's
`generation_config.json`. On 2026-10-12 the server stopped filling them in,
and an omitted value then meant vLLM's own default (no
top-p or top-k limit). Sending them keeps every run sampling as September's
did. BEAR's generators get them through a wrapper (`llm.Sampled`) that fills
any value a call leaves out. A hosted model gets none, since it never had a
local server's defaults.

A call the server never answers (refused, timed out or failed, after BEAR's
own retries) is counted apart from a reply with nothing usable in it, and a
run records the count as `speech_errors` in `meta.json`. A run never stops
for a failed call. It goes on without the line, passes the news on word for
word, or writes no lessons, so a server that goes down and comes back leaves
a run that looks complete. `experiments/reproduce.sh` stops on any paper run,
or either counterfactual, that has one, and names what to redo. The count is
kept in the checkpoint, so a resumed run carries it on. A run made before the
count, or resumed from a checkpoint made before it, records none, and the
check (`experiments/unanswered.py`) refuses it as unmeasured rather than
passing it as clean.

A missing embedding service degrades to BM25 with a warning, and the run
metadata records which was used. BM25 is a development convenience, not a
valid configuration (section 6.5). The health check flags a run that asked for
the service and ended without it.

**When a server goes down (2026-10-18).** At 22:27 on 2026-10-17 a GPU reset
(NVIDIA driver event 153) took both servers down. The model server's container
restarted itself and answered again about four minutes later. The embedding
service kept reporting itself loaded at `/health` while every request failed
with a CUDA error, until its container was restarted by hand. A run going at
the time would have lost every model call in those minutes, which by the rule
above means redoing it, and would have stopped at its first embedding. The
same machine logged five bursts of graphics exceptions (event 13) on
2026-10-12, so it can happen again in a ten-year run.

So a call that fails while its server cannot answer waits for the server, up
to `server_wait_minutes` (30), asking it every 10 or 15 seconds, and is sent
again once it answers (`SpeechModel._generate`, `ServiceEmbedder._post`). Each
asks with a real request, a one-token reply or one embedding, since a health
address can say all is well when it is not. A call that fails while its server
answers fails as before. A lockstep run waits with the call, so an outage
waited out changes nothing in its outcome. The run's record counts the
outages and their seconds (`speech_outages`, and `outages` under `embedder`).
A model server still down after the wait leaves the call failed, and an
embedding service still down stops the run.

A run that stops on a failure no longer saves where it stopped. The tick it
failed in is half done, and saving it put that half-done tick over the last
checkpoint taken between ticks, so a resume would repeat part of a tick. The
run settles what is in flight, closes, and leaves its last clean checkpoint to
resume from (`__main__._run_to`). Tested by `tests/test_server_outages.py`. A live
test recreated the embedder's container under a running village
(`results/outage_test/`): the run waited 30 seconds, carried on, and recorded
the outage. The embedder in `serving/` now ends its own process on a
lost GPU, so Docker restarts it without anyone's help.

**Choosing the models** (2026-10-25, for the public repository). Anyone
without the paper's GPU can pick both models.
- **A hosted language model.** `--llm-provider anthropic|openai|gemini` with
  `--model` sends speech through BEAR's backend for that provider, with its
  key from the environment or `.env` (`SimConfig.llm_provider`). Any
  OpenAI-compatible server works through `--llm-url`, as before.
- **Other embedders, through BEAR.** `--embedder bear --embed-model <name>`
  wraps BEAR's own `Embedder` in `BearEmbedder`, a subclass of the service's
  client that keeps its cache and kept documents. `openai:<name>` calls
  OpenAI's embeddings API, or any server that speaks it when
  `OPENAI_BASE_URL` names it, a sentence-transformers name runs a local model,
  and vectors are made unit length as the service's are. The model is part of
  the run's record (`SimConfig.embed_model`), since another embedder makes
  another village. The threshold (0.15) and the same-news cutoff (0.85) were
  set for the service's model.
- **A run stops without its embedder.** `run` and `serve` set
  `embedder_strict`, so an embedder that does not answer at startup stops the
  run with what to do, where it fell back to BM25 before. `--embedder bm25`
  still runs without one. Library use and the tests keep the fallback.
- **Serving it yourself.** `serving/` holds the paper's two models, a compose
  file for SGLang and the embedding service, the embedding server and the
  preparation script. The embedder also runs on a CPU without Docker, where
  it took 0.07 s a query at 8 threads, and its vectors matched the GPU
  service's to a cosine of 0.9999.

With these, a run under a paper run's configuration is unchanged, and
`tests/test_model_choice.py` covers the choices.

---

## 3. Design rules

Each was learned by breaking it.

1. A precondition is a hard gate, and a preference is a soft tag. "It is
   night" and "nobody is watching the road" are absolutes. "The year was lean"
   is a reason. A preference in `required_tags` does not make behaviour
   likelier. It makes it impossible whenever the preference is absent.
2. A decision that changes nothing is not a decision. Handlers refuse markers
   whose effect is already in force, and the chooser falls through to the next
   candidate. This must hold for every entity, including the world.
3. Whatever can be refused must also be able to wear off. Rule 2 without
   recovery is a ratchet.
4. Things that always do the same thing do not need BEAR. Walking a path is not
   a decision. Deciding where to walk is.
5. Tags are embedded with the query, so tag text is not free. Adding or
   reordering a tag changes scores even when it gates nothing. Sort them, and
   treat any tag-level control as perturbing retrieval.
6. Soft tags require dense vectors. Under BM25, soft gating picks on lexical
   overlap and the village misbehaves outright.
7. Declared is not implemented. Two of the world faults were a capability
   declared in one table and absent from another.
8. A threshold written as an absolute count is a hidden dependency on
   population. Growing the village can make an instruction unreachable with no
   test failing and no instruction wrong.
9. A tag that is always present is not a tag. It cannot tell one day from
   another. Check how often each context tag is true, not just that it fires.
10. Filter before the cut, not after. Taking the top eight instructions and
    then keeping the `absorbing` ones left half of all reframings with no lens.
11. A fix that makes a measurement easier to obtain deserves more suspicion
    than one that makes it harder.
12. Check what a model writes against what the simulation can execute, down to
    the values. A marker with a wrong argument name or a place that does not
    exist is not an error. It is silently inert. Check what you write the same
    way. The first run of that check over the authored corpus found two
    faults.
13. Resolve before you choose. A candidate that cannot be carried out must not
    take a place among the options, or enough of them will leave nothing to
    choose. A fixed number of options only moves the point at which that
    happens, because what cannot be done grows with what an agent knows.

---

## 4. Measurement methodology

### 4.1 Why the obvious experiment is invalid

The first individuality measurement compared a village against a control
village with temperament instructions stripped, across runs. It gave a clean
result at ten villagers and reversed at thirty.

It is confounded in principle, not by noise. Change the policy and the village
takes a different course, so the two conditions never face the same situations.
No sample size fixes this. Structurally it is treatment-confounder feedback,
known since Robins in the 1980s, and it has recently been stated for LLM agents
(the Replay Gap, arXiv:2608.08239).

### 4.2 The paired design

Both measurements are paired and within-run. A logged decision is replayed with
one thing changed and everything else held fixed. Any difference is caused by
the change.

Action counterfactual (`experiments/counterfactual.py`). Each logged decision
is re-scored with the villager's temperament tags swapped for another
villager's. The situation, the knowledge and the query text are held fixed.
Marker resolution depends on the rest of the world, so the comparison stops at
the best-scoring instruction that carries an action.

Absorption counterfactual (`experiments/diffusion_counterfactual.py`). Each
reframing the simulation performed is replayed with the receiver's `absorbing`
instructions rebuilt from another villager's temperament. The speaker, the
sentence heard, the receiver's prior knowledge, and its name, stage and role are
held fixed. The logged run sampled at 0.8, so both halves of every pair are
re-decoded at temperature 0. The original is replayed too, so the baseline is a
matched call rather than the logged one. The `lens` event carries everything a
replay needs, so the measurement reads logs and never re-runs the village.

Rewording (`experiments/lens_divergence.py`). Among pairs where both sides kept
the fact, how far apart the two rewordings are (1 minus cosine), compared by
rank-sum with the no-lens loci pooled.

### 4.3 Controls

The absorption measurement carries two floors, because they answer different
questions.

- The decoder floor is the identical prompt asked twice. The model server
  batches continuously and is not bitwise deterministic even at temperature 0.
- The inert-tag floor is the loci whose alleles carry no `absorbing`
  instruction (sociability and diligence), pooled. Swapping them adds no
  filter, but it changes the query's tag text.

A claim about a trait must clear the second floor. At a few hundred pairs every
locus can clear the decoder floor, so it cannot separate a trait that matters
from a tag that merely jostles retrieval.

Each locus also reports a manipulation check. That is how often the swap
changed the retrieved lens at all. A swap that retrieved the same lens cannot
have caused anything. Significance is a one-sided Fisher exact test against the
relevant floor. No p-value is given where a locus helps define its own floor.

For action, candor is the floor. Its alleles carry no action markers.

### 4.4 Effective sample size

Nominal n is not effective n. Observations cluster within stimuli, and the
stimuli are the things the world can say. `experiments/world_balance.py`
reports the inverse-Simpson count of distinct (seed, event) stimuli beside
every run set. The Fisher p-values treat clustered observations as independent
and overstate significance, so the absorption result must be reported with the
effective stimulus count beside it.

---

## 5. What is measured, and what is not

| Question | Measured by | Unit |
|---|---|---|
| how far and how faithfully news travels | `knowledge_flow.py` | facts, by telling |
| whether knowledge changes behaviour | `knowledge_flow.py` | decisions |
| whether temperament changes what a villager does | action counterfactual | decisions |
| whether it changes what a villager keeps | absorption counterfactual | reframings |
| whether it changes how a villager retells | rewording | kept pairs |
| whether one villager's memory shapes the next one's | `memory_carryover.py` | told facts |
| whether a teller's personality changes the listener's memory | two-step counterfactual | chains |
| whether retrieval or the gates decide | `retrieval_ablation.py` | configurations |
| whether the world does more than one thing | `world_balance.py` | seeds, events |

Not measured, and not claimed, are the following. That this produces better
play. That it is cheaper. That villagers are believable to a human reader.
That anything here evolves. Growth and consolidation are observed in
rehearsals, not measured (section 6.7).

---

## 6. Results

### 6.1 How news travels

Over six ten-day runs of thirty villagers, 36 events reached at least one other
person: 18 sicknesses, 9 tales storytellers brought, 4 travelers, 2 raids, 2
storyteller arrivals and 1 harvest. A given event ended up held by a median of
25 of 30 villagers, in a median of 18 distinct wordings. A sickness reached a
median of 30, a traveler's news 18.5, and a storyteller's tale 11, so the
tales pull the overall median down from the 29.5 of the build before. The longest chain was eight tellings deep. Of
5,987 offers, 88.1% were already known to the receiver. Of what was new, 15.9%
was refused by the receiver's lens.

Only events that were told at least once count here. Weather is witnessed by
everyone and told by nobody, and once the world decided the sky every day it
was most of the events. Counted, it made the median event one wording.

Distance from the first-hand wording, by tellings from the witness, is below.

| Tellings | Median distance | n |
|---|---|---|
| 0 | 0.000 | 138 |
| 1 | 0.189 | 257 |
| 2 | 0.269 | 185 |
| 3 | 0.318 | 103 |
| 4 | 0.312 | 32 |
| 5 | 0.407 | 14 |
| 6 | 0.445 | 4 |
| 7 | 0.500 | 2 |
| 8 | 0.485 | 1 |

The distance rises through three tellings, holds at four, and is higher again
beyond, where few facts remain. Cosine distance is sensitive to length and
register, so this shows the wording diverging, not the content degrading.
Whether the facts survive is a separate measurement and has not been made.

A listener also chooses the kind. 393 of 736 facts (53.4%) were filed under a
different kind than the witness used, and 89.8% of those moved toward hazard or
sickness. Most were a sickness retold as a hazard (228), and next came plain
news retold as a hazard (100). News becomes danger as it travels. Nothing in
the corpus asks for that.

### 6.2 Deduplication is provenance

Of 5,276 duplicates, the root check caught 5,252 and vector similarity caught
24. The 24 descend from different events that amounted to the same thing
(0.853 to 0.890 cosine). The embedder earns its place in retrieval, not in
deduplication.

### 6.3 Knowledge becomes behaviour

3,548 of 20,947 decisions (16.9%) were taken on instructions that a `knows_`
gate keeps out of reach until someone has learned something. One decision in
six was made possible by diffusion. Villagers warn of the blight (726), the
sick well (558) and the raided road (462), keep away from each, and the healer
makes house calls. Farmers who knew of the blight went to cut it out 568
times, where everyone else kept away.

The measure now classifies an instruction by its gate. It used to count ids
starting `knows-`, which left out the farmers' answer to the blight and gave
14.2% on these runs.

### 6.4 Does temperament reach action and absorption?

Action. Swapping a villager's whole temperament changes 14.0% of decisions
(56/400). The floor is candor at 2.8%. By locus, caution 9.5%, curiosity 7.2%,
trust 6.8%, diligence 6.5%, sociability 6.0%.

Absorption and rewording are below. The decoder floor is 2.5% and the inert-tag
floor 2.0% (sociability 2.0%, diligence 1.9%).

| Swapped | Keep/discard flipped | Lens moved | Median rewording |
|---|---|---|---|
| candor | 4.8% | 100% | 0.151 |
| trust | 4.7% | 100% | 0.155 |
| caution | 3.8% | 99% | 0.037 |
| whole temperament | 3.4% | 94% | 0.114 |
| curiosity | 2.5% | 100% | 0.151 |
| no-lens loci | 1.9% to 2.0% | 0% | 0.007 |
| same prompt | 2.5% | 0% | 0.000 |

Every locus that carries a lens clears the inert-tag floor on rewording (p below
0.0001, rank-sum). On keeping, candor (p = 0.009) and trust (p = 0.013) clear
the inert-tag floor. Neither clears the decoder floor, which is higher on
these runs (p = 0.073 and 0.086), so on keeping nothing clears the floor a
claim has to clear. The manipulation check is clean. Swapping a locus with a
lens changes the retrieved instructions nearly every time, and swapping one
without a lens never does.

Keeping has a ceiling. On this world listeners refused only 15.9% of new news,
against 48.9% on the narrow world. A blight or a sickened well is plainly worth
keeping, and a decision nearly everyone makes alike leaves little for
temperament to flip. Rewording has no such ceiling, which is why it is the
steadier measure.

Candor is again the largest effect on what a villager keeps and the smallest
on what it does, since its alleles carry no action markers. Swapping the whole
temperament (3.4%) moves less than candor (4.8%) or trust (4.7%) alone.

How this result changed. The keep/discard measurement has now given six
answers. On a world that could say four sentences, trust flipped 12.2% and
nothing else cleared the floor. On a wider world, nothing cleared it, and 91% of
offers were kept whatever the lens. Both were measured while the lens was
composed by filtering the top eight instructions, which left half of all
reframings with no lens at all (rule 10). With the lens present, on three seeds
where vague traveler news dominated, all four lens loci cleared it. On six
seeds with concrete news, two did, and after feasibility re-ranking three of
four. On these runs, with 15.9% refused, none clears the higher floor. How
often temperament decides what is kept depends on how often keeping is in
doubt. How it rewords what is kept does not.

### 6.4a Does a personality reach the next villager's memory?

Descriptively, yes (`experiments/memory_carryover.py`, 598 told facts). When the
teller filed news as trouble, the listener did too 95.4% of the time, against
26.0% when the teller did not. Hedged tellings gave hedged memories 85.2% of
the time, against 55.5%. The listener's own allele adds to both. Wary listeners
filed untroubled news as trouble 33.9% of the time and bold ones 18.0%.
Suspicious listeners hedged an unhedged telling 62.7% of the time and trusting
ones 49.2%.

Causally, mainly in wording (`experiments/two_step_counterfactual.py`). It
takes 199 chains where B reframed news and then told it to C. It swaps B's
temperament, replays both steps, and holds C's lens, knowledge and decoder
seed fixed.

| Swapped at B | C's memory changed | p vs decoder | p vs inert | C's rewording | p vs inert |
|---|---|---|---|---|---|
| candor | 23.6% | 0.048 | 0.005 | 0.173 | below 0.0001 |
| caution | 23.2% | 0.063 | 0.009 | 0.108 | 0.17 |
| trust | 21.2% | 0.13 | 0.025 | 0.171 | below 0.0001 |
| curiosity | 16.8% | 0.44 | 0.21 | 0.164 | below 0.0001 |
| whole temperament | 15.8% | 0.53 | 0.29 | 0.126 | 0.070 |
| no-lens loci | 12.3% to 14.6% | - | - | 0.089 to 0.095 | - |
| same prompt | 15.5% | - | - | 0.050 | - |

"Memory changed" means the news no longer reached C, or C kept it differently,
or C filed it under another kind. The kind sets C's `knows_` tag, so a changed
kind changes what C can do.

The two floors swapped places on these runs. The decoder floor (15.5%) is above
the inert floor (13.5%), and a claim has to clear the higher one, so the
report now tests both. On memory, only candor clears it, and only just
(p = 0.048), with caution close (p = 0.063). On wording, B's trust, curiosity
and candor all move what C holds (p below 0.0001).

How this result changed. The build before feasibility re-ranking found candor
at B changing C's memory in 31.7% of 116 chains, when most news was traveler
news, whose kind is not in doubt. The build after found no memory effect above
the floor, when most news was a sickened well, which a listener can file as
sickness or hazard almost at random. These runs sit between. What holds across
all three is the wording.

The chains come from 26 events, 16.51 of them effective. The p-values treat
chains as independent and overstate significance. The raw model outputs are
saved, and `--from-raw` recomputes every statistic without a GPU.

### 6.5 Is retrieval doing the work?

Thirty villagers over two and a half days. "Similarity decided" is the share of
decisions where ranking by score chose differently from ranking by priority.
It is computed over the twelve best-scoring retrieved instructions that carry a
marker, before feasibility re-ranking, so it measures retrieval rather than
what the world allowed. Computed over the feasible candidates instead, it falls,
because re-ranking removes options that similarity preferred, and the metric
then confounds the two stages. The 9am column is the first dry morning (day 2).
On a wet one everybody shelters, whatever the configuration, and the check
tells nothing.

| Configuration | Similarity decided | Instructions used | 9am, first dry morning |
|---|---|---|---|
| hard gates, BM25 | 48.7% | 44/101 | 22 working |
| hard gates, embedder | 41.0% | 45/101 | 30 working |
| soft tags, BM25 | 95.0% | 23/101 | 25 of 30 talking |
| soft tags, embedder, t=0 | 75.2% | 34/101 | 14 working, 7 walking |
| soft tags, embedder, t=0.15 | 74.0% | 38/101 | 14 working, 6 talking, 5 walking |
| soft tags, embedder, t=0.40 | 42.5% | 30/101 | 16 working, 9 walking |

Soft tags hand the decision to similarity, but only with dense vectors. Under
BM25 most of the village spends the morning talking. The working configuration
(t=0.15) now sends about half the village to work at 9am, against five of
thirty on the build before food. Hard gates with the embedder send all thirty,
which is the trade the soft configuration makes for letting similarity decide.
Similarity decided less often than on the build before (74.0% against 84.4%).
The food and trade instructions added since are gated on their situations
(`harvest_ripe`, `crop_behind`, `graduating`), which would move decisions to
the gates, but the change has not been decomposed.

### 6.6 Can the world do more than one thing?

The world decides twice a day. Across the six seeds it made 54 decisions about
what happens and stayed quiet on 10 days. It fired weather 48 times, sickness
19, a traveler 14, a festival 6, a storyteller 3 and raiders 2. The harvest is
no longer the world's to decide. It was reckoned once in every seed, from what
the villagers brought in. Weather aside, the most common kind was 38.0% of 50
events. All six seeds produced different histories. 15 of 18 world
instructions were chosen at least once. The harvest festival never was,
because every harvest came in poor (section 6.10).

The world's own vocabulary is still small. It produced 21 distinct first-hand
sentences, 5.66 effective, and the most common was 29.3% of first-hand facts.
Weather is never told, so what bounds the absorption result is what listeners
actually heard. The 675 reframings came from 36 (seed, event) stimuli, 24.31
of them effective. That is the effective sample size behind section 6.4, and
its Fisher p-values treat the pairs as independent.

### 6.7 Growth and consolidation, observed

These come from rehearsals, not the measured runs, and are reported without
statistics.

A thirty-day run with growth on (`20260923-113539-seed51`) was stopped by
SIGINT at tick 1,664, resumed, and finished at 4,320 as one log. The log has
47,058 events and 19 checkpoints, with no tick going backwards and no
duplicate frame. Four children advanced to apprentice, two of them after the
resume. They wrote twelve instructions and chose eight of them 227 times.

- `learned-ilsa-storm-indoors` was chosen 153 times, always in rain or storm.
  Retrieval gated it by situation, though nothing in its scope said so.
- Four of the twelve named a place that does not exist, such as
  `avoid(place=outside)`, so that marker never fired. A fifth,
  `talk(target=Sena)`, never resolved because ids are lowercase. The check
  that let these through covered names only. It now covers values, and
  replaying the twelve through it refuses the four and keeps the fifth.
- `learned-bryn-inn-observation` was used 24 of 25 times at home. It is a
  lesson about the inn, and nothing in its scope tied it to the inn. Lessons
  are now tied to where they are set (section 2.8), and replayed, this one is
  gated on `at_inn`.

Consolidating twelve villagers from the run's final state with the live model,
after these fixes, wrote 36 instructions. 28 were kept and 8 refused. Every
refusal named something that does not exist, such as
`avoid(place=eastern_fields)` or `talk(target=traveler)`, or gave `work` an
argument it does not read.

In an earlier ten-day rehearsal, a child who had heard of a traveler wrote
itself "You know a traveler came up the east road with news from beyond the
village. Share this news with anyone nearby who might be unaware of the
developments." It chose that instruction 25 times.

### 6.8 Cost

The headline ten-day run of thirty villagers took nine and a half minutes on
one workstation (19:00:41 to 19:10:03 in its `meta.json`). That includes 806
speech, rewording and consolidation calls with no failures, and 6,669
embedding calls, of which 1,572 were served from an in-process cache. Choosing
an action costs no model call. A day without speech runs in a few seconds. The
cost follows conversation, so the warning fault cost time as well as validity.
Before the fix, the same seed on the same world made 2,588 model calls.

### 6.9 Learning a practice

How children came to shelter from the rain under `practices`, and whether
reinforcement helped. Practices are not in this edition. What was measured
stays in `results/practice_learning.md`.

### 6.10 Food

`experiments/food_economy.py`, on the same six runs. A year is eight days, so
each run has one harvest, on the first morning of winter (day 6).

| Seed | Brought in | Share of a year's need | Fields grew | Plots at the end |
|---|---|---|---|---|
| 1 | 168.3 | 75% | 3 times | 132 |
| 2 | 168.3 | 75% | 2 times | 121 |
| 3 | 160.3 | 72% | 2 times | 121 |
| 4 | 152.4 | 68% | 2 times | 121 |
| 5 | 168.3 | 75% | 4 times | 143 |
| 6 | 168.4 | 75% | 2 times | 121 |

Every harvest came in poor, between 68% and 75% of a year's food, just under
the 80% that counts as good, so the harvest festival never fired. The fields
grew two to four times, in winter, each time because adults chose to clear
ground (`food-clear-ground`). Nobody went hungry, since the granary starts with
enough to reach the harvest and a ten-day run ends before a poor one runs out.
Whether short harvests lead to hunger and then to more ground cleared needs
runs of about thirty days.

Work now happens. Adults and elders spent between 38% and 46% of dry working
hours at work, against 14% in the headline run before food. Food instructions
were chosen 126 to 248 times a run.

### 6.11 Traveling storytellers

`experiments/visitors.py`. A storyteller came in three of the six seeds, and
the world sent it when news had gone stale.

| Seed | Storyteller | Came, left | Conversations | Its three tales: villagers holding, longest chain |
|---|---|---|---|---|
| 3 | Tamsin | day 1, day 3 | 32, with 14 villagers | 23 (4), 10 (1), 30 (5) |
| 4 | Isolde | day 1, day 3 | 29, with 10 villagers | 30 (6), 11 (2), 25 (6) |
| 5 | Wystan | day 9, still there | 10, with 6 villagers | 6 (1), 6 (1), 3 (1) |

Across all nine tales the median reached 11 villagers, from 3 to 30
(`experiments/knowledge_flow.py`, by event kind), fewer than a sickness (30) or
a traveler's news (18.5). A storyteller who stayed its two days still had one
tale that reached every villager, through chains up to six tellings. Villagers
chose to go and hear the stranger 48, 34 and 11 times. Tamsin left with two pieces of the village's news and Isolde
with one, and Wystan held five when the run ended.

### 6.12 School, trades and masters

`experiments/trades.py`. Children went to school 636 times across the runs,
and elders taught 1,170 times. In every seed the two oldest founder children,
Hilde28 and Ilsa, graduated, between days 2 and 7. All twelve graduates chose
a trade: merchant five times, farmer three, healer twice, crafter and guard
once each. Merchant was the trade the village lacked (`needed_merchant`) in
every seed. Every graduate who chose farming was taken on by a parent, since a
parent in the chosen trade comes first. Apprentices qualified four times,
Gisla as a crafter in three seeds and Corin as a healer in one, each taking up
its trade as its role.

Choosing a trade competes with everything else a graduate might do. In seed 1
Ilsa graduated and chose the instruction she had just consolidated from her
childhood six times before she chose a trade. In seed 4 she sheltered from a
storm first.

---

## 7. Faults found, and what they cost

Recorded because each was invisible in aggregate and several inverted a
conclusion.

| # | Fault | Effect |
|---|---|---|
| 1 | `char_<id>` leaked into the embedded query in the impersonal condition | villagers partly retrieved on their own names, which inflated individuality |
| 2 | context tags were unsorted | tag order moved scores |
| 3 | across-run ablation | confounded in principle, replaced by the paired design |
| 4 | the traveler handler never refused a no-op | once everything else was in force, only travelers could fire, on 6 of 9 events |
| 5 | no world state ever recovered | every event was a one-way door, and the world's options shrank daily |
| 6 | a passing trader set a hazard | raids are refused while a hazard stands, so one merchant blocked raiders permanently |
| 7 | weather and harvest declared tellable with no template | 41% of world events could never become news |
| 8 | harvest witnessed within six tiles of the fields | nobody is there at that hour, so four harvests gave no facts |
| 9 | the world agent had no sampling | every seed produced identical events, so seeds were not replicates |
| 10 | placebo loci assumed inert, and the test checked one tag set | they moved the lens 5 to 12% of the time, so the floor was wrong |
| 11 | world thresholds were absolute counts sized for ten | at thirty, `road_watched` fired 54 of 54 days and `well_busy` 52 of 54 |
| 12 | raiders required an empty road | unsatisfiable at thirty, so raids were impossible at the scale the evaluation used |
| 13 | witnessing was place-bound within six tiles | one seed gave six days, four events and no knowledge at all |
| 14 | the fix for 13 made events village-wide | nothing was left to tell. Duplicates rose from 90% to 95% and lens calls fell from 635 to 144 |
| 15 | semantic deduplication was assumed to do the work | the root identifier catches nearly all duplicates, and vectors catch a handful |
| 16 | the lens took the top eight, then filtered | stage and role instructions won the slots, and half of all reframings had no lens |
| 17 | recall looked for `retriever.embedder`, which does not exist | relevance recall silently fell back to recency on every decision |
| 18 | learned instructions kept generation's priority (10 to 35) | below every authored band, so no learned instruction was ever chosen |
| 19 | consolidation ranked chats and news together | villagers learned their address book ("return to house 3 and speak with Osric again") instead of what they had heard |
| 20 | every moving learned instruction got `daytime` | a lesson about going home at night could never apply at night |
| 21 | generated markers were checked by name only | a wrong argument name made the marker inert |
| 22 | argument values were not checked | `avoid(place=outside)` and `talk(target=Sena)` were kept and never fired |
| 23 | a checkpoint was taken mid-conversation | knowledge being absorbed at that moment was lost (159 facts became 134) |
| 24 | resume opened the logs for writing | a resume would have truncated the run it continued |
| 25 | analysis scripts counted experience as news | chats would have appeared as events in every diffusion figure |
| 26 | learned instructions carried no place | a lesson about the inn was used 24 times of 25 at home |
| 27 | the check refused positional arguments and allowed missing ones | `[!avoid(well)]` would have been refused, and `[!work(ticks=2)]`, which does nothing, kept |
| 28 | two authored instructions failed the same check | a crafter who knew the grain had spoiled walked to the mill and never worked there, and the blight warning passed on "something you should know" |
| 29 | the world's vocabulary counted retellings as first-hand | it reported 174 first-hand sentences where there were 9 |
| 30 | weather shared the world's one decision a day with every event | weather took a third of all days, and a day spent on weather produced no news. The absorption result rested on 12 events |
| 31 | a festival was refused only on its own day | once weather had its own decision, festivals fired on consecutive days in four of six seeds, and a festival is never told |
| 32 | the sky was applied before the day's event was decided | the rain that ends a dry spell erased it first, so nothing needing a dry spell could happen. The well never sickened in six seeds, and blight, which needs recent rain, came in almost every run |
| 33 | a warning went to whoever was nearest | once blight was common, villagers warned neighbours who already knew in 29% of all decisions. A warning now goes only to someone who lacks news about the place it names |
| 34 | the brain sampled a top four and only then resolved, giving up when all four refused | from day 5 of the paper runs, up to a third of all decisions on some days chose nothing, and 714 in one run. Villagers who knew of the blight and the sick well stood idle in the rain, because warning nobody and avoiding places already avoided were their best options. Candidates are now resolved down the whole ranking before choosing |
| 35 | a reinforced practice could reach priority 75 | above most instructions that knowing something unlocks (67 to 78), so a habit could outrank a known danger. The ceiling is 66 |
| 36 | a crowd sheltering together reinforced each of them once for every other | every child's practice reached its ceiling on the first rainy day, so the reinforcement rate made no difference. Reinforcement now counts at most once a day |
| 37 | a learner's copy of a practice took its teacher's priority | a child started with its teacher's habit strength. A learner now starts at the practice's base strength |
| 38 | a good harvest needed the fields well watered and well worked, judged on yesterday | well watered means rain yesterday or today, and in rain villagers shelter, so yesterday's fields were empty whenever the fields were watered. No harvest in six seeds. Field work is now judged on the busiest of the last three days |
| 39 | "You are exhausted, go home and rest" preferred low energy rather than requiring it | at priority 70 it outranked going to work (65). In the headline run a tired instruction was chosen 703 times, and no villager was ever tired. It was the adults' most frequent choice in dry working hours (129 of 688 decisions, `experiments/food_economy.py`). The four tired instructions now require `energy_low`, as rule 1 says a precondition must |
| 40 | `go` resolved when the villager was already there | a bold farmer at the forest edge chose "walk out to the forest edge" seven times running and spent the morning there. Going where you already are is now refused |
| 41 | a farmer who heard of the blight avoided the fields | once food depended on the crop, the farmers who knew of a blight could not tend or harvest it. Nobody avoids their own workplace now, and farmers answer the blight by working it |
| 42 | villagers sought out a storyteller whatever they already knew | one storyteller had 87 conversations with 14 villagers. `stranger` now resolves only to a visitor with news the villager lacks, and the storyteller looks for a `listener` who lacks its own |
| 43 | a storyteller brought up the village's hazards before its own tales | once it had heard of the blight, two of its three tales reached nobody. A storyteller now tells first a tale the listener has not heard |
| 44 | growing up gave a villager no place in the village's work | a child who became an apprentice had no master, so "go to your mentor's workplace" resolved to nothing, and an apprentice who became an adult had no trade, so "go to your workplace" failed too. Graduates now choose a trade and a master, and qualify into it |
| 45 | a practice copy dropped its template's instruction tags | Hearthwick built each villager's copy of a practice from scratch and left out the template's own `tags`, which the retriever embeds. So a villager's "shelter from rain" was embedded differently from the shared instruction it replaced. Found when owner gating moved to `bear.ownership`, whose `own` copies the template whole. A one-day probe with practices on changed every copy and no choice. Without practices, the move left the decision log byte-identical |
| 46 | a visiting storyteller learned to shelter from the rain like a child | a storyteller arrived without the practice every adult villager holds, so it learned it by being told, and the practice experiment counted two storytellers among the children, reporting 14 learners of 12. Visitors now arrive holding the village's practices, and the experiment counts only villagers who began as children |
| 47 | births were checked when decided, not when carried out, and nothing paced them | both partners decided in the same tick, before either acted, so couples had two children at once, and every couple of age had a child on the first evening and again the moment the rules allowed. In a 20-day run 15 children were born on two days. The check now runs again when the action is carried out, a couple tries at most once a day, and a try succeeds with a chance of 0.2 |

Fault 9 carries the sharpest lesson about method. It was invisible because the
world's decisions were reasonable every day. A traveler arriving is not a bug
on any single day. It shows only in the distribution across runs, and only if
you check whether seeds differ at all.

Fault 13 was hidden by fault 4. The old world sent a traveler every day, so ten
chances at an unlikely witnessing eventually landed and the village always
learned something. Balancing the world removed the brute-force repetition and
exposed the fragility underneath.

Fault 14 would have produced a clean and meaningless result. An event everyone
saw first-hand is not news and never diffuses. It was caught only because the
lens-call count fell fourfold between two runs meant to be comparable.

Faults 11 and 12 are why world balance is a standing experiment. Scaling the
village from ten to thirty silently deleted behaviour. Nothing errored, no test
failed, and every instruction involved was still correct.

Faults 16 to 22 share a shape. Each part was present and did nothing, and
nothing reported it. The lens existed but was empty half the time. Recall ran
but fell back to recency. Learned instructions were added but never chosen.
Markers were kept but never fired. Each was found by looking at what a
mechanism actually did in the logs, not at whether it ran.

---

## 8. Not built

Milestone 4 is partnership, breeding, children and death. Births are built
(section 2.7b), and so are couples forming and the houses built for them
(section 2.7c), and death of old age (section 2.7d). Milestone 5 is long, seeded, multi-generation runs. Temperament is already a BEAR genome. The
genes are declared in `data/loci.yaml`, an allele is the instructions that
share a `temp_` gate and a `gene_category`, and `bear.evolution.breed` and
`express` do the breeding and expression (`hearthwick/genome.py`,
`tests/test_genome.py`). Every founder carries two copies of every gene, and
its temperament is what they express under the dominance scores the library
now carries. DESIGN.md section 7 has the plan for the rest.

Several other parts of the design are not built either. They are updating a villager's lens and persona at each
stage, `teach`, `trade` and `investigate`, and forgetting.

Open-endedness needs heritable variation, differential selection and an
unbounded behaviour space. Hearthwick has none of the first two. Consolidation
lets the corpus grow at run time, which is the seed of the third. No
open-endedness claim is made.

---

## 9. Reproducibility

```
docker compose --profile llm --profile embed up -d     # in serving/
bash experiments/reproduce.sh                          # six runs, every analysis
RUNS="$(cat results/paper_runs.txt)" bash experiments/reproduce.sh   # reuse runs
python paper/check_numbers.py

# the pieces, each writing results/<name>.json and .md
python -m hearthwick run --days 10 --seed 1 --village greater
python experiments/knowledge_flow.py $RUNS
python experiments/world_balance.py $RUNS
python experiments/memory_carryover.py $RUNS
python experiments/figures.py <first run>
python experiments/counterfactual.py <first run> --sample 400
python experiments/diffusion_counterfactual.py $RUNS --sample 400 --concurrency 8
python experiments/lens_divergence.py
python experiments/two_step_counterfactual.py $RUNS --concurrency 8
python experiments/two_step_counterfactual.py --from-raw results/two_step_counterfactual.json
python experiments/retrieval_ablation.py --village greater

# long runs
python -m hearthwick run --days 30 --checkpoint-every 1
python -m hearthwick run --resume <run_id>
python -m hearthwick view                  # watch at http://localhost:8010/3d
```

Name runs explicitly rather than with `--latest`. The retrieval ablation writes
runs of its own, so the latest runs are usually not the measured ones. Run logs
are not in the repository (about 10 MB each). The runs behind the current
numbers are listed in `results/paper_runs.txt`, and `reproduce.sh` regenerates
a comparable set. A new set gives nearby values rather than identical ones,
because speech is sampled and the model server is not bitwise deterministic.

Every figure is generated from a run's logs. None is assembled by hand, so a
figure cannot disagree with the run it came from. `check_numbers.py` recomputes
every number quoted in the paper and fails loudly when one drifts. The
absorption counterfactual saves its raw per-pair outcomes, so its analysis can
be redone without a GPU.
