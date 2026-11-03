# Health check of 20261021-003622-seed3

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
  "0": 0.828,
  "1": 0.915
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 11,
  "1": 12
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
  "0": 0.565,
  "1": 0.564
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 3,
  "1": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "ilsa",
   "learned-ilsa-traveler-news",
   6
  ],
  "1": [
   "gisla",
   "learned-gisla-check-village-gathering",
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
  "each_time": 14,
  "each_day": 4
 },
 "lasts": {
  "news": 16,
  "season": 2
 },
 "answering no news": 0
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 12,
  "1": 13
 },
 "which (day, warner, listener, topic)": {
  "0": [
   27,
   "corin",
   "peder",
   "danger abroad that could come this way"
  ],
  "1": [
   43,
   "bryn",
   "corin",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 41,
  "1": 225
 }
}
```

## FLAG: a villager warning again and again in a day

```
{
 "most warnings by one villager in a day, by year": {
  "0": 50,
  "1": 55
 },
 "which (day, warner)": {
  "0": [
   27,
   "edda"
  ],
  "1": [
   31,
   "wynn"
  ]
 },
 "villager-days over 40, by year": {
  "0": 3,
  "1": 4
 },
 "warnings that carried nothing, by year": {
  "0": 29,
  "1": 145
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1165,
  "1": 1629
 },
 "per villager": {
  "0": 37.6,
  "1": 46.5
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.027,
  "1": 0.047
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
