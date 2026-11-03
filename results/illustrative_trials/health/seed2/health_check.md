# Health check of 20261017-043130-seed2

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
 "Replacing duplicate instruction": 6488
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
  "4": 1,
  "5": 4,
  "6": 3,
  "7": 3,
  "8": 4,
  "9": 9
 },
 "empty days by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 1,
  "5": 4,
  "6": 3,
  "7": 3,
  "8": 4,
  "9": 9
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.846,
  "1": 0.885,
  "2": 0.901,
  "3": 0.907,
  "4": 0.896,
  "5": 0.898,
  "6": 0.904,
  "7": 0.904,
  "8": 0.913,
  "9": 0.885
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 13,
  "1": 13,
  "2": 8,
  "3": 18,
  "4": 15,
  "5": 22,
  "6": 17,
  "7": 20,
  "8": 19,
  "9": 19
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
   "mads",
   "a story from the old days"
  ],
  "3": [
   "rosa",
   "nils",
   "a story from the old days"
  ],
  "4": [
   "osric",
   "nils",
   "a story from the old days"
  ],
  "5": [
   "osric",
   "dag",
   "a story from the old days"
  ],
  "6": [
   "sena",
   "brit",
   "a story from the old days"
  ],
  "7": [
   "ivar",
   "orla",
   "Ilsa and Peder's marriage"
  ],
  "8": [
   "osric",
   "runa",
   "a story from the old days"
  ],
  "9": [
   "nell",
   "hal",
   "current village needs and safety"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.548,
  "1": 0.53,
  "2": 0.635,
  "3": 0.557,
  "4": 0.532,
  "5": 0.525,
  "6": 0.63,
  "7": 0.57,
  "8": 0.584,
  "9": 0.513
 }
}
```

## FLAG: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 2,
  "1": 59,
  "2": 67,
  "3": 52,
  "4": 67,
  "5": 56,
  "6": 62,
  "7": 53,
  "8": 56,
  "9": 61
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
  ],
  "2": [
   "fen",
   "learned-fen-3",
   58
  ],
  "3": [
   "fen",
   "learned-fen-3",
   87
  ],
  "4": [
   "fen",
   "learned-fen-3",
   132
  ],
  "5": [
   "fen",
   "learned-fen-3",
   157
  ],
  "6": [
   "fen",
   "learned-fen-3",
   170
  ],
  "7": [
   "fen",
   "learned-fen-3",
   219
  ],
  "8": [
   "fen",
   "learned-fen-3",
   241
  ],
  "9": [
   "ivar",
   "learned-ivar-003",
   270
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 14,
  "2": 11,
  "3": 25,
  "4": 14,
  "5": 23,
  "6": 35,
  "7": 46,
  "8": 27,
  "9": 32
 },
 "one-shot lessons written": 83
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 1311,
  "1": 1887,
  "2": 2376,
  "3": 2881,
  "4": 3092,
  "5": 3204,
  "6": 3689,
  "7": 3905,
  "8": 3851,
  "9": 3915
 },
 "per villager": {
  "0": 43.7,
  "1": 53.9,
  "2": 64.2,
  "3": 73.9,
  "4": 75.4,
  "5": 74.5,
  "6": 82.0,
  "7": 86.8,
  "8": 83.7,
  "9": 79.9
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.05,
  "1": 0.051,
  "2": 0.046,
  "3": 0.04,
  "4": 0.034,
  "5": 0.04,
  "6": 0.056,
  "7": 0.048,
  "8": 0.042,
  "9": 0.03
 }
}
```

## FLAG: grown villagers stuck in one place and activity

```
{
 "still for 48+ waking ticks, by year": {
  "9": 2
 },
 "first cases": [
  {
   "who": "garrick",
   "doing": "follow",
   "at": [
    19,
    11
   ],
   "from_tick": 37194
  },
  {
   "who": "garrick",
   "doing": "follow",
   "at": [
    21,
    10
   ],
   "from_tick": 40062
  }
 ]
}
```

## ok: years without a birth

```
{
 "births by year": {
  "0": 4,
  "1": 3,
  "2": 2,
  "3": 1,
  "4": 2,
  "5": 3,
  "7": 1,
  "8": 3,
  "9": 1
 },
 "longest run of years without": 1,
 "people at a year's start": {
  "0": 30,
  "1": 35,
  "2": 37,
  "3": 39,
  "4": 41,
  "5": 43,
  "6": 45,
  "7": 45,
  "8": 46,
  "9": 49
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
