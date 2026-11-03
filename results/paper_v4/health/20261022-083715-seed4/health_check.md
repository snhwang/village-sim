# Health check of 20261022-083715-seed4

Made by `experiments/health_check.py`. 0 of 17 checks flagged.

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
  "0": 0.797,
  "1": 0.828
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 5
 },
 "which": {
  "0": [
   "merrick",
   "nell",
   "a story from the old days"
  ],
  "1": [
   "merrick",
   "nell",
   "a story from the old days"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.521,
  "1": 0.445
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
   "learned-hilde28-mill-mold-check",
   4
  ],
  "1": [
   "orla",
   "learned-orla-verify-well-water",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 17
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 17,
 "recurs": {
  "each_time": 14,
  "each_day": 3
 },
 "lasts": {
  "news": 14,
  "season": 2,
  "life": 1
 },
 "answering no news": 0
}
```

## ok: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 3,
  "1": 2
 },
 "which (day, warner, listener, topic)": {
  "0": [
   16,
   "edek",
   "gisla",
   "danger abroad that could come this way"
  ],
  "1": [
   35,
   "fen",
   "gisla",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 0,
  "1": 0
 }
}
```

## ok: warnings that carried nothing

```
{
 "share by year": {
  "0": 0.001,
  "1": 0.003
 },
 "count by year": {
  "0": 1,
  "1": 2
 },
 "warnings by year": {
  "0": 1814,
  "1": 628
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 25,
  "1": 29
 },
 "which (day, warner)": {
  "0": [
   10,
   "hilde"
  ],
  "1": [
   37,
   "sena"
  ]
 },
 "villager-days over 40, by year": {
  "0": 0,
  "1": 0
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 760,
  "1": 1031
 },
 "per villager": {
  "0": 24.5,
  "1": 29.5
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.02,
  "1": 0.015
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
  "0": 4,
  "1": 3
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 31,
  "1": 35
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
