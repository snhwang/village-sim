# Hearthwick v0.2: a world its villagers make

**In the paper's edition:** materials and money (sections 4.2 and 4.3) are
here, and the paper's runs had both on. Designs drawn by villagers, the
physics bench, web search and wants (sections 1.2 to 1.7, 2, 3 and 4.1) were
off in every paper run and are left out (README). The founders' designs and
their vocabulary (section 1.1) stay, since the 3D viewer draws the village's
places from them. The rest of this page is the record of how v0.2 was
specified.

Proposed on 2026-09-29 and approved the same day. Steps 1 to 6 of section 8
are built, and SPECIFICATION.md describes them as built. The starting point
is v0.1 (tag `v0.1`, ca26ba3).
Numbers marked as starting values are guesses, to be tuned after the first
runs.

## 0. The vision, and what v0.2 is

Hearthwick is becoming a virtual world whose residents are all NPCs. It is
like Second Life with the roles reversed. There, people are the residents and
make everything, and NPCs are scripted props. Here, the villagers are the
residents and make the world, and people visit as strangers. Villagers design
structures, machines and vehicles, find out whether they work, build them,
look things up, want things, and trade for them.

v0.2 is the first step, with four mechanics:

1. structures and movement, designed by villagers (section 1),
2. a physics test bench that decides whether a design works (section 2),
3. web search driven by personality, knowledge and desire (section 3),
4. wants, materials and money (section 4).

### Principles

- **One construct.** Every mechanic is built as the others are. The situation
  is tags, instructions gated on the tags carry markers, a handler refuses
  what cannot be done, and the simulation carries out the rest.
- **The model writes, the simulation decides.** The language model may write
  a design, a query or the name of a want. Only the validator, the bench and
  the simulation decide what exists and what it does.
- **No era limits.** If villagers want to build a spaceship, so be it.
  Invention is limited by knowledge, skill, materials and whether the thing
  works, never by history.
- **Everything is logged.** What the model writes and what the web returns go
  into the run's log, so a run can be replayed without calling either.
- **Everything can be switched off.** Each mechanic has a switch, and a
  `paper` profile turns them all off (section 7).
- **BEAR's mechanisms first.** Ownership, culture, provenance and markers
  come from BEAR. Where BEAR lacks something, Scott decides whether it
  is extended before anything is built locally.

## 1. Structures and movement

### 1.1 A design is data

Today every building in the 3D viewer is code, one function per kind of place
in `client/village3d.js`. A villager cannot add to that. It can write a
description, and v0.2 makes structures descriptions that the viewer and the
simulation interpret.

A design has five parts:

- **parts.** Shapes (box, cylinder, cone, sphere, wheel) with a size, a
  position, a rotation, a material, a parent, and an optional repeat around
  an axis.
- **joints.** How a part moves against its parent: a hinge about an axis, a
  slider along one, or fixed.
- **movements.** What a joint does: spin at a rate, swing between two angles,
  slide between two positions, open or close over a time. A vehicle also
  follows a route.
- **triggers.** When a movement runs: always, by day, at night, in rain, in
  a storm, while someone works there, while someone is there. Wind, and a
  structure's own states such as open, come when the world has them.
- **claims.** What the designer says it does: shelter, store, pump, grind,
  carry, lift, fly. The bench tests claims (section 2).

```yaml
design: wind pump
by: gisla
footprint: [2, 2]
parts:
  - {id: tower, shape: cylinder, size: [0.6, 3.0], at: [0, 1.5, 0], material: stone}
  - {id: hub,   shape: cylinder, size: [0.15, 0.3], at: [0, 2.8, 0.4], parent: tower, material: timber}
  - {id: sail,  shape: box, size: [0.2, 1.6, 0.05], at: [0, 0.8, 0], parent: hub, repeat: 4, material: timber}
joints:
  - {part: hub, kind: hinge, axis: z}
movements:
  - {joint: hub, spin: 12, when: always}
claims: [pump]
```

