"""Is the corpus doing situational work, or is it a lookup table?

An instruction that fires for everyone in every context is a constant wearing
BEAR's clothes, and a corpus where similarity never changes the outcome is a
priority-ordered lookup. Both are easy to build by accident, so every run
reports them.

Read the numbers this way:

* ``similarity_decided`` — decisions where ranking by score picked a different
  instruction than ranking by priority alone. Near zero means the query is not
  doing anything and the gates are deciding everything.
* ``always_fires`` — instructions retrieved in nearly every decision where the
  character could use them. Candidates for demotion to code.
* ``never_fires`` — instructions that were never chosen. Dead, mis-gated, or
  outcompeted.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


class UsageReport:
    def __init__(self) -> None:
        self.decisions = 0
        self.chosen = Counter()
        self.offered = Counter()
        self.retrieved = Counter()
        self.similarity_decided = 0
        self.sampling_moved = 0
        self.by_character = defaultdict(Counter)
        self.contexts = defaultdict(Counter)

    def record(self, decision: dict) -> None:
        self.decisions += 1
        chosen = decision.get("chosen")
        if chosen:
            self.chosen[chosen] += 1
            self.by_character[decision["character"]][chosen] += 1
            for tag in decision.get("tags", []):
                self.contexts[chosen][tag] += 1
        for item in decision.get("retrieved", []):
            self.retrieved[item["id"]] += 1
            if item.get("actionable"):
                self.offered[item["id"]] += 1
        if decision.get("by_score") and decision["by_score"] != decision.get("by_priority"):
            self.similarity_decided += 1
        if chosen and decision.get("by_score") and chosen != decision["by_score"]:
            self.sampling_moved += 1

    def summary(self, actionable_ids: list[str]) -> dict:
        """``actionable_ids`` are the instructions that carry action markers.

        Speech-only instructions are never "chosen" — they shape what a
        character says — so counting them as dead would be misleading.
        """
        n = max(self.decisions, 1)
        dead_weight = [i for i in actionable_ids
                       if self.chosen.get(i, 0) == 0 and self.offered.get(i, 0) >= n * 0.9]
        return {
            "decisions": self.decisions,
            "similarity_decided": self.similarity_decided,
            "similarity_decided_pct": round(100 * self.similarity_decided / n, 1),
            "sampling_moved_pct": round(100 * self.sampling_moved / n, 1),
            "actionable_instructions": len(actionable_ids),
            "instructions_chosen": len(self.chosen),
            "never_chosen": sorted(set(actionable_ids) - set(self.chosen)),
            "always_offered_never_chosen": sorted(dead_weight),
            "chosen_counts": dict(self.chosen.most_common()),
            "per_character": {c: dict(counts.most_common(5))
                              for c, counts in sorted(self.by_character.items())},
        }

    def write(self, path: Path, actionable_ids: list[str]) -> dict:
        summary = self.summary(actionable_ids)
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    @staticmethod
    def describe(summary: dict) -> str:
        return (f"{summary['decisions']} decisions | "
                f"similarity decided {summary['similarity_decided_pct']}% | "
                f"{summary['instructions_chosen']}/{summary['actionable_instructions']} "
                f"actionable instructions used | "
                f"{len(summary['never_chosen'])} never chosen")
