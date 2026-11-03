# Health check of 20261022-090533-seed5

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
  "0": 0.802,
  "1": 0.795
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 9,
  "1": 8
 },
 "which": {
  "0": [
   "bryn",
   "freya",
   "a question about the village"
  ],
  "1": [
   "gisla",
   "dunn",
   "how the day has gone"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.71,
  "1": 0.642
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
   "hilde28",
   "learned-hilde28-inn-gossip",
   21
  ],
  "1": [
   "peder",
   "learned-peder-verify-road-safety",
   29
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
  "each_time": 9,
  "each_day": 3
 },
 "lasts": {
  "season": 2,
  "news": 8,
  "life": 2
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
   13,
   "sena",
   "thea",
   "the blight in the fields"
  ],
  "1": [
   31,
   "lise",
   "ada",
   "the water at the well has turned"
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
  "0": 0.002,
  "1": 0.002
 },
 "count by year": {
  "0": 4,
  "1": 2
 },
 "warnings by year": {
  "0": 2427,
  "1": 1182
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 28,
  "1": 24
 },
 "which (day, warner)": {
  "0": [
   19,
   "per"
  ],
  "1": [
   35,
   "corin"
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
  "0": 980,
  "1": 1336
 },
 "per villager": {
  "0": 32.7,
  "1": 38.2
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.03,
  "1": 0.028
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
  "0": 5
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 30,
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