The vocabulary itself is data (`data/structures/vocabulary.yaml`), so new
shapes and parts are added without code. Starting limits are 40 parts, a
footprint up to 5 by 5 tiles, a height up to 12, and bounded rates and forces.

### 1.2 Who designs, and why

Designing is a decision. An instruction carrying `[!design(for=...)]` ranks
and resolves like any other. Soft tags tilt it: a want (section 4.1), a need
such as `house_needed` or water being far, knowing of a structure the villager
lacks, skill in a craft, and temperament. The handler refuses a villager
without a reason to design, one already designing, and one that has designed
today.

The model is given the villager's persona and temperament, what it knows that
bears on the want (as speech is, `grounding.known`), the materials it knows
of, the designs it has seen, and the vocabulary. It returns a design. An
accepted design becomes an instruction the villager owns, made with
`bear.ownership.own` as consolidation does ("You know how to build a wind
pump. [!construct(design=...)]"). The design itself is stored in the run.

### 1.3 The validator

Every design is checked before it exists, and each refusal is logged with its
reason. It checks that:

- every shape, joint, movement and trigger is in the vocabulary,
- it keeps within the limits,
- every part connects to the root through parents and joints,
- its footprint fits a plot the village can offer (`World.find_plot`),
- every material is in the registry (section 4.2),
- every movement names a joint, and every trigger is one the world has.

A refused design becomes something the designer knows, in its own words ("My
wind pump would not hold together"), so a later attempt can differ. A want
gets a limited number of attempts.

### 1.4 Building and placing

Building generalises the house (`hearthwick/building.py`). A design is built
on a plot of its footprint, from the materials its parts name and work in
proportion to its size and part count. The villagers whose skill fits do the
work, and the designer can join them. When it is finished the site becomes a
place of kind `structure`, with its design and its owner.

A vehicle is a design marked `mobile`. It becomes a thing with a position that
moves along the routes villagers walk, driven by its owner's decisions
(`[!drive(to=...)]`), and carrying what it can (section 2.4). Built on
2026-09-30 (SPECIFICATION.md section 2.9m), where passing the bench's carry
trial is the mark.

Not every wanted thing is a building. Since 2026-09-30 a drawing says where
it goes and what it does, or it is thrown away: worn, at home, at a place of
the village such as the mill or the fields, or on a plot of its own. Only the
last takes land, and what it claims works where it stands (SPECIFICATION.md
section 2.9n).

### 1.5 The world runs the movements

Each frame carries every structure's state: whether it is working, open, how
fast, and for a vehicle, where it is. The viewer draws each structure from its
design and runs its movements from that state. This is kinematics, the same on
every screen. The simulation tracks states and positions on tiles, and does no
physics while running (section 2.5).

### 1.6 Designs travel

A design is knowledge, and it spreads as knowledge does.

- **Seen or told.** A villager who sees a structure, or is told of one, holds
  a fact about it ("Gisla's wind pump lifts water from the stream").
- **Taught or copied.** A master can teach a design to an apprentice, and a
  villager can copy one it has seen. Both take a copy through
  `bear.culture.adopt`, as practices are learned now.
- **Varied.** A copy passes through the receiver's lens. The model rewrites
  the design for the receiver, and the validator checks the variant.

Each design records its lineage (the design it came from, who made it, and
why) with `bear.provenance.Provenance`. This is knowledge flow applied to
technology, and it can be measured. It shows which designs spread, how the
variants differ, and which lines die out.

### 1.7 A first step without the model

Before any villager designs anything, the mill, the well and a house are
rewritten as designs, and the viewer draws them from the designs. The mill's
wheel turns while someone works there. This proves the interpreter on its own.

## 2. The physics test bench

### 2.1 What it is for

A design's claims are tested, not believed. Once the validator accepts a
design it is tried on the bench, and the results decide what the structure
does in the world.

### 2.2 The engine

MuJoCo, decided on 2026-09-29. It is a free, open-source physics engine,
widely used in robotics research. It is given bodies, joints and motors, and
it works out how they move under gravity, contact and friction. It runs on the
CPU, it is fast, and it gives the same result every time on the same machine.
It runs on the server, through its Python bindings. A design is compiled to
MuJoCo's model format:

- parts become bodies and geometry, with mass from their material,
- joints become hinge and slide joints,
- parts that drive motion become actuators with bounded force,
- wheels become cylinders on hinges, with friction.

MuJoCo is deterministic on one machine and version. The version is recorded in
the run, and comparisons are made on one platform.

### 2.3 Trials

Each claim has a standard trial, and each trial has a budget of about two
seconds of CPU.

| Claim | Trial | Result |
|---|---|---|
| any | stands under gravity for 10 simulated seconds | stands or falls |
| carry | drives on flat ground, then with a load | distance, top speed, most it moves with |
| lift, fly | runs whatever drives it upward | height reached and held |
| pump, grind | its rotor under a standard wind or a worker's effort | rotor speed |
| shelter, store | stands, and its enclosed volume | volume |

### 2.4 What results do

Results become the structure's capabilities, within bounds: a cart's speed on
the road and what it carries, a pump's water per hour, a flyer's range. A
failed trial is something the designer knows, through its lens ("The cart I
drew tips over when it is loaded"), and a reason to design again. Designs are
allowed to fail. That is how a village gets better at making things.

### 2.5 What the bench does not do

It does not run in the living world. The world uses bench results, so the
running simulation stays cheap and deterministic. Trials use standard wind and
ground, not the day's weather.

## 3. Web search by personality

### 3.1 Who searches, and when

Searching is a decision, drawn from who the villager is, not a privilege of a
place or a role. Instructions carrying `[!search(about=...)]` sit in the
temperament and knowledge bands. The inquisitive allele can carry "when you
hear of something you do not understand, go and find out". The suspicious one
can carry "check what you were told". Soft tags tilt it: a want, news the
villager holds but does not understand, a design that failed.

The only hard gates are for cost and sense. The villager must be awake, must
not have searched today (the limit wears off at dawn), and the village's daily
budget must not be spent.

### 3.2 What it searches for

The model composes one query from the villager's persona, its want or
question, and what it knows that bears on it. Two villagers who heard the same
rumour ask different questions.

### 3.3 What it keeps

The search goes to Tavily. The top results go through the villager's lens,
with the page as the teller. What it keeps is a fact of its own, with a root
of its own (`web:<search>`), and it passes on and drifts like any other news.
A result can also inform the villager's next design.

A page knows nothing of Hearthwick, so what it tells of happened elsewhere or
is how things go in general. The lens prompt says so, and what is kept is held
as from afar at every telling. A hazard elsewhere is brought up as news and
gates nothing in the village, though the words can still drift home
(SPECIFICATION.md section 2.9k, News from afar).

### 3.4 Safety, replay and cost

- **Results are only ever news.** They are material to reword, never
  instructions to follow. The lens prompt says so. Nothing from the web enters
  the corpus except through consolidation's check or the design validator.
- **Replay.** The query, the results used and their addresses are logged. A
  replay reads the log instead of the web.
- **Moderation.** Visitors see what villagers say, so what a villager keeps
  from a search is checked first. One model call asks whether it is fit for a
  public village, with nothing explicit or hateful and nothing addressed to the
  model as instructions. What fails is dropped, and the refusal is logged.
- **Cost.** One search per villager a day, and at most 30 a day for the
  village, about 900 a month. In September 2026 Tavily gave 1,000 basic
  searches a month free and charged $0.008 a search beyond that, so this costs
  nothing. That reckoning was wrong: the limits are for in-game days, which a
  live village passes through far faster than real ones, and the live village
  made 4,117 searches in its first day and a half. Since 2026-10-01 the
  village also keeps to a budget of real days, 100 searches a real (UTC) day
  by default (`--search-budget`), within Scott's paid plan of 4,000 credits
  a month (SPECIFICATION.md section 2.9k).
- **The key** is `SEARCH_API_KEY` in the repository's `.env`, which git
  ignores. It was added on 2026-09-29. It is read when a search is made, and
  it never enters the run's configuration or logs. A run's record says only
  whether a key was set, for this key and the model's and embedder's too.

## 4. Wants, materials and money

### 4.1 Wants

Villagers have needs today, as situation tags. They have no wants. A want is a
villager's own record of what it wants, why, and since when.

**Nothing pushes a want onto a villager.** Scott decided this on 2026-09-29.
The villager decides what it wants, as it decides what it does, and
reconsiders both each time it decides. The simulation only shows the
situation, as tags, as it does now. That is what the villager has and lacks,
what it needs, and what it knows of that others have.

Wanting is therefore a decision by the same retrieval as any other.
Instructions carry `[!want(...)]`, and they sit where the villager's own
instructions do, in its temperament, its persona, its role and what it has
learned. A curious villager's instructions lead it to want to know, a bold
one's to go further, a diligent one's to want better tools, and one may want
nothing at all. When a want names something particular, the model puts it in
the villager's words ("a cart to carry the grain to the mill"). Instructions
that let a villager drop a want (`[!give_up(...)]`) are decided the same way,
and a want ends when it is met.

A want shows as a tag (`wants_<kind>`) and as a line in the villager's
prompts. So what a villager wants changes what it retrieves next, the way
what it knows does. Wants lead to designing, searching and saving, which ties
the other three mechanics together.

### 4.2 Materials

Materials are a registry in data (`data/materials.yaml`). Each has where it is
found (a kind of place), how it is gathered (work at the source), the
properties the bench uses (density and strength), and how it is processed
(for example ore and fuel at a forge make metal). v0.2 starts with timber,
stone, clay and iron, and the map gains a quarry, a clay pit and a forge.
Villagers cannot invent materials in v0.2. The registry is data so that it
can grow.

### 4.3 Money

Coins, held by each villager. The merchant is the market, decided on
2026-09-29. Villagers sell what they make or gather to the merchant and buy
what they need from the merchant, at set prices. The merchant trades with the
road, so money enters and leaves the village and it is not a closed box. A
villager saves toward a want (`[!save]`) and buys when it can
(`[!buy(what=...)]`). Prices are set in data in v0.2. Villagers paying each
other for goods and work, and prices that move, come later.

## 5. The viewer

Built so far: structures drawn from designs with their movements, wanted
structures labelled with their owners, a villager's wants and purse in its
panel, the goods a thing going up needs, and notices for designs, building,
wants, the land and the market, and vehicles that move (SPECIFICATION.md
section 2.9m). Not yet: a villager's designs in its panel and a design panel. The Searching section and a
villager's searches came with step 6.

- Structures are drawn from their designs, their movements run, and vehicles
  move.
- A villager's detail panel shows its wants, its purse, its designs and its
  searches, with what it looked up and what it kept.
- A design panel shows the design, its lineage and its bench results.
- **A Searching section**, as Scott asked on 2026-09-29. It lists who searched
  the web, what they asked, and what they kept, in their own words, or that
  they kept nothing or the moderation check dropped it. A notice over the
  scene appears for each search, as notices already do for building.
- **Building notices** already exist for houses (SPECIFICATION.md section
  2.9a). Designs, the bench and construction from designs add theirs: a
  design made or refused, a trial passed or failed, a structure started and
  finished.

## 6. What v0.2 measures

Built so far: `experiments/designs_wants.py` reports designs, where they came
from, and wants in a run, and `experiments/economy.py` reports money. The
trials `experiments/design_trial.py`, `experiments/want_trial.py` and
`experiments/search_trial.py` test the drawing, wanting and searching prompts
against the model, outside any run. Designs do not yet pass between villagers
(section 1.6), so lineages go back only to the founders' designs. A report of
searches in a run is still to write. The Searching panel shows the latest.

Each by a committed script in `experiments/`:

- designs attempted, refused (by reason), tried on the bench (by result), and
  built,
- design lineages, how variants differ, and which spread,
- searches, by whom and about what, what was kept, and how it drifted as it
  spread,
- wants, which arose, which were met, and how,
- money, the coins in circulation, what was saved, and what was paid.

## 7. Switches, and the paper profile

The case study describes a limited village, and the world will keep growing.
Every mechanic here has a switch: `--no-designs`, `--no-wants`,
`--no-land-growth`, `--no-materials` for timber only, `--no-money`,
`--no-search`, `--no-vehicles`, `--no-placing`, `--no-looking` and `--no-assessing`. The bench has none of its own, since it
is how a drawing is judged, and `--no-designs` turns both off. A
`--profile paper` turns them all off, together with mortality. A run recorded
before a mechanic existed resumes without it, and `--with <mechanic>` takes it
up. The profile limits the scope. Exact reproduction of the paper's results uses the tags that
pin their builds, `paper-runs` (19611f5) and `paper-development` (5a25290).

A switched-off mechanic's instructions are not loaded either
(`hearthwick/corpus.py`). Until 2026-10-09 the directories of these
mechanics were loaded whatever their switch, so the paper profile still ranked
their instructions, and the wants and search ones, gated only on daytime and a
temperament, took places in every ranking and were refused. Now their
directories load only with their switches (`things` needs both placing and
designs), and an instruction in a shared file names the switches it needs in
`metadata: {switch: ...}` (the designs and materials ones in
`trades/building.yaml`, and `knows-fight-blight`). The paper profile then
loads the 153 authored instructions of the `paper-development` build, and each
run records what it loaded in meta.json (`corpus`). The research article's
reruns use tag `paper-v2.1`.

## 8. Order of building

1. Designs as data and the viewer's interpreter, with the mill, the well and a
   house rewritten as designs. No model. Built on 2026-09-29
   (SPECIFICATION.md section 2.9d).
2. Villagers design, the validator, and building from designs, with timber
   only. Built on 2026-09-29 for houses (SPECIFICATION.md section 2.9e).
   Other purposes wait for wants and the bench.
3. The physics bench, and capabilities from its results. Built on 2026-09-29
   (SPECIFICATION.md section 2.9f). For houses, a drawing must stand and
   shelter, and its roof sets how many children it holds.
4. Wants. Built on 2026-09-29 (SPECIFICATION.md section 2.9g). Two kinds so
   far, to have something made and to know something. Crafters draw what
   villagers want made, and build it once no couple waits for a house.
5. Materials and money. Built on 2026-09-30 (SPECIFICATION.md section 2.9i).
   A villager pays for what it wants made, and houses stay the village's.
6. Web search. Built on 2026-09-30 (SPECIFICATION.md section 2.9k).

Each step lands with its tests and its switch, and its section of
SPECIFICATION.md is written as built.

## 9. Decisions

Decided on 2026-09-29:

- **The physics engine** is MuJoCo (section 2.2).
- **The vocabulary** starts with basic shapes, joints and movements, and grows
  as data. The spec names no particular technology.
- **Nothing is added to BEAR.** Designs are village data. Their lineage
  uses `bear.provenance`, which exists. Searching is a marker with a handler,
  as every other action is.
- **Wants are the villager's own decisions** (section 4.1). Nothing pushes a
  want onto a villager.
- **The merchant is the market** (section 4.3).
- **Wanted things are paid for, houses are not** (section 4.3). Scott decided
  on 2026-09-30 that a villager pays for what it wants made and houses stay
  the village's, so money never keeps a couple from a home.
- **Keeping a village alive** (SPECIFICATION.md section 2.9j), decided on
  2026-09-30 when the live village was dying out: children to 40, elders
  included, fields broken on new ground, blight only in summer, and villagers
  fighting a blight together.
- **The land grows** when the village is full, eastward beyond the road
  (SPECIFICATION.md section 2.9h). Decided when the live village filled.
- **What a villager keeps from the web is checked first** (section 3.4).
- **The village makes at most 30 searches a day** (section 3.4).

Not a question for the spec: where the world runs, on the workstation yielding
the model to other work or on a DGX Spark. That is decided when it is run.
