# Health check of 20261017-043130-seed2

Made by `experiments/health_check.py`, read to day 56. 1 of 13 checks flagged.

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
  "outages": "not recorded",
  "seconds": "not recorded"
 },
 "embedder": {
  "outages": "not recorded",
  "seconds": "not recorded"
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
  "0": 0.846,
  "1": 0.885
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 13,
  "1": 13
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
  "0": 0.548,
  "1": 0.53
 }
}
```

## FLAG: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 2,
  "1": 59
 },
 "which (villager, lesson, day)": {
  "0": [
   "ilsa",
   "learned-ilsa-01",
   18
  ],
  "1": [
   "fen",
   "learned-fen-3",
   39
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 14
 },
 "one-shot lessons written": 15
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1311,
  "1": 1887
 },
 "per villager": {
  "0": 43.7,
  "1": 53.9
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.05,
  "1": 0.051
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
