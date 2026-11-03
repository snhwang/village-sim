# Health check of 20261017-213553-seed1

Made by `experiments/health_check.py`. 0 of 12 checks flagged.

## ok: model calls never answered

```
{
 "speech_errors": 0,
 "from": "record"
}
```

## ok: errors in the console log

```
{
 "Replacing duplicate instruction": 1091
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
  "0": 0.876,
  "1": 0.877
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 8
 },
 "which": {
  "0": [
   "merrick",
   "nell",
   "a story from the old days"
  ],
  "1": [
   "fen",
   "katrin",
   "news of the day"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.597,
  "1": 0.525
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
   "learned-hilde28-1",
   3
  ],
  "1": [
   "peder",
   "learned-peder-grain-storehouse-safety",
   36
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 13
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1278,
  "1": 1439
 },
 "per villager": {
  "0": 42.6,
  "1": 45.0
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.059,
  "1": 0.025
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
  "0": 2,
  "1": 2
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 30,
  "1": 32
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
