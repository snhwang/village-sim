# Health check of 20261023-012700-seed3

Made by `experiments/health_check.py`. 1 of 18 checks flagged.

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
 "Replacing duplicate instruction": 6223
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
  "5": 5,
  "6": 2,
  "7": 3,
  "8": 0,
  "9": 0
 },
 "empty days by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 2,
  "5": 5,
  "6": 2,
  "7": 3,
  "8": 0,
  "9": 0
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.753,
  "1": 0.844,
  "2": 0.838,
  "3": 0.861,
  "4": 0.865,
  "5": 0.838,
  "6": 0.848,
  "7": 0.867,
  "8": 0.878,
  "9": 0.865
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 11,
  "1": 12,
  "2": 20,
  "3": 20,
  "4": 13,
  "5": 7,
  "6": 21,
  "7": 18,
  "8": 19,
  "9": 23
 },
 "which": {
  "0": [
   "merrick",
   "nell",
   "a story from the old days"
  ],
  "1": [
   "bryn",
   "freya",
   "a question about the village"
  ],
  "2": [
   "osric",
   "ivar",
   "a story from the old days"
  ],
  "3": [
   "osric",
   "ivar",
   "a story from the old days"
  ],
  "4": [
   "katrin",
   "runa",
   "a story from the old days"
  ],
  "5": [
   "gisla",
   "garrick",
   "news of the day"
  ],
  "6": [
   "fen",
   "jory",
   "a story from the old days"
  ],
  "7": [
   "katrin",
   "jory",
   "a story from the old days"
  ],
  "8": [
   "edek",
   "col",
   "a story from the old days"
  ],
  "9": [
   "thea",
   "per",
   "a story from the old days"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.53,
  "1": 0.554,
  "2": 0.649,
  "3": 0.694,
  "4": 0.6,
  "5": 0.522,
  "6": 0.626,
  "7": 0.552,
  "8": 0.64,
  "9": 0.585
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1,
  "1": 1,
  "2": 2,
  "3": 2,
  "4": 1,
  "5": 1,
  "6": 1,
  "7": 1,
  "8": 2,
  "9": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "hilde28",
   "learned-hilde28-share-frode-birth",
   3
  ],
  "1": [
   "peder",
   "learned-peder-check-mill-grain",
   29
  ],
  "2": [
   "osric",
   "learned-osric-assess-road-danger",
   57
  ],
  "3": [
   "osric",
   "learned-osric-assess-road-danger",
   90
  ],
  "4": [
   "corin",
   "learned-corin-well-sickness",
   112
  ],
  "5": [
   "ilsa",
   "learned-ilsa-3",
   141
  ],
  "6": [
   "ilsa",
   "learned-ilsa-3",
   168
  ],
  "7": [
   "rosa",
   "learned-rosa-3",
   196
  ],
  "8": [
   "osric",
   "learned-osric-assess-road-danger",
   225
  ],
  "9": [
   "rosa",
   "learned-rosa-3",
   252
  ]
 },
 "villager-days over 12, by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0,
  "6": 0,
  "7": 0,
  "8": 0,
  "9": 0
 },
 "one-shot lessons written": 127
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 132,
 "recurs": {
  "each_time": 98,
  "each_day": 29,
  "always": 5
 },
 "lasts": {
  "life": 7,
  "news": 109,
  "season": 16
 },
 "answering no news": 6
}
```

## FLAG: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1,
  "1": 2,
  "2": 3,
  "3": 2,
  "4": 2,
  "5": 3,
  "6": 2,
  "7": 4,
  "8": 3,
  "9": 3
 },
 "which (day, warner, listener, topic)": {
  "0": [
   9,
   "hilde",
   "dunn",
   "the water at the well has turned"
  ],
  "1": [
   41,
   "thea",
   "katrin",
   "the blight in the fields"
  ],
  "2": [
   77,
   "freya",
   "ada",
   "the water at the well has turned"
  ],
  "3": [
   89,
   "elin",
   "orla",
   "danger abroad that could come this way"
  ],
  "4": [
   116,
   "maren",
   "sten",
   "danger abroad that could come this way"
  ],
  "5": [
   167,
   "maja",
   "gorm",
   "raiders on the east road"
  ],
  "6": [
   168,
   "lorne",
   "corin",
   "raiders on the east road"
  ],
  "7": [
   202,
   "frida",
   "ilsa",
   "danger abroad that could come this way"
  ],
  "8": [
   244,
   "per",
   "gorm",
   "danger abroad that could come this way"
  ],
  "9": [
   267,
   "col",
   "gisla",
   "danger abroad that could come this way"
  ]
 },
 "listener-days over 3, by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0,
  "6": 0,
  "7": 2,
  "8": 0,
  "9": 0
 }
}
```

## ok: warnings that carried nothing

```
{
 "share by year": {
  "0": 0.004,
  "1": 0.001,
  "2": 0.003,
  "3": 0.002,
  "4": 0.003,
  "5": 0.0,
  "6": 0.003,
  "7": 0.004,
  "8": 0.005,
  "9": 0.005
 },
 "count by year": {
  "0": 6,
  "1": 1,
  "2": 10,
  "3": 8,
  "4": 8,
  "5": 0,
  "6": 9,
  "7": 10,
  "8": 24,
  "9": 16
 },
 "warnings by year": {
  "0": 1415,
  "1": 1951,
  "2": 3466,
  "3": 3408,
  "4": 2565,
  "5": 1393,
  "6": 3454,
  "7": 2547,
  "8": 4420,
  "9": 3329
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 20,
  "1": 38,
  "2": 41,
  "3": 34,
  "4": 26,
  "5": 21,
  "6": 32,
  "7": 31,
  "8": 42,
  "9": 40
 },
 "which (day, warner)": {
  "0": [
   10,
   "corin"
  ],
  "1": [
   47,
   "rosa"
  ],
  "2": [
   79,
   "dunn"
  ],
  "3": [
   101,
   "wynn"
  ],
  "4": [
   132,
   "lorne"
  ],
  "5": [
   153,
   "aldo"
  ],
  "6": [
   168,
   "dag"
  ],
  "7": [
   205,
   "kell"
  ],
  "8": [
   241,
   "gisla"
  ],
  "9": [
   272,
   "per"
  ]
 },
 "villager-days over 40, by year": {
  "0": 0,
  "1": 0,
  "2": 1,
  "3": 0,
  "4": 0,
  "5": 0,
  "6": 0,
  "7": 0,
  "8": 1,
  "9": 0
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 993,
  "1": 1275,
  "2": 1851,
  "3": 2074,
  "4": 1881,
  "5": 1928,
  "6": 2540,
  "7": 2233,
  "8": 2217,
  "9": 2216
 },
 "per villager": {
  "0": 32.0,
  "1": 36.4,
  "2": 52.9,
  "3": 57.6,
  "4": 45.9,
  "5": 45.9,
  "6": 60.5,
  "7": 50.8,
  "8": 54.1,
  "9": 51.5
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.017,
  "1": 0.022,
  "2": 0.031,
  "3": 0.031,
  "4": 0.021,
  "5": 0.011,
  "6": 0.023,
  "7": 0.018,
  "8": 0.032,
  "9": 0.022
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
  "0": 5,
  "3": 6,
  "4": 1,
  "5": 1,
  "6": 1,
  "7": 1,
  "8": 1,
  "9": 4
 },
 "longest run of years without": 2,
 "people at a year's start": {
  "0": 31,
  "1": 35,
  "2": 35,
  "3": 36,
  "4": 41,
  "5": 42,
  "6": 42,
  "7": 44,
  "8": 41,
  "9": 43
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
