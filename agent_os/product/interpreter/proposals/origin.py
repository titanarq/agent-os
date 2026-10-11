"""The status an item is born with, decided by code from its `origin` and never by the prompt
(`docs/adr/2026-10-11-an-items-origin-sets-its-status-and-the-owner-is-asked-only-about-what-is-derived.md`).

The owner's own words are approved as they are; what the interpreter only derives from them is asked
in the chat first; what Agentos detects against a criterion above the case (a goal, an evaluator) is
applied under the owner's standing pre-acceptance and commented. Review mode
(`sessions.confirm_before_dispatch`) overrides all of it: everything is born proposed.
"""

from __future__ import annotations

from agent_os.product.interpreter.constants import (
    KIND_CHANGE,
    KIND_DECISION,
    KIND_PUNTAL_CHANGE,
    KIND_VERDICT,
    ORIGIN_DETECTED,
    ORIGIN_STATED,
    STATUS_APPROVED,
    STATUS_PROPOSED,
)
from agent_os.product.interpreter.items import Item

# The kinds that carry a status: the work a `change` launches, the record a `verdict` writes, the
# issue a `puntal_change` opens and the what a `decision` states.
STATUS_KINDS = (KIND_CHANGE, KIND_DECISION, KIND_VERDICT, KIND_PUNTAL_CHANGE)


def status_born_of(item: Item, *, review_mode: bool) -> str:
    """`approved` for a stated or detected item, `proposed` for a derived one and, in review mode,
    for every one. An item with no origin (the model must give one) is proposed: when in doubt, the
    owner is asked."""
    is_the_owners_or_pre_accepted = item.origin in (ORIGIN_STATED, ORIGIN_DETECTED)
    return STATUS_APPROVED if is_the_owners_or_pre_accepted and not review_mode else STATUS_PROPOSED


def is_newly_detected(item: Item, carried: dict[str, Item]) -> bool:
    """A detected item this turn adds (or rewrites) that the reply must comment on."""
    previous = carried.get(item.id)
    return (
        item.origin == ORIGIN_DETECTED
        and not item.withdrawn
        and item.kind in STATUS_KINDS
        and (
            previous is None
            or previous.origin != ORIGIN_DETECTED
            or previous.summary != item.summary
        )
    )
