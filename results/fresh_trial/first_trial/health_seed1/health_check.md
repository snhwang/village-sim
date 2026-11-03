# Health check of 20261021-151653-seed1

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
 "Replacing duplicate instruction": 883
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
  "0": 0.832,
  "1": 0.843
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 14,
  "1": 12
 },
 "which": {
  "0": [
   "merrick",
   "nell",
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
  "0": 0.646,
  "1": 0.69
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
   "learned-hilde28-mill-grain-check",
   3
  ],
  "1": [
   "peder",
   "learned-peder-report-east-road-sickness",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 18
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 18,
 "recurs": {
  "each_time": 15,
  "each_day": 3
 },
 "lasts": {
  "news": 15,
  "life": 2,
  "season": 1
 },
 "answering no news": 1
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 4,
  "1": 4
 },
 "which (day, warner, listener, topic)": {
  "0": [
   8,
   "inga",
   "garrick",
   "danger abroad that could come this way"
  ],
  "1": [
   47,
   "osric",
   "fen",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 1,
  "1": 3
 }
}
```

## FLAG: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 59,
  "1": 43
 },
 "which (day, warner)": {
  "0": [
   16,
   "gisla"
  ],
  "1": [
   54,
   "wynn"
  ]
 },
 "villager-days over 40, by year": {
  "0": 1,
  "1": 1
 },
 "warnings that carried nothing, by year": {
  "0": 586,
  "1": 565
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 931,
  "1": 1464
 },
 "per villager": {
  "0": 31.0,
  "1": 44.4
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.034,
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
  "0": 3,
  "1": 1
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
