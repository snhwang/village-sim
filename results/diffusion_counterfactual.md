# Counterfactual: swap the lens, hold what was heard

Runs `20261022-070414-seed1`, `20261022-073709-seed2`, `20261022-080916-seed3`, `20261022-083715-seed4`, `20261022-090533-seed5`, `20261022-093732-seed6`, 51 villagers, 400 reframings replayed, Qwen3.8-27B at temperature 0, 2026-10-22.

Every reframing the simulation performed is replayed with the receiver's absorbing instructions rebuilt from another villager's temperament. The speaker, the sentence heard, what the receiver already knew, and its name, stage and role are held fixed, and the original is replayed under the same decoder settings, so the pair differs in its lens and nothing else.

**There are two floors, and a claim about a trait has to clear the higher one.**

The *decoder floor* is `same prompt`: the identical prompt, asked twice. vLLM batches continuously and is not bitwise deterministic even at temperature 0, so some flips are the model rather than the lens. It is low — around 1% — which is the good news.

The *inert-tag floor* is the loci that carry no lens of their own, pooled. Swapping one adds no filter, but it still changes the tag text the lens query is embedded with, which reorders the role instructions around it. At this sample size every locus clears the decoder floor, including those two, so the decoder floor cannot separate a trait that matters from a tag that merely jostles retrieval. The inert-tag floor can.

**sociability and diligence carry no absorbing instruction on either allele** and were expected to be inert controls. They are not, which is worth more than the result they were meant to support: changing any tag changes the text the lens query is embedded with, reordering the role instructions around it. The `lens moved` column is how often a swap actually handed the villager different instructions, and the last column restricts the flip rate to those pairs. A swap that retrieved the same lens cannot have caused anything.

| Swapped | Keep/discard flipped | vs decoder floor | vs inert-tag floor | Lens moved | Flipped when it moved |
|---|---|---|---|---|---|
| **same prompt (floor)** | 2/382 (0.5%) | — | — | 0/382 (0%) | — |
| whole temperament | 27/382 (7.1%) | **p=0.0000** | **p=0.0052** | 359/382 (94%) | 27/359 (7.5%) |
| *sociability (no lens of its own)* | 13/380 (3.4%) | **p=0.0033** | — | 0/380 (0%) | — |
| caution | 34/383 (8.9%) | **p=0.0000** | **p=0.0001** | 373/383 (97%) | 34/373 (9.1%) |
| curiosity | 15/380 (3.9%) | **p=0.0010** | p=0.382 | 372/380 (98%) | 15/372 (4.0%) |
| trust | 30/383 (7.8%) | **p=0.0000** | **p=0.0012** | 372/383 (97%) | 30/372 (8.1%) |
| *diligence (no lens of its own)* | 13/381 (3.4%) | **p=0.0034** | — | 0/381 (0%) | — |
| candor | 34/376 (9.0%) | **p=0.0000** | **p=0.0001** | 370/376 (98%) | 34/370 (9.2%) |

## Examples

- **Hal** discarded "Wystan claims he heard of fighting beyond the forest, which puts a shadow over the safety of the northern fields and the grain trade."; with another villager's temperament it would have been kept
- **Hal** kept "A blight is on the crop at the fields. What it touches rots."; with another villager's temperament it would have been discarded
- **Merrick** discarded "Elin, the child of Mabel and Edek, was born at house 13."; with another villager's temperament it would have been kept
- **Freya** discarded "Hal says Thea and his own child, Ivar, was born at house 10."; with another villager's temperament it would have been kept
- **Merrick** discarded "Rosa and Osric had a child named Col, who was born at house three."; with another villager's temperament it would have been kept

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
