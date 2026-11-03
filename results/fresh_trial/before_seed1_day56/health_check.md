# Health check of 20261021-003622-seed1

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
  "0": 0.87,
  "1": 0.869
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 16,
  "1": 16
 },
 "which": {
  "0": [
   "merrick",
   "bryn",
   "a story from the old days"
  ],
  "1": [
   "merrick",
   "bryn",
   "a story from the old days"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.579,
  "1": 0.557
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1,
  "1": 2
 },
 "which (villager, lesson, day)": {
  "0": [
   "hilde28",
   "learned-hilde28-01",
   3
  ],
  "1": [
   "peder",
   "learned-peder-traveler-news",
   30
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
  "each_time": 17,
  "each_day": 4
 },
 "lasts": {
  "news": 16,
  "life": 2,
  "season": 3
 },
 "answering no news": 1
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 12,
  "1": 25
 },
 "which (day, warner, listener, topic)": {
  "0": [
   20,
   "fen",
   "bryn",
   "danger abroad that could come this way"
  ],
  "1": [
   49,
   "peder",
   "brannoc",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 217,
  "1": 122
 }
}
```

## FLAG: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 61,
  "1": 48
 },
 "which (day, warner)": {
  "0": [
   22,
   "edek"
  ],
  "1": [
   29,
   "gisla"
  ]
 },
 "villager-days over 40, by year": {
  "0": 10,
  "1": 2
 },
 "warnings that carried nothing, by year": {
  "0": 418,
  "1": 75
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1255,
  "1": 1771
 },
 "per villager": {
  "0": 41.8,
  "1": 52.1
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.058,
  "1": 0.034
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
  "0": 3,
  "1": 4
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
