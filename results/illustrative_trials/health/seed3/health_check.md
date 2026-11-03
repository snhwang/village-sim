# Health check of 20261017-043226-seed3

Made by `experiments/health_check.py`. 1 of 12 checks flagged.

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
 "Replacing duplicate instruction": 6294
}
```

## ok: the granary empty for long

```
{
 "longest empty streak by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 1,
  "4": 3,
  "5": 6,
  "6": 0,
  "7": 0,
  "8": 0,
  "9": 0
 },
 "empty days by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 1,
  "4": 3,
  "5": 6,
  "6": 0,
  "7": 0,
  "8": 0,
  "9": 0
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.811,
  "1": 0.901,
  "2": 0.927,
  "3": 0.908,
  "4": 0.9,
  "5": 0.9,
  "6": 0.899,
  "7": 0.887,
  "8": 0.918,
  "9": 0.877
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 11,
  "2": 9,
  "3": 17,
  "4": 16,
  "5": 16,
  "6": 19,
  "7": 20,
  "8": 23,
  "9": 21
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
  ],
  "2": [
   "osric",
   "ivar",
   "a story from the old days"
  ],
  "3": [
   "freya",
   "ivar",
   "a story from the old days"
  ],
  "4": [
   "hal",
   "runa",
   "a story from the old days"
  ],
  "5": [
   "hilde",
   "frida",
   "a story from the old days"
  ],
  "6": [
   "sena",
   "jory",
   "a story from the old days"
  ],
  "7": [
   "wynn",
   "maja",
   "a story from the old days"
  ],
  "8": [
   "edek",
   "per",
   "a story from the old days"
  ],
  "9": [
   "frida",
   "dag",
   "blight and frost observations"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.491,
  "1": 0.593,
  "2": 0.675,
  "3": 0.762,
  "4": 0.614,
  "5": 0.542,
  "6": 0.503,
  "7": 0.493,
  "8": 0.694,
  "9": 0.639
 }
}
```

## FLAG: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 24,
  "1": 20,
  "2": 39,
  "3": 27,
  "4": 14,
  "5": 119,
  "6": 16,
  "7": 21,
  "8": 16,
  "9": 21
 },
 "which (villager, lesson, day)": {
  "0": [
   "hilde28",
   "learned-hilde28-share-birth-news",
   13
  ],
  "1": [
   "hilde28",
   "learned-hilde28-share-birth-news",
   36
  ],
  "2": [
   "hilde28",
   "learned-hilde28-share-birth-news",
   63
  ],
  "3": [
   "hilde28",
   "learned-hilde28-report-fighting-nearby",
   108
  ],
  "4": [
   "ivar",
   "learned-ivar-storyteller-inn",
   123
  ],
  "5": [
   "nell",
   "learned-nell-warn-storyteller",
   144
  ],
  "6": [
   "frida",
   "learned-frida-002",
   191
  ],
  "7": [
   "hilde28",
   "learned-hilde28-report-fighting-nearby",
   201
  ],
  "8": [
   "ivar",
   "learned-ivar-storyteller-inn",
   226
  ],
  "9": [
   "per",
   "learned-per-1",
   273
  ]
 },
 "villager-days over 12, by year": {
  "0": 5,
  "1": 9,
  "2": 6,
  "3": 1,
  "4": 4,
  "5": 10,
  "6": 4,
  "7": 7,
  "8": 3,
  "9": 9
 },
 "one-shot lessons written": 51
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1226,
  "1": 1732,
  "2": 2166,
  "3": 2827,
  "4": 2977,
  "5": 2987,
  "6": 3402,
  "7": 3592,
  "8": 4094,
  "9": 4599
 },
 "per villager": {
  "0": 39.5,
  "1": 49.5,
  "2": 60.2,
  "3": 76.4,
  "4": 74.4,
  "5": 69.5,
  "6": 77.3,
  "7": 78.1,
  "8": 87.1,
  "9": 90.2
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.023,
  "1": 0.051,
  "2": 0.054,
  "3": 0.06,
  "4": 0.038,
  "5": 0.03,
  "6": 0.015,
  "7": 0.02,
  "8": 0.059,
  "9": 0.049
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
  "1": 2,
  "2": 1,
  "3": 3,
  "4": 3,
  "5": 2,
  "6": 1,
  "7": 5,
  "8": 4,
  "9": 2
 },
 "longest run of years without": 0,
 "people at a year's start": {
  "0": 31,
  "1": 35,
  "2": 36,
  "3": 37,
  "4": 40,
  "5": 43,
  "6": 44,
  "7": 46,
  "8": 47,
  "9": 51
 }
}
```

## ok: deaths before old age

```
{
 "deaths": 4,
 "young": []
}
```
