# Health check of 20261017-043036-seed1

Made by `experiments/health_check.py`. 2 of 12 checks flagged.

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
 "Replacing duplicate instruction": 7083
}
```

## ok: the granary empty for long

```
{
 "longest empty streak by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 2,
  "5": 9,
  "6": 4,
  "7": 0,
  "8": 9,
  "9": 1
 },
 "empty days by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 2,
  "5": 9,
  "6": 4,
  "7": 0,
  "8": 9,
  "9": 1
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.859,
  "1": 0.891,
  "2": 0.902,
  "3": 0.889,
  "4": 0.928,
  "5": 0.902,
  "6": 0.901,
  "7": 0.923,
  "8": 0.924,
  "9": 0.905
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 9,
  "1": 14,
  "2": 13,
  "3": 17,
  "4": 23,
  "5": 24,
  "6": 22,
  "7": 18,
  "8": 20,
  "9": 21
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
  ],
  "2": [
   "merrick",
   "inga",
   "a story from the old days"
  ],
  "3": [
   "merrick",
   "dagny",
   "a story from the old days"
  ],
  "4": [
   "merrick",
   "dagny",
   "a story from the old days"
  ],
  "5": [
   "wynn",
   "col",
   "a story from the old days"
  ],
  "6": [
   "sena",
   "lorne",
   "a story from the old days"
  ],
  "7": [
   "gorm",
   "liv",
   "a story from the old days"
  ],
  "8": [
   "wynn",
   "oda",
   "a story from the old days"
  ],
  "9": [
   "edek",
   "hedda",
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
  "1": 0.605,
  "2": 0.653,
  "3": 0.705,
  "4": 0.696,
  "5": 0.504,
  "6": 0.626,
  "7": 0.729,
  "8": 0.5,
  "9": 0.493
 }
}
```

## FLAG: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 21,
  "1": 29,
  "2": 6,
  "3": 18,
  "4": 14,
  "5": 31,
  "6": 129,
  "7": 73,
  "8": 21,
  "9": 56
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
  ],
  "2": [
   "nell",
   "learned-nell-blight-source",
   62
  ],
  "3": [
   "peder",
   "learned-peder-well-illness",
   104
  ],
  "4": [
   "maja",
   "learned-maja-2",
   115
  ],
  "5": [
   "jory",
   "learned-jory-1",
   142
  ],
  "6": [
   "nils",
   "learned-nils-1",
   184
  ],
  "7": [
   "ivar",
   "learned-ivar-well-poison-check",
   213
  ],
  "8": [
   "sten",
   "learned-sten-check-mill-grain",
   229
  ],
  "9": [
   "liv",
   "learned-liv-nighttime-warn",
   267
  ]
 },
 "villager-days over 12, by year": {
  "0": 2,
  "1": 1,
  "2": 0,
  "3": 4,
  "4": 3,
  "5": 9,
  "6": 15,
  "7": 14,
  "8": 13,
  "9": 32
 },
 "one-shot lessons written": 91
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1235,
  "1": 2045,
  "2": 2347,
  "3": 3438,
  "4": 3240,
  "5": 3609,
  "6": 4400,
  "7": 4675,
  "8": 4454,
  "9": 4574
 },
 "per villager": {
  "0": 41.2,
  "1": 58.4,
  "2": 60.2,
  "3": 83.9,
  "4": 73.6,
  "5": 78.5,
  "6": 83.0,
  "7": 88.2,
  "8": 79.5,
  "9": 83.2
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.046,
  "1": 0.054,
  "2": 0.045,
  "3": 0.064,
  "4": 0.065,
  "5": 0.034,
  "6": 0.056,
  "7": 0.07,
  "8": 0.044,
  "9": 0.031
 }
}
```

## FLAG: grown villagers stuck in one place and activity

```
{
 "still for 48+ waking ticks, by year": {
  "6": 1
 },
 "first cases": [
  {
   "who": "nils",
   "doing": "idle",
   "at": [
    17,
    15
   ],
   "from_tick": 26519
  }
 ]
}
```

## ok: years without a birth

```
{
 "births by year": {
  "0": 4,
  "1": 4,
  "2": 2,
  "3": 4,
  "4": 2,
  "5": 6,
  "6": 2,
  "7": 3,
  "9": 3
 },
 "longest run of years without": 1,
 "people at a year's start": {
  "0": 30,
  "1": 35,
  "2": 39,
  "3": 41,
  "4": 44,
  "5": 46,
  "6": 53,
  "7": 53,
  "8": 56,
  "9": 55
 }
}
```

## ok: deaths before old age

```
{
 "deaths": 2,
 "young": []
}
```
