# Counterfactual: swap the temperament, hold the situation

Runs `20261022-070414-seed1`, `20261022-073709-seed2`, `20261022-080916-seed3`, `20261022-083715-seed4`, `20261022-090533-seed5`, `20261022-093732-seed6`, 37 villagers, 2400 decisions replayed, donor random, 2026-10-22.

Each decision is replayed with the deciding villager's temperament replaced by another villager's, holding the situation, the knowledge and the query text fixed. A change is caused by the instructions and nothing else.

**Candor is the placebo.** Its two alleles carry only speech instructions and no action markers, so swapping it should change nothing; what it does change is the noise floor from altering the tag text the query is embedded with. Read the other loci against it.

| Swapped | Decisions changed |
|---|---|
| whole temperament | 196/2400 (8.2%) |
| sociability | 52/2400 (2.2%) |
| caution | 167/2400 (7.0%) |
| curiosity | 29/2400 (1.2%) |
| trust | 59/2400 (2.5%) |
| diligence | 187/2400 (7.8%) |
| candor | 33/2400 (1.4%) |

## Examples

- [at_forest_edge, time_afternoon] **Dunn** chose `temp-bold-roam`; with **Wynn**'s temperament it would have been `knows-avoid-sick-well`
- [at_forest_edge, time_morning] **Corin** chose `temp-bold-roam`; with **Wynn**'s temperament it would have been `weather-wait-out-rain`
- [at_home, at_home_13, near_adult] **Maja** chose `coming-pass-the-word`; with **Nell**'s temperament it would have been `temp-bold-roam`
- [at_market, near_adult, near_crowd] **Garrick** chose `temp-easygoing-break`; with **Fen**'s temperament it would have been `knows-avoid-sick-well`
- [near_adult, near_someone, time_morning] **Sten** chose `knows-warn-about-blight`; with **Garrick**'s temperament it would have been `knows-fight-blight`
