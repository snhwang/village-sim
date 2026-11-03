# BEAR items: fading and the audit, on a village's memory

13,275 facts from `knowledge_t34899.json.gz`, asked at tick 34899 (experiments/items_fading_audit.py). BEAR from `/mnt/c/tmp/bear-pictures-main/bear/__init__.py at 0842899`.

- check: knows_ tags from items above min_salience 0.5, against KnowledgeStore.tags(now, fade); villagers: 174; identical: 174; differing: 0; examples: []
- check: a faded fact asked for by its own words; facts: 40; found without a floor: 40; left out with the floor: 40
- check: 1,000 faded facts reinforced in one call, against a rebuild carrying the same reinforcement; updated: 1000; seconds for the call: 0.0404; queries: 40; identical: 40; back above the floor: 1000; index_version equal: True
- check: an audited session verified from its log alone; retrievals: 36; records: 54; log MB: 13.9; record kinds: {'baseline': 2, '?': 36, 'add': 10, 'reinforce': 6}; versions replayed: 18; match: 18; other: []
- check: the same log with one item's words altered in the first add record only; altered: record 6 (add), item f81445:kell; match: 2; differs: 16; skipped: 0; versions after the last baseline: 1; of those matching: 1
- check: the same log with one item's words altered in the first baseline record only; altered: record 0 (baseline), item f1:gorm; match: 1; differs: 17; skipped: 0; versions after the last baseline: 1; of those matching: 1
