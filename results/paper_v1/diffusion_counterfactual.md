# Counterfactual: swap the lens, hold what was heard

Runs `20260927-190041-seed1`, `20260927-191014-seed2`, `20260927-192146-seed3`, `20260927-193347-seed4`, `20260927-194732-seed5`, `20260927-195852-seed6`, 30 villagers, 400 reframings replayed, Qwen3.8-27B at temperature 0, 2026-09-27.

Every reframing the simulation performed is replayed with the receiver's absorbing instructions rebuilt from another villager's temperament. The speaker, the sentence heard, what the receiver already knew, and its name, stage and role are held fixed, and the original is replayed under the same decoder settings, so the pair differs in its lens and nothing else.

**There are two floors, and a claim about a trait has to clear the higher one.**

The *decoder floor* is `same prompt`: the identical prompt, asked twice. vLLM batches continuously and is not bitwise deterministic even at temperature 0, so some flips are the model rather than the lens. It is low — around 1% — which is the good news.

The *inert-tag floor* is the loci that carry no lens of their own, pooled. Swapping one adds no filter, but it still changes the tag text the lens query is embedded with, which reorders the role instructions around it. At this sample size every locus clears the decoder floor, including those two, so the decoder floor cannot separate a trait that matters from a tag that merely jostles retrieval. The inert-tag floor can.

**sociability and diligence carry no absorbing instruction on either allele** and were expected to be inert controls. They are not, which is worth more than the result they were meant to support: changing any tag changes the text the lens query is embedded with, reordering the role instructions around it. The `lens moved` column is how often a swap actually handed the villager different instructions, and the last column restricts the flip rate to those pairs. A swap that retrieved the same lens cannot have caused anything.

| Swapped | Keep/discard flipped | vs decoder floor | vs inert-tag floor | Lens moved | Flipped when it moved |
|---|---|---|---|---|---|
| **same prompt (floor)** | 9/360 (2.5%) | — | — | 0/360 (0%) | — |
| whole temperament | 12/354 (3.4%) | p=0.315 | p=0.113 | 333/354 (94%) | 11/333 (3.3%) |
| *sociability (no lens of its own)* | 7/356 (2.0%) | p=0.768 | — | 0/356 (0%) | — |
| caution | 13/346 (3.8%) | p=0.229 | p=0.065 | 344/346 (99%) | 13/344 (3.8%) |
| curiosity | 9/354 (2.5%) | p=0.580 | p=0.339 | 354/354 (100%) | 9/354 (2.5%) |
| trust | 16/341 (4.7%) | p=0.086 | **p=0.0126** | 341/341 (100%) | 16/341 (4.7%) |
| *diligence (no lens of its own)* | 7/359 (1.9%) | p=0.774 | — | 1/359 (0%) | 0/1 (0.0%) |
| candor | 17/353 (4.8%) | p=0.073 | **p=0.0092** | 353/353 (100%) | 17/353 (4.8%) |

## Examples

- **Gisla** kept "On the road here I heard that the miller at Ashby found a hoard of old coins in his wall."; with another villager's temperament it would have been discarded
- **Gisla** kept "On the road here I heard that the miller at Ashby found a hoard of old coins in his wall."; with another villager's temperament it would have been discarded
- **Gisla** kept "On the road here I heard that the miller at Ashby found a hoard of old coins in his wall."; with another villager's temperament it would have been discarded
- **Orla** kept "On the road here I heard that the miller at Ashby found a hoard of old coins in his wall."; with another villager's temperament it would have been discarded
- **Garrick** kept "A traveler came up the east road with news from beyond the village."; with another villager's temperament it would have been discarded

## Which alleles carry a lens at all

| Locus | Allele | Absorbing instruction |
|---|---|---|
| candor | embellishing | absorb-embellishing |
| candor | plainspoken | absorb-plainspoken |
| caution | bold | — |
| caution | wary | absorb-wary |
| curiosity | inquisitive | absorb-inquisitive |
| curiosity | settled | — |
| diligence | diligent | — |
| diligence | easygoing | — |
| sociability | gregarious | — |
| sociability | reserved | — |
| trust | suspicious | absorb-suspicious |
| trust | trusting | absorb-trusting |
