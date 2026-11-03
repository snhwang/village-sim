# Health check of 20261022-073709-seed2

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
  "0": 0.826,
  "1": 0.84
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
   "freya",
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
  "0": 0.691,
  "1": 0.61
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
   "learned-ilsa-wolf-road",
   3
  ],
  "1": [
   "orla",
   "learned-orla-wolf-sightings",
   33
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
  "each_time": 17,
  "each_day": 1
 },
 "lasts": {
  "news": 18
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
   16,
   "wynn",
   "rosa",
   "the water at the well has turned"
  ],
  "1": [
   28,
   "ilsa",
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
  "0": 0.002,
  "1": 0.002
 },
 "count by year": {
  "0": 7,
  "1": 3
 },
 "warnings by year": {
  "0": 2808,
  "1": 1550
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 32,
  "1": 27
 },
 "which (day, warner)": {
  "0": [
   16,
   "wynn"
  ],
  "1": [
   37,
   "nell"
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
  "0": 934,
  "1": 1144
 },
 "per villager": {
  "0": 31.1,
  "1": 33.6
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.029,
  "1": 0.033
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
  "0": 4
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
