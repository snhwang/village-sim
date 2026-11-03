# Health check of 20261021-003622-seed2

Made by `experiments/health_check.py`, read to day 56. 2 of 16 checks flagged.

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
  "0": 0.841,
  "1": 0.878
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 11,
  "1": 13
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
  "0": 0.518,
  "1": 0.61
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
   "learned-hilde28-forest-fighting",
   2
  ],
  "1": [
   "hilde28",
   "learned-hilde28-wolf-warning",
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
  "each_time": 18,
  "each_day": 3
 },
 "lasts": {
  "news": 21
 },
 "answering no news": 0
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 12,
  "1": 14
 },
 "which (day, warner, listener, topic)": {
  "0": [
   26,
   "garrick",
   "cadell",
   "danger abroad that could come this way"
  ],
  "1": [
   46,
   "edek",
   "bryn",
   "raiders on the east road"
  ]
 },
 "listener-days over 3, by year": {
  "0": 118,
  "1": 257
 }
}
```

## FLAG: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 47,
  "1": 60
 },
 "which (day, warner)": {
  "0": [
   25,
   "gorm"
  ],
  "1": [
   41,
   "wynn"
  ]
 },
 "villager-days over 40, by year": {
  "0": 1,
  "1": 8
 },
 "warnings that carried nothing, by year": {
  "0": 369,
  "1": 221
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1147,
  "1": 1976
 },
 "per villager": {
  "0": 38.2,
  "1": 58.1
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.046,
  "1": 0.052
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
  "0": 30,
  "1": 34
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
