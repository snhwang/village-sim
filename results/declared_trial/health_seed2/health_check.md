# Health check of 20261018-061550-seed2

Made by `experiments/health_check.py`. 0 of 15 checks flagged.

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
 "Replacing duplicate instruction": 1251
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
  "0": 0.871,
  "1": 0.871
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 9,
  "1": 11
 },
 "which": {
  "0": [
   "bryn",
   "osric",
   "a question about the village"
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
  "0": 0.618,
  "1": 0.557
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
   "learned-hilde28-fight-warning",
   11
  ],
  "1": [
   "gisla",
   "learned-gisla-avoid-sick-well",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 24
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 24,
 "recurs": {
  "each_time": 23,
  "each_day": 1
 },
 "lasts": {
  "news": 23,
  "season": 1
 },
 "answering no news": 0
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1261,
  "1": 1818
 },
 "per villager": {
  "0": 42.0,
  "1": 53.5
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.062,
  "1": 0.05
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
