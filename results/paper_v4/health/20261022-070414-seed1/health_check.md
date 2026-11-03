# Health check of 20261022-070414-seed1

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
  "0": 0.824,
  "1": 0.883
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 4
 },
 "which": {
  "0": [
   "freya",
   "bryn",
   "a story from the old days"
  ],
  "1": [
   "wynn",
   "ada",
   "news of the day"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.617,
  "1": 0.725
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
   "learned-hilde28-2",
   3
  ],
  "1": [
   "gisla",
   "learned-gisla-warn-forest-edge",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 15
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 15,
 "recurs": {
  "each_time": 10,
  "each_day": 5
 },
 "lasts": {
  "news": 12,
  "life": 2,
  "season": 1
 },
 "answering no news": 1
}
```

## ok: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 2,
  "1": 2
 },
 "which (day, warner, listener, topic)": {
  "0": [
   4,
   "tobin",
   "nell",
   "danger abroad that could come this way"
  ],
  "1": [
   28,
   "ilsa",
   "sten",
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
  "0": 0.004,
  "1": 0.005
 },
 "count by year": {
  "0": 13,
  "1": 6
 },
 "warnings by year": {
  "0": 3149,
  "1": 1235
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 26,
  "1": 21
 },
 "which (day, warner)": {
  "0": [
   23,
   "gisla"
  ],
  "1": [
   31,
   "bryn"
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
  "0": 996,
  "1": 1101
 },
 "per villager": {
  "0": 33.2,
  "1": 33.4
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.032,
  "1": 0.035
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
  "0": 3
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
