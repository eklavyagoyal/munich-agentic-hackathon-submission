"""COVERAGE: t = 0 for items the policy excludes. Uncovered items submit a=b=0.

Concept-based, not word-matching: an exclusion fires only when the policy
DECLARES the exclusion and the line item MATCHES that concept. Matching the
policy's own wording against the item description (as an earlier version did)
is meaningless -- invoices do not contain the word "excluded".

Scope: this catches explicit, stated exclusions only. Judging whether an item
is *related to the reported damage* is a reasoning task and belongs to the LLM
PRIOR/COVERAGE rule (build order step 4). This rule abstains there.
"""
from c2f.core.models import Context, Stage, Verdict
from c2f.rules.protocol import BaseRule

# (markers that must appear in the POLICY, keywords that must appear in the ITEM)
EXCLUSIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("wear and tear", "verschleiss", "verschleiß", "abnutzung"),
     ("wear", "abnutzung", "verschleiss", "verschleiß", "aufarbeitung")),
    (("cosmetic", "kosmetisch", "optische aufwertung"),
     ("cosmetic", "visual uniformity", "optisch", "verschönerung", "aufwertung")),
)


class PolicyExclusion(BaseRule):
    name = "policy_exclusion"
    stage = Stage.COVERAGE
    priority = 5
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        policy = ctx.policy_text.lower()
        desc = ctx.item.description.lower()
        for policy_markers, item_keywords in EXCLUSIONS:
            marker = next((m for m in policy_markers if m in policy), None)
            if marker is None:
                continue
            hit = next((k for k in item_keywords if k in desc), None)
            if hit is not None:
                return Verdict(covered=False,
                               note=f"policy excludes {marker!r}; item matches {hit!r}")
        return None        # abstain -- silence is the normal case


RULES = [PolicyExclusion()]
