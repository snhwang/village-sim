# Everything is a BEAR item

**In the paper's edition:** memories as BEAR items are built behind
`bear_memory` (SPECIFICATION-memory.md), which the paper's runs had on.
Family as memory (section 5, `living_memory`), natural names (section 6,
`bynames`) and the new talk prompt (section 7, `natural_talk`) were off in
every paper run and are left out (README), with the checks this page names
(`experiments/items_check.py`, `experiments/items_fading_audit.py`). Their
results stay in `results/items_check/`.

**Status:** proposed 2026-10-04. Scott: "Data entries should be BEAR with
tags", and "We can always start over." BEAR's side is built
(BEAR's `design/items.md`, stages 1 to 5, 2026-10-05) and checked on
the open-ended run's 13,275 facts (`experiments/items_check.py`,
`experiments/items_fading_audit.py`, results in `results/items_check/`).
Hearthwick's side is not started. Of sections 5 to 7, living memory,
character-only personas, natural names and the new talk prompt are already
built on Hearthwick's own store, behind switches (SPECIFICATION-talk.md).
**Scope:** a rebuild of how Hearthwick holds what villagers know, remember and
say, for a fresh village. It is built on main behind switches, like
everything new, not on a branch. A running village keeps the code it loaded,
so main can change under the open-ended long run. The paper's results are
pinned to the `paper-runs` and `paper-development` tags and are not
affected.
**Follows:** BEAR's item model, where chunks, statements and notes are
entities with declared tags and parents.

## 1. Items

Every piece of data a villager holds is an item:
- news and tales
- its own experiences
- family events
- what it learned as it grew up
- artworks and opinions, later

An item has:
- **content**, its text, and later a picture or a model
- **declared tags**, which say what it is and who may reach it: its owner
  (`char_dunn`, from `bear.ownership.owner_tag`), its kind (`news`, `hazard`, `experience`), and what it is
  about (`family`, `death`, `person:katrin`, `at:home_2`, `afar`).
  A `person:` tag names whom the item is about, never who told it or saw
  it. A retelling carries `person:*` from its parents (bear.items carry), so
  a tag naming a teller would collect every teller down a chain, and asking
  what a villager remembers of Katrin would return news that only passed
  through her.
- **parents**, the items it was made from. A retold piece of news has the
  telling it came from as its parent, and the witness's account is its root
- **timestamps**, when it was made and when it was last reinforced
- **salience**, how strongly it is held (section 4)

Items are retrieved under BEAR's rules, with required tags as hard gates and
soft tags raising the score. Behaviour is still instructions, and memory is
items. One retriever serves both, with one way of asking.

## 2. Responses are items

Everything the model writes is an item: each spoken line, each rewording of
news, each instruction a villager writes as it grows up, and later each tale
and opinion. A response carries the combined tags of everything retrieved to
make it, and those items are its parents. "Why did Dunn say that?" then has an answer in the
record. A line built from a family memory carries `family`, so a later
question finds it.

Queries are not items. A query is an act. What it retrieved is kept as the
response's parents, and the log keeps each query with its tags and results.

## 3. A series of questions

A prompt is assembled from several tagged questions to one store, not from
code that reads the state:

| Question | Required tags | Query |
|---|---|---|
| topic | `char_<self>` | what was just said |
| family | `char_<self>`, `family` | home and family |
| listener | `char_<self>`, `person:<listener>` | the listener |
| setting | `village` | the village now |

Each question gets its own slots, so no kind of memory crowds out another.
The old recall put news first, and that buried a widower's memory of his wife
under rumours. The same shape serves decisions, through the shared check layer
(`bear.checks`).

## 4. Short-term and long-term memory

- **Short-term.** Items made or reinforced in about the last day are always
  eligible.
- **Long-term.** Older items are recalled only when relevant, and their
  salience fades unless they are reinforced by being retold, recalled or lived
  again. Rumours fade fast, news more slowly, and family memories hardly at all.
- **Behaviour follows salience.** A faded hazard stops unlocking warnings and
  avoidance, while its item is still held and can still be recalled. That ends
  the fear loop in the open-ended run, where warnings grew to 28% of all
  decisions from rumours that never faded. It is the forgetting Talk of the Town
  has.

## 5. Family is memory, not a family tree

- **Events write items to the people they concern:**
  - a marriage to both partners: "I married Orla, the storyteller"
  - a birth to the parents and siblings
  - a death to the partner, children and parents, each in its own words:
    "My wife Katrin died in the night"
  - an apprenticeship to the apprentice and the master
- **Founders start with their family items written in,** since their
  marriages and children came before the village did.
