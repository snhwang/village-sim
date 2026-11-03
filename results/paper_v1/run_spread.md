# Run-to-run spread of the paper's measures

Runs: 20260927-190041-seed1, 20260927-191014-seed2, 20260927-192146-seed3, 20260927-193347-seed4, 20260927-194732-seed5, 20260927-195852-seed6. The pooled analysis matched `results/knowledge_flow.json` before these were computed.

| measure | mean | SD | min | max |
|---|---|---|---|---|
| events that spread | 6.0 | 2.4 | 3 | 9 |
| median holders of an event | 22.4 | 7.2 | 12 | 30 |
| median wordings of an event | 14.6 | 5.2 | 9 | 20 |
| longest chain | 5.3 | 1.6 | 3 | 8 |
| offers already known (%) | 87.7 | 3.7 | 82.4 | 92 |
| new news refused (%) | 12.5 | 10.6 | 1.3 | 25.9 |
| facts reclassified (%) | 53.3 | 9.3 | 41.3 | 65.2 |
| reclassified toward trouble (%) | 90.8 | 10.4 | 75 | 100 |
| knowledge-only decisions (%) | 16.7 | 6.2 | 10.6 | 24.7 |

## Each run

| run | events that spread | median holders of an event | median wordings of an event | longest chain | offers already known (%) | new news refused (%) | facts reclassified (%) | reclassified toward trouble (%) | knowledge-only decisions (%) |
|---|---|---|---|---|---|---|---|---|---|
| 20260927-190041-seed1 | 5 | 30 | 19 | 5 | 84.9 | 3.2 | 65.2 | 94.5 | 11.4 |
| 20260927-191014-seed2 | 3 | 30 | 20 | 5 | 92 | 1.3 | 60 | 98.1 | 20.3 |
| 20260927-192146-seed3 | 8 | 18.5 | 10 | 5 | 82.4 | 25.9 | 44.4 | 75 | 10.6 |
| 20260927-193347-seed4 | 7 | 25 | 19 | 6 | 90.8 | 22.2 | 51.7 | 80.5 | 24.7 |
| 20260927-194732-seed5 | 9 | 12 | 9 | 8 | 86.7 | 17.1 | 57.3 | 96.7 | 21.5 |
| 20260927-195852-seed6 | 4 | 19 | 10.5 | 3 | 89.2 | 5.2 | 41.3 | 100 | 11.5 |

## Action counterfactual, Wilson 95% intervals (run 20260927-190041-seed1)

Decisions are clustered by villager, so these understate the uncertainty.

| swapped | changed | % | 95% interval |
|---|---|---|---|
| whole temperament | 56/400 | 14.0 | 10.9--17.7 |
| sociability | 24/400 | 6.0 | 4.1--8.8 |
| caution | 38/400 | 9.5 | 7.0--12.8 |
| curiosity | 29/400 | 7.2 | 5.1--10.2 |
| trust | 27/400 | 6.8 | 4.7--9.6 |
| diligence | 26/400 | 6.5 | 4.5--9.4 |
| candor | 11/400 | 2.8 | 1.5--4.9 |

## Decisions that chose a restored candidate

2,415 of 20,947 villagers' decisions (11.5%) chose a candidate the threshold set aside and BEAR restored at priority alone. In 1,274 of them it ranked above an unrefused instruction that only knowledge makes available.

| instruction | times chosen |
|---|---|
| adult-evening-home | 768 |
| adult-morning-work | 655 |
| child-home-evening | 314 |
| adult-afternoon-work | 309 |
| apprentice-morning-work | 130 |
| apprentice-afternoon-work | 127 |
| temp-reserved-avoid-crowd | 33 |
| temp-diligent-back-to-work | 22 |
| temp-settled-routine | 15 |
| elder-afternoon-work | 15 |
