# Health check of 20261018-014501-seed1

Made by `experiments/health_check.py`. 0 of 13 checks flagged.

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
 "Replacing duplicate instruction": 1092
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
  "0": 0.88,
  "1": 0.885
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 11
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
  "0": 0.617,
  "1": 0.62
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
   "learned-ilsa-1",
   13
  ],
  "1": [
   "gisla",
   "learned-gisla-1",
   29
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0
 },
 "one-shot lessons written": 21
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 21,
 "recurs": {
  "each_day": 4,
  "each_time": 17
 },
 "lasts": {
  "life": 2,
  "news": 18,
  "season": 1
 },
 "answering no news": 2
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1191,
  "1": 1840
 },
 "per villager": {
  "0": 39.7,
  "1": 55.8
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.055,
  "1": 0.044
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
  "1": 3
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
