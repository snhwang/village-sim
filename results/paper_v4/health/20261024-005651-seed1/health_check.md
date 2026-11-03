# Health check of 20261024-005651-seed1

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
  "0": 0
 },
 "empty days by year": {
  "0": 0
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.843
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 6
 },
 "which": {
  "0": [
   "ivo167",
   "fen122",
   "a story from the old days"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.297
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "tobin295",
   "learned-tobin295-warn-sickness",
   2
  ]
 },
 "villager-days over 12, by year": {
  "0": 0
 },
 "one-shot lessons written": 89
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 90,
 "recurs": {
  "each_day": 31,
  "each_time": 58,
  "always": 1
 },
 "lasts": {
  "life": 30,
  "news": 60
 },
 "answering no news": 16
}
```

## ok: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1
 },
 "which (day, warner, listener, topic)": {
  "0": [
   1,
   "rosa293",
   "orla201",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 0
 }
}
```

## ok: warnings that carried nothing

```
{
 "share by year": {
  "0": 0.005
 },
 "count by year": {
  "0": 80
 },
 "warnings by year": {
  "0": 16213
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 92
 },
 "which (day, warner)": {
  "0": [
   2,
   "katrin242"
  ]
 },
 "villager-days over 40, by year": {
  "0": 37
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 5191
 },
 "per villager": {
  "0": 17.2
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.042
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
  "0": 9
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 301
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
