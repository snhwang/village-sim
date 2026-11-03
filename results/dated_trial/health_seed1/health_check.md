# Health check of 20261024-003205-seed1

Made by `experiments/health_check.py`. 0 of 18 checks flagged.

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
 "Replacing duplicate instruction": 6585
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
  "4": 3,
  "5": 6,
  "6": 3,
  "7": 3,
  "8": 9,
  "9": 4
 },
 "empty days by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 3,
  "5": 6,
  "6": 3,
  "7": 3,
  "8": 9,
  "9": 4
 }
}
```

## ok: news told to someone who had it

```
{
 "share of tellings by year": {
  "0": 0.802,
  "1": 0.851,
  "2": 0.857,
  "3": 0.873,
  "4": 0.862,
  "5": 0.867,
  "6": 0.864,
  "7": 0.885,
  "8": 0.893,
  "9": 0.906
 }
}
```

## ok: the same talk again and again

```
{
 "most repeated talk a year": {
  "0": 10,
  "1": 12,
  "2": 9,
  "3": 16,
  "4": 19,
  "5": 24,
  "6": 18,
  "7": 23,
  "8": 22,
  "9": 21
 },
 "which": {
  "0": [
   "bryn",
   "freya",
   "a question about the village"
  ],
  "1": [
   "merrick",
   "nell",
   "a story from the old days"
  ],
  "2": [
   "wynn",
   "ada",
   "news of the day"
  ],
  "3": [
   "sena",
   "jory",
   "a story from the old days"
  ],
  "4": [
   "gorm",
   "jory",
   "a story from the old days"
  ],
  "5": [
   "gorm",
   "nils",
   "a story from the old days"
  ],
  "6": [
   "freya",
   "per",
   "a story from the old days"
  ],
  "7": [
   "gorm",
   "aldo",
   "a story from the old days"
  ],
  "8": [
   "wynn",
   "dag",
   "a story from the old days"
  ],
  "9": [
   "osric",
   "cilla",
   "a story from the old days"
  ]
 }
}
```

## ok: decisions with a refused action

```
{
 "share by year": {
  "0": 0.552,
  "1": 0.637,
  "2": 0.741,
  "3": 0.704,
  "4": 0.671,
  "5": 0.685,
  "6": 0.519,
  "7": 0.5,
  "8": 0.673,
  "9": 0.634
 }
}
```

## ok: a one-shot lesson acted on again and again in a day

```
{
 "most times in a day, by year": {
  "0": 1,
  "1": 1,
  "2": 1,
  "3": 1,
  "4": 1,
  "5": 1,
  "6": 1,
  "7": 2,
  "8": 2,
  "9": 1
 },
 "which (villager, lesson, day)": {
  "0": [
   "hilde28",
   "learned-hilde28-mill-grain-spoilage",
   3
  ],
  "1": [
   "corin",
   "learned-corin-verify-blight",
   35
  ],
  "2": [
   "hilde28",
   "learned-hilde28-newborn-news",
   56
  ],
  "3": [
   "hilde28",
   "learned-hilde28-forest-danger-proximity",
   85
  ],
  "4": [
   "hilde28",
   "learned-hilde28-distant-sickness-travel",
   112
  ],
  "5": [
   "nell",
   "learned-nell-avoid-contaminated-well",
   141
  ],
  "6": [
   "wynn",
   "learned-wynn-raid-response",
   168
  ],
  "7": [
   "bryn",
   "learned-bryn-guard-livestock-wolves",
   215
  ],
  "8": [
   "frida",
   "learned-frida-weather-crisis-response",
   237
  ],
  "9": [
   "frida",
   "learned-frida-food-scarcity-check",
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
 "one-shot lessons written": 158
}
```

## ok: what lessons declared as they were written

```
{
 "lessons": 164,
 "recurs": {
  "each_time": 128,
  "always": 6,
  "each_day": 30
 },
 "lasts": {
  "news": 147,
  "season": 14,
  "life": 3
 },
 "answering no news": 3
}
```

## ok: the same warning to the same listener again and again in a day

```
{
 "most times in a day, by year": {
  "0": 2,
  "1": 2,
  "2": 2,
  "3": 2,
  "4": 3,
  "5": 2,
  "6": 2,
  "7": 3,
  "8": 3,
  "9": 3
 },
 "which (day, warner, listener, topic)": {
  "0": [
   13,
   "thea",
   "sena",
   "danger abroad that could come this way"
  ],
  "1": [
   38,
   "maren",
   "sten",
   "the water at the well has turned"
  ],
  "2": [
   56,
   "bryn",
   "rosa",
   "danger abroad that could come this way"
  ],
  "3": [
   84,
   "frode",
   "orla",
   "raiders on the east road"
  ],
  "4": [
   136,
   "frida",
   "maren",
   "raiders on the east road"
  ],
  "5": [
   140,
   "edek",
   "maja",
   "the water at the well has turned"
  ],
  "6": [
   170,
   "per",
   "corin",
   "raiders on the east road"
  ],
  "7": [
   211,
   "thea",
   "per",
   "danger abroad that could come this way"
  ],
  "8": [
   243,
   "jorun",
   "dag",
   "the blight in the fields"
  ],
  "9": [
   256,
   "lorne",
   "corin",
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
  "7": 0,
  "8": 0,
  "9": 0
 }
}
```

## ok: warnings that carried nothing

```
{
 "share by year": {
  "0": 0.003,
  "1": 0.003,
  "2": 0.004,
  "3": 0.003,
  "4": 0.004,
  "5": 0.002,
  "6": 0.003,
  "7": 0.003,
  "8": 0.002,
  "9": 0.003
 },
 "count by year": {
  "0": 7,
  "1": 8,
  "2": 16,
  "3": 11,
  "4": 14,
  "5": 10,
  "6": 9,
  "7": 12,
  "8": 15,
  "9": 16
 },
 "warnings by year": {
  "0": 2065,
  "1": 2383,
  "2": 4306,
  "3": 3914,
  "4": 3977,
  "5": 4820,
  "6": 2685,
  "7": 3921,
  "8": 6169,
  "9": 5785
 }
}
```

## ok: warnings by one villager in a day

```
{
 "most in a day, by year": {
  "0": 24,
  "1": 38,
  "2": 38,
  "3": 45,
  "4": 46,
  "5": 32,
  "6": 32,
  "7": 43,
  "8": 43,
  "9": 62
 },
 "which (day, warner)": {
  "0": [
   21,
   "dunn"
  ],
  "1": [
   52,
   "katrin"
  ],
  "2": [
   63,
   "wynn"
  ],
  "3": [
   100,
   "dunn"
  ],
  "4": [
   134,
   "frida"
  ],
  "5": [
   165,
   "maja"
  ],
  "6": [
   171,
   "lorne"
  ],
  "7": [
   216,
   "kell"
  ],
  "8": [
   251,
   "edek"
  ],
  "9": [
   252,
   "bryn"
  ]
 },
 "villager-days over 40, by year": {
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 1,
  "4": 1,
  "5": 0,
  "6": 0,
  "7": 1,
  "8": 1,
  "9": 3
 }
}
```

## ok: the live memory index growing without end

```
{
 "live index at a year's last trim": {
  "0": 945,
  "1": 1406,
  "2": 1854,
  "3": 2159,
  "4": 2212,
  "5": 2489,
  "6": 2255,
  "7": 2377,
  "8": 2835,
  "9": 2570
 },
 "per villager": {
  "0": 31.5,
  "1": 41.4,
  "2": 50.1,
  "3": 52.7,
  "4": 51.4,
  "5": 56.6,
  "6": 45.1,
  "7": 45.7,
  "8": 53.5,
  "9": 47.6
 }
}
```

## ok: grown villagers standing idle

```
{
 "idle share of waking frames by year": {
  "0": 0.021,
  "1": 0.025,
  "2": 0.039,
  "3": 0.031,
  "4": 0.028,
  "5": 0.033,
  "6": 0.016,
  "7": 0.022,
  "8": 0.031,
  "9": 0.033
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
  "2": 4,
  "3": 3,
  "4": 1,
  "5": 6,
  "6": 3,
  "7": 2,
  "9": 4
 },
 "longest run of years without": 1,
 "people at a year's start": {
  "0": 30,
  "1": 34,
  "2": 37,
  "3": 41,
  "4": 43,
  "5": 44,
  "6": 50,
  "7": 52,
  "8": 53,
  "9": 54
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
