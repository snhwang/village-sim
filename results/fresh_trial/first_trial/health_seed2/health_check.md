# Health check of 20261021-151653-seed2

Made by `experiments/health_check.py`. 2 of 17 checks flagged.

## ok: model calls never answered

```
{
 "speech_errors": 0,
 "from": "record"
}
```

## ok: the run without the embedder it asked for

```
{
 "asked": "service",
 "used": "service"
}
```

## ok: servers that stopped answering, waited out

```
{
 "model": {
  "outages": 0,
  "seconds": 0.0
 },
 "embedder": {
  "outages": 0,
  "seconds": 0.0
 }
}
```

## ok: errors in the console log

```
{
 "Replacing duplicate instruction": 1045
}
```

## ok: the granary empty for long

```
{
 "longest empty streak by year": {
  "0": 0,
  "1": 0
 },
 "empty days by year": {
  "0": 0,
  "1": 0
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.812,
  "1": 0.86
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 11,
  "1": 6
 },
 "which": {
  "0": [
   "merrick",
   "nell",
   "a story from the old days"
  ],
  "1": [
   "edda",
   "gisla",
   "news of the day"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.658,
  "1": 0.679
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1,
  "1": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "hilde28",
   "learned-hilde28-forest-fight",
   3
  ],
  "1": [
   "corin",
   "learned-corin-avoid-sick-well-night",
   28
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 21
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 21,
 "recurs": {
  "each_time": 19,
  "each_day": 2
 },
 "lasts": {
  "news": 19,
  "season": 1,
  "life": 1
 },
 "answering no news": 0
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 5,
  "1": 4
 },
 "which (day, warner, listener, topic)": {
  "0": [
   12,
   "hilde28",
   "mabel",
   "the blight in the fields"
  ],
  "1": [
   32,
   "edda",
   "hal",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 8,
  "1": 2
 }
}
```

## FLAG: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 45,
  "1": 31
 },
 "which (day, warner)": {
  "0": [
   12,
   "hilde28"
  ],
  "1": [
   41,
   "wynn"
  ]
 },
 "villager-days over 40, by year": {
  "0": 1,
  "1": 0
 },
 "warnings that carried nothing, by year": {
  "0": 562,
  "1": 653
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 898,
  "1": 1267
 },
 "per villager": {
  "0": 29.9,
  "1": 38.4
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.032,
  "1": 0.037
 }
}
```

## ok: grown villagers stuck in one place and activity

```
{
 "still for 48+ waking ticks, by year": {},
 "first cases": []
}
```

## ok: years without a birth

```
{
 "births by year": {
  "0": 2,
  "1": 7
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 30,
  "1": 33
 }
}
```

## ok: deaths before old age

```
{
 "deaths": 0,
 "young": []
}
```
