# Marker signatures in consolidation

30 consolidations of run `20261003-093714-seed1`, replayed with the paper profile's 18 markers, by Qwen3.8-27B, on 2026-10-09.

| Shown as | Accepted | Refused | Failed calls |
|---|---|---|---|
| bare names | 22 | 56 | 0 |
| signatures | 78 | 0 | 0 |

Why bare names were refused:

- 18 x [!avoid] was given ['site'], which it does not read (it reads ['place', 'ticks'])
- 11 x [!warn] has no target, so it cannot act
- 4 x [!avoid] was given ['target'], which it does not read (it reads ['place', 'ticks'])
- 3 x [!warn] names 'neighbors', who is not anyone in this village
- 3 x [!rest] was given ['site'], which it does not read (it reads ['ticks', 'until'])
- 3 x [!avoid] has no place, so it cannot act
- 2 x [!warn] names 'village', who is not anyone in this village
- 2 x [!go] was given ['site'], which it does not read (it reads ['to'])
