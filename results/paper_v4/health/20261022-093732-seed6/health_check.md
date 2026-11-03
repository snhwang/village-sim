# Health check of 20261022-093732-seed6

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
  "0": 0.841,
  "1": 0.821
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 12,
  "1": 4
 },
 "which": {
  "0": [
   "bryn",
   "freya",
   "a question about the village"
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
  "0": 0.717,
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
   "ilsa",
   "learned-ilsa-1",
   4
  ],
  "1": [
   "gisla",
   "learned-gisla-verify-well-water",
   32
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 12
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 12,
 "recurs": {
  "each_day": 2,
  "each_time": 10
 },
 "lasts": {
  "news": 11,
  "season": 1
 },
 "answering no news": 0
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
   7,
   "garrick",
   "ada",
   "danger abroad that could come this way"
  ],
  "1": [
   29,
   "frida",
   "katrin",
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
  "1": 0.003
 },
 "count by year": {
  "0": 15,
  "1": 5
 },
 "warnings by year": {
  "0": 3902,
  "1": 1671
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 30,
  "1": 25
 },
 "which (day, warner)": {
  "0": [
   9,
   "garrick"
  ],
  "1": [
   38,
   "sten"
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
  "0": 1008,
  "1": 1246
 },
 "per villager": {
  "0": 33.6,
  "1": 36.6
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.04,
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
  "0": 4,
  "1": 1
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
