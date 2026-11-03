# Run-to-run spread of the paper's measures

Runs: 20261022-070414-seed1, 20261022-073709-seed2, 20261022-080916-seed3, 20261022-083715-seed4, 20261022-090533-seed5, 20261022-093732-seed6. The pooled analysis matched `results/knowledge_flow.json` before these were computed.

| measure | mean | SD | min | max |
|---|---|---|---|---|
| events that spread | 44.8 | 6.0 | 35 | 52 |
| median holders of an event | 28.4 | 2.3 | 24 | 30 |
| median wordings of an event | 19.9 | 1.7 | 17 | 22 |
| longest chain | 8.3 | 1.4 | 7 | 11 |
| offers already known (%) | 81.2 | 3.1 | 75.9 | 84 |
| new news refused (%) | 20.6 | 1.8 | 18.9 | 22.8 |
| facts reclassified (%) | 55.4 | 7.0 | 47.1 | 65.2 |
| reclassified toward trouble (%) | 84.8 | 5.2 | 80.1 | 93.4 |
| knowledge-only decisions (%) | 20.5 | 4.7 | 14.5 | 26.5 |

## Each run

| run | events that spread | median holders of an event | median wordings of an event | longest chain | offers already known (%) | new news refused (%) | facts reclassified (%) | reclassified toward trouble (%) | knowledge-only decisions (%) |
|---|---|---|---|---|---|---|---|---|---|
| 20261022-070414-seed1 | 46 | 29.5 | 20.5 | 8 | 84 | 19.1 | 58.1 | 93.4 | 22.2 |
| 20261022-073709-seed2 | 47 | 30 | 22 | 11 | 83.1 | 18.9 | 65.2 | 85.8 | 22.7 |
| 20261022-080916-seed3 | 41 | 28 | 19 | 8 | 75.9 | 22.1 | 47.1 | 80.1 | 15.3 |
| 20261022-083715-seed4 | 35 | 30 | 20 | 8 | 80.7 | 22 | 54.3 | 81.4 | 14.5 |
| 20261022-090533-seed5 | 48 | 24 | 17 | 7 | 80 | 18.9 | 47.9 | 80.4 | 21.8 |
| 20261022-093732-seed6 | 52 | 29 | 21 | 8 | 83.5 | 22.8 | 59.5 | 87.8 | 26.5 |

## Action counterfactual, Wilson 95% intervals (20261022-070414-seed1, 20261022-073709-seed2, 20261022-080916-seed3, 20261022-083715-seed4, 20261022-090533-seed5, 20261022-093732-seed6)

Decisions are clustered by villager, so these understate the uncertainty.

| swapped | changed | % | 95% interval |
|---|---|---|---|
| whole temperament | 196/2400 | 8.2 | 7.1--9.3 |
| sociability | 52/2400 | 2.2 | 1.7--2.8 |
| caution | 167/2400 | 7.0 | 6.0--8.0 |
| curiosity | 29/2400 | 1.2 | 0.8--1.7 |
| trust | 59/2400 | 2.5 | 1.9--3.2 |
| diligence | 187/2400 | 7.8 | 6.8--8.9 |
| candor | 33/2400 | 1.4 | 1.0--1.9 |

## Decisions that chose a restored candidate

0 of 172,064 villagers' decisions (0.0%) chose a candidate the threshold set aside and BEAR restored at priority alone. In 0 of them it ranked above an unrefused instruction that only knowledge makes available.

| instruction | times chosen |
|---|---|
