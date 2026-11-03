# Counterfactual: swap the temperament, hold the situation

Run `20260927-190041-seed1`, 30 villagers, 400 decisions replayed, 2026-09-27.

Each decision is replayed with the deciding villager's temperament replaced by another villager's, holding the situation, the knowledge and the query text fixed. A change is caused by the instructions and nothing else.

**Candor is the placebo.** Its two alleles carry only speech instructions and no action markers, so swapping it should change nothing; what it does change is the noise floor from altering the tag text the query is embedded with. Read the other loci against it.

| Swapped | Decisions changed |
|---|---|
| whole temperament | 56/400 (14.0%) |
| sociability | 24/400 (6.0%) |
| caution | 38/400 (9.5%) |
| curiosity | 29/400 (7.2%) |
| trust | 27/400 (6.8%) |
| diligence | 26/400 (6.5%) |
| candor | 11/400 (2.8%) |

## Examples

- [at_fields, at_work, near_adult] **Mabel** chose `knows-warn-about-blight`; with **Ada**'s temperament it would have been `adult-evening-home`
- [at_shrine, time_afternoon] **Corin** chose `temp-bold-roam`; with **Ada**'s temperament it would have been `apprentice-midday`
- [at_inn, near_adult, near_crowd] **Dunn** chose `weather-wait-out-rain`; with **Ada**'s temperament it would have been `adult-evening-home`
- [at_forest_edge, time_afternoon] **Sena** chose `temp-bold-roam`; with **Ada**'s temperament it would have been `weather-wait-out-rain`
- [at_fields, near_adult, near_someone] **Hilde28** chose `knows-avoid-blighted-field`; with **Ada**'s temperament it would have been `knows-warn-about-blight`
