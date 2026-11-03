# Can experience become instructions?

`20260922-000553-seed1`, Bryn (child, None).

The growth milestone turns a character's most reinforced knowledge and its weakest moments into new instructions it then carries. This probes that step alone, before the milestone is built around it.

## What it was given

Facts it holds, and how often it was told them again:

- 11x — Rosa says she saw raiders on the east road.
- 11x — A blight is rotting the crops in the fields.
- 3x — A traveler came up the east road with news from beyond the village.
- 1x — A storm broke over the village and kept everyone indoors.

Situations where nothing in the corpus fitted well:

- It is night and dark, time to sleep. It is raining. Bryn is at the Wick & Kettle inn. Nearby: Katrin, a elder, Hilde28, a child, Peder, a apprentice, Freya, a elder. Knows: A traveler came up the east road with news from beyond the village.
- It is night and dark, time to sleep. It is raining. Bryn is at the Wick & Kettle inn. Nearby: Corin, a apprentice, Ilsa, a child, Tobin, a adult, Freya, a elder. Knows: A traveler came up the east road with news from beyond the village.
- It is midday. Bryn is at house 3. Nobody is nearby. Knows: A traveler came up the east road with news from beyond the village.
- It is night and dark, time to sleep. It is raining. Bryn is at house 3. Nearby: Ada, a adult, Osric (father), Rosa (mother). Knows: Rosa says she saw raiders on the east road. A blight is rotting the crops in the fields.
- It is night and dark, time to sleep. A storm is blowing. Bryn is at house 3. Nearby: Rosa (mother), Wynn, a adult, Ada, a adult. Knows: A storm broke over the village and kept everyone indoors. A traveler came up the east road with news from beyond the village.
- It is night and dark, time to sleep. Bryn is at house 3. Nearby: Hilde, a elder. Knows: A traveler came up the east road with news from beyond the village.

## What came back

**✓ `learned-bryn-1`**

> You know a traveler brought news from beyond the village. Seek out the storyteller at the inn to hear the details and spread the word. [!go(to=inn)] [!talk(target=storyteller)]

markers: `['go', 'talk']` · scope: `[]`

**✓ `learned-bryn-2`**

> You know a blight is rotting the crops in the fields. Do not enter the fields to work or wander, as the air is tainted. [!avoid(place=fields)]

markers: `['avoid']` · scope: `[]`

**✓ `learned-bryn-3`**

> You know a storm broke over the village. Stay indoors and rest until the weather passes; do not venture out. [!rest(ticks=8)]

markers: `['rest']` · scope: `[]`


**Verdict: usable**

