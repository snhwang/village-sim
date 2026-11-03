# Talk: a setting, small talk, and room to speak

**In the paper's edition:** only news from afar (section 2, `afar_news`) and
old news that fades (section 6, `news_fades`) are here, and the paper's runs
had both on. Natural talk (sections 1, 3 to 5 and 8) and natural names
(section 7) were off in every paper run and are left out (README), with
living memory and the scripts this page names. The rest of this page is the
record of how they were specified and built.

**Status:** proposed and built 2026-10-04. Scott asked for it (2026-10-04).
Natural talk is 667240f, news from afar and fading news 9f5f107, and natural
names 899e76e. Living memory, the family as memories rather than a family
tree, came with them (SPECIFICATION-items.md section 5, `hearthwick/lifememory.py`).
The comparison is `experiments/talk_compare.py`, and
`experiments/talk_measures.py` measures how villagers talked in any run.
**Scope:** the live village. Each part is behind a switch, the paper profile
turns them all off, and the case study's runs and the open-ended long run
(`results/long_run/runs.txt`) are unaffected.

## 0. Why

The open-ended run (`20261003-093714-seed1`, to day 185) showed six problems
with what villagers say:

- **Warnings set nearly every topic.** 86% of 27,658 conversations were about
  "raiders on the east road" (45%) or "the blight in the fields" (41%). A
  conversation's topic comes from the decision that started it, and warnings
  outrank chatting (priorities 68 to 70 against 45 to 60). The gregarious
  allele's "whatever is on your mind" started 1.3%.
- **Lines read as orders being obeyed.** Each line's prompt carries every
  speech instruction the speaker retrieves, one per gene plus role, stage,
  weather and food. A guard's first line drew on 11: "Rain still hasn't
  stopped. You saw the raiders on the east road, didn't you? Who told you?"
  About 5,200 lines began with "rain" or "rain's".
- **There's no room to talk.** Each line is "ONE short line, under 25 words"
  (80 tokens at most), and a conversation is 2 to 4 lines. Replies collapse
  into acknowledgements: "Good. Keep it plain."
- **There's no setting.** The prompt names Hearthwick and lists its places, but
  never says what kind of place it is or where the wider world begins.
- **News from beyond becomes local.** Storytellers' tales are not held as from
  afar, as web findings are, so a tale about distant wolves became a hazard on
  the east road. 1,883 of the run's 2,020 hazard facts came from tales.
- **Names with numbers.** The newborn name pool has 16 names a sex, and it
  counts the dead as taken. Once it runs out, a number becomes part of the
  name, and villagers say "Jory101" and "Col64" aloud.

## 1. A setting

A village-level instruction, gated on `talking` and `absorbing`, so every
speaker and every listener retrieves it. It's written from the village as it
stands: its size, its places, its people's work, the season, recent events
such as a harvest or a festival, and that the east road leads out to market
towns and the wider world, from which travellers and storytellers bring news.
It names no era. The village is an entity with
its own instructions, as the world agent is, and the setting is rewritten as
the village changes.

## 2. Hearthwick and afar

- Storytellers' tales and travellers' news are held as from afar, as web
  findings are already (`Fact.afar`). The prompt marks
  each such fact "(heard from afar)".
- A fact from afar never makes a local hazard. A tale of wolves in distant
  pastures is held as something far away. It can be retold, but it does not tag
  the listener `knows_hazard_east_road`, so it unlocks no warning about the road
  and no avoiding it.
- The conduct says that Hearthwick and its people and places are the
  villager's own, and that places beyond the east road are far away, known only
  from travellers and tales, so they are spoken of as far away and never as
  here. Villagers may then talk about the wider world, which the old rule
  ("name only the people and places of Hearthwick") discouraged.

## 3. Small talk

- Both sociability alleles carry small talk with an action marker.
  Gregarious villagers chat often and at length. Reserved villagers talk
  briefly about practical things. The stage chat instructions stay.
- The topic is concrete. A `topic=your_day` alias is filled by the talk handler
  from the speaker's own life: its day's work, a child's news, its partner,
  the season, something it heard. A vague topic got filled with whatever the
  villager knew best, which was the hazards.
- Under the shared check layer (`bear.checks`), a social check asks
  its own question when a villager wants company, so warnings can't crowd
  small talk out. Until then, section 6 frees most of those decisions.

## 4. A lighter character prompt

- At most three speech instructions a line: the persona, the role's, and the
  temperament ones that fit the moment best. The weather instruction comes only
  when the talk turns to the weather, and food only when it turns to food.
- They're framed as tendencies that show now and then, never all at once. Later,
  the speech instructions themselves can be rewritten as descriptions ("Nell
  tends to doubt hearsay") rather than orders.

## 5. Room to speak

- One or two sentences of spoken dialogue, up to 45 words, with a cap of 120
  tokens.
- Four to six lines a conversation.
- The opening topic starts the talk, and the talk may move on when it naturally
  would.
- On a slow server, longer lines slow a run in proportion to their tokens.

## 6. Old news fades

A hazard nobody has reinforced for a while stops unlocking warnings and
avoidance, and a warning goes only with fresh news about a place. In the open
run, warnings rose from 4% of decisions in year 1 to 28% in year 16 from
rumours that never faded, all after a single raid. A faded fact is still held
and can still be recalled and retold. It simply stops driving behaviour, the way
an old rumour does.

## 7. Names

Names never carry digits. The pool grows. A child may be named after kin who
have died, as families do, and a living villager who shares a name with
another is told apart by a byname, a patronymic such as "Jory Dagsson" or a
place such as "Jory of the mill". Ids keep their numbers for the record.

## 8. The comparison

`experiments/talk_compare.py` loads a copy of a run's checkpoint into a
throwaway village, samples recent conversations from its log, and has the
model hold each twice. A is the prompt the runs use, and B adds sections 1,
2, 4 and 5. Small-talk conversations are added, with B taking its topic
from the speaker's life (section 3). It writes `results/talk_compare.md`.

## 9. Switches

| Switch | Sections |
|---|---|
| `natural_talk` | 1, 3, 4 and 5 |
| `afar_news` | 2 |
| `news_fades` | 6 |
| `bynames` | 7 |

All four are off in `SimConfig` and `PROFILES["paper"]`, listed in `ADDABLE`,
and on from the command line for a new run (`--no-natural-talk`,
`--no-afar-news`, `--no-news-fades`, `--no-bynames` turn each off). So is
`living_memory` (`--no-living-memory`). The small-talk instruction lives in
`data/instructions/talk/`, loaded only with `natural_talk`
(`corpus.SWITCHED_DIRS`), since the embedding service's vectors depend a
little on what shares their batch and a gated instruction still moved others.

## 10. Decisions

1. **Is B better?** Read `results/talk_compare.md`.
2. **Line length.** 45 words, or another limit? Built at 45, with 4 to 6
   turns.
3. **Fading time.** How long a hazard takes to fade unreinforced, for example a
   season. Built at a year for a rumour or a sickness and two for a hazard
   (`knowledge.FADE_YEARS`), restarted only when it is lived again.
4. **Bynames.** Patronymics, places, or both? Built as patronymics after the
   father (Ivar Hakonsson, Liv Hakonsdotter), only when a name has been borne
   in the village before, with sometimes the name of a dead relative
   (`hearthwick/names.py`).
