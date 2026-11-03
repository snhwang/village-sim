# BEAR items on a village's memory

13,275 facts held by 174 villagers, from `knowledge_t34899.json.gz`, as items (experiments/items_check.py). BEAR from `/mnt/c/tmp/bear-pictures-main/bear/__init__.py at c992de4`.

- check: add then query, against a rebuild; queries: 60; identical: 60; differing: 0; largest similarity gap: 0.0; index_version equal: True
- check: remove 5% then query, against a rebuild; queries: 60; identical: 60; differing: 0; largest similarity gap: 0.0; index_version equal: True
- check: select_all on the owner, against the gate alone; queries: 60; same items in the same order: 60; differing: 0; largest score gap: 1.5e-07; ms per query, gate alone: 32.6; ms per query, selected: 3.3
- check: select_all=[hazard] with the owner gate, against the gate then filtered to hazards; queries: 60; same items in the same order: 60; differing: 0; fewer results: 0; largest score gap: 8.3e-08
- check: no cache directory: add against a rebuild; queries: 60; identical: 16; differing: 44; largest similarity gap: 0.001529; index_version equal: True

Timing (seconds): build 80% 8.1; each add (mean) 0.681; slices 40; rebuild 100% from a warm cache 0.73
