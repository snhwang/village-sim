# Health check of 20261017-043036-seed1

Made by `experiments/health_check.py`, read to day 56. 1 of 11 checks flagged.

## ok: model calls never answered

```
{
 "speech_errors": 0,
 "from": "record"
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
  "0": 0.859,
  "1": 0.891
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 9,
  "1": 14
 },
 "which": {
  "0": [
   "freya",
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
  "0": 0.555,
  "1": 0.605
 }
}
```

## FLAG: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 21,
  "1": 29
 },
 "which (villager, lesson, day)": {
  "0": [
   "ilsa",
   "learned-ilsa-sickness-warning",
   4
  ],
  "1": [
   "gisla",
   "learned-gisla-wolf-threat",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 2,
  "1": 1
 },
 "one-shot lessons written": 14
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1235,
  "1": 2045
 },
 "per villager": {
  "0": 41.2,
  "1": 58.4
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.046,
  "1": 0.054
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
  "1": 4
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