- **Personas describe character only:** role, temperament and origin, with no
  living relationships and no names. A persona never goes stale, because
  relationships live in memory.
- **The prompt's genealogy line goes,** replaced by the family question.

Tags can reach behaviour, as `knows_` tags do now. A recent item tagged `death`
and `partner` could set a `bereaved` tag that unlocks mourning.

## 6. Names

- A pool of about 80 names a sex.
- Children sometimes named after kin who have died.
- A family name at birth from a parent ("Jory Dagsson"), used to tell living
  namesakes apart.
- No digits in any name. Ids keep their numbers for the record.

## 7. Talk

The proposed prompt from `SPECIFICATION-talk.md` and `results/talk_compare.md`
becomes the only prompt: the setting, at most three speech instructions as
tendencies, lines of up to 45 words, 4 to 6 turns, and news from afar spoken of
as far away. Small talk gets concrete topics from the speaker's own items.

## 8. What BEAR needs

- **Incremental indexing.** The retriever only rebuilds its whole index
  (`Retriever.build_index`), and a village adds thousands of items a day. The
  live village held 87,000 by day 600.
- **An item type** beside the instruction types, with parents, timestamps and
  salience, or a convention on `Instruction` that both applications share.
- **One item model for every BEAR application.** This is a BEAR core change,
  agreed before anyone builds it, and it needs Scott's OK.

### What BEAR has now (2026-10-05)

Each of these was checked on the open-ended run's facts, shaped as items.
- `bear.items.item()` makes an item: its owner as `char_<id>`
  (`bear.ownership`), classifications, descriptive tags, kind, parents, root,
  created and its own half-life. `respond()` makes a response that carries its
  parents' tags as named in `carry`, which for Hearthwick is `("person:*",)`.
- `Retriever.add`, `remove` and `reinforce` change the index without
  rebuilding it. With a cache directory, adding and removing give exactly what
  a rebuild gives: the same ids, similarities, scores and index_version. Without
  one, a service embedder's vectors move by up to 0.0015 with what shares their
  batch.
- `Context.select_all` and `select_any` choose before scoring. Selecting a
  villager's own memory by its owner tag returns what the hard gate returns,
  in the same order, in a tenth of the time (3.3 ms against 32.6 at 13,275
  items).
- `Context.now` fades each item by its half-life from when it was last
  reinforced, and `min_salience` leaves faded ones out before scoring.
- The audit records items as a delta log, and verifies every version a
  retrieval names by replaying it.

Hearthwick itself runs unchanged on BEAR's development repository. Checked
2026-10-06 at cecee66: all 522 of its tests pass, and a run with every new switch off
replays decision for decision as on f9b509c (`experiments/replay_fingerprint.py`,
3f14a406312cdaec), although the range removed the implicit prefilter by
context tags. The composer changed in that range too, but not on Hearthwick's
path: its speech composer sets no cap and no quotas, the corpus declares no
mandatory instructions, and the lens does not use the composer. New runs can
move to a pinned checkout of main. The open-ended long run stays on f9b509c
anyway, so a run that cannot be repeated finishes on the build it began with.

### How Hearthwick will use it

- An item's half-life is set when it is made, from its kind, in ticks of the
  run's own year: a year for a rumour or a sickness, two for a hazard, none
  for news, opportunities, family and what a villager lived. So the same thing
  fades over the same span of a life at any year length.
- What drives behaviour (the `knows_` tags) comes from items above
  `min_salience` 0.5. That reproduces today's fading rule exactly, for all 174
  villagers checked. Recall passes `now` without a floor, so an old hazard is
  still remembered and talked about, lower down.
- A witnessed duplicate is reinforced with `Retriever.reinforce` (boost 0), in
  one call per tick. Hearing something again never reinforces it, and its
  count stays in Hearthwick's own metadata.
- Nothing changes an item's metadata except `reinforce` and `add`, or the
  salience columns go stale with nothing to show it.
- `Context.now` is the run's tick, restored from the checkpoint on a resume,
  never wall time.
- A `person:` tag names whom an item is about, never who told it.
- Vectors are cached in a directory. An in-memory cache flushed when the run
  saves is being built in BEAR, and Hearthwick flushes it where it
  checkpoints, so after a crash the cache and the restored state agree.
- Hearthwick never removes items. Each removal would write the whole remaining
  set to the audit log.

## 9. Order

1. Agree the item model and incremental indexing in BEAR. Done, and built.
2. Hearthwick v0.3 on main, behind switches: items, combined tags on
   responses, the series of questions, salience and fading, family memory,
   character-only personas, names, and the new talk prompt. Family memory,
   personas, names and the talk prompt are built on the old store.
3. A trial village, read side by side with the open-ended run.
4. A fresh live village.
