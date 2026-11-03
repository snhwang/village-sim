# Health check of 20261021-151653-seed3

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

## ok: errors in the console log

```
{
 "Replacing duplicate instruction": 718
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
  "0": 0.738,
  "1": 0.829
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 11,
  "1": 11
 },
 "which": {
  "0": [
   "bryn",
   "freya",
   "a question about the village"
  ],
  "1": [
   "bryn",
   "freya",
   "a question about the village"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.514,
  "1": 0.558
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 2,
  "1": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "ilsa",
   "learned-ilsa-ask-village-questions",
   16
  ],
  "1": [
   "ilsa",
   "learned-ilsa-ask-village-questions",
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
  "each_day": 2,
  "each_time": 13
 },
 "lasts": {
  "life": 3,
  "news": 11,
  "season": 1
 },
 "answering no news": 2
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
   14,
   "hilde28",
   "hal",
   "the water at the well has turned"
  ],
  "1": [
   28,
   "freya",
   "nell",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 0,
  "1": 0
 }
}
```

## ok: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 27,
  "1": 28
 },
 "which (day, warner)": {
  "0": [
   14,
   "gisla"
  ],
  "1": [
   44,
   "gorm"
  ]
 },
 "villager-days over 40, by year": {
  "0": 0,
  "1": 0
 },
 "warnings that carried nothing, by year": {
  "0": 285,
  "1": 323
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 997,
  "1": 1291
 },
 "per villager": {
  "0": 32.2,
  "1": 36.9
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.019,
  "1": 0.026
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
