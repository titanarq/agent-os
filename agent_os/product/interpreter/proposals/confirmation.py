"""What `sessions.confirm_before_dispatch` adds to the interpreter, decided by code and never by the
prompt: a new `change` leaves `proposed`, `approved` is bound to what the owner was shown, a node
must be one the brief listed, and the reply must be the proposal. See
`docs/adr/2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md`."""

from __future__ import annotations

import dataclasses
import pathlib

from agent_os.product.interpreter.constants import (
    KIND_CHANGE,
    KIND_PUNTAL_CHANGE,
    KIND_VERDICT,
    MAX_LISTED_USE_CASES,
    MAX_REPLY_CHARS,
    PROPOSAL_REPLY_CHARS_PER_ITEM,
    QUESTION_MARKS,
    STATUS_APPROVED,
    STATUS_PROPOSED,
    InterpreterRefused,
)
from agent_os.product.interpreter.items import Item
from agent_os.product.interpreter.request import CaseContext, Request

# The kinds that wait for the owner's yes: the work a `change` launches, the record a `verdict`
# writes and the issue a `puntal_change` opens.
PROPOSABLE_KINDS = (KIND_CHANGE, KIND_VERDICT, KIND_PUNTAL_CHANGE)


@dataclasses.dataclass(frozen=True)
class Confirmation:
    """The nodes the owner may be told an item is about: the case first, then the tree's use cases
    (id, title), cut at `MAX_LISTED_USE_CASES`."""

    listed: tuple[tuple[str, str], ...]
    omitted: int = 0

    def title_of(self, node_id: str) -> str | None:
        return dict(self.listed).get(node_id)


def confirmation_from_tree(case: CaseContext | None, tree_root: pathlib.Path) -> Confirmation:
    """Fails loudly when the tree cannot be read: an item tied to a node nobody can check is what
    this mode exists to prevent."""
    from agent_os.product.tree.loader import TreeRootError, load_tree, require_tree_root

    try:
        tree = load_tree(require_tree_root(tree_root))
    except TreeRootError as error:
        raise InterpreterRefused(
            f"sessions.confirm_before_dispatch needs the tree to list the use cases: {error}"
        ) from error
    use_cases = sorted(
        (node.id, node.title) for node in tree.nodes.values() if node.type == "use-case"
    )
    listed = [(case.id, case.title)] if case else []
    listed += [entry for entry in use_cases if not case or entry[0] != case.id]
    return Confirmation(
        tuple(listed[:MAX_LISTED_USE_CASES]), max(0, len(listed) - MAX_LISTED_USE_CASES)
    )


def _same_proposal(item: Item, previous: Item) -> bool:
    return (item.kind, item.summary, item.node, item.page, item.verdict, item.invocations) == (
        previous.kind,
        previous.summary,
        previous.node,
        previous.page,
        previous.verdict,
        previous.invocations,
    )


def _bound_status(item: Item, previous: Item | None) -> tuple[str | None, str | None]:
    """`(status, retry reason)` for one item the model returned."""
    if item.withdrawn:
        return (previous.status if previous else None), None
    if item.kind not in PROPOSABLE_KINDS:
        reason = (
            "`approved` is only for a `change`, `verdict` or `puntal_change` item"
            if item.status == STATUS_APPROVED
            else None
        )
        return None, reason
    unchanged = previous is not None and _same_proposal(item, previous)
    if unchanged and previous.status == STATUS_APPROVED:
        return STATUS_APPROVED, None
    if item.status != STATUS_APPROVED:
        return STATUS_PROPOSED, None
    if previous is None:
        return (
            STATUS_PROPOSED,
            "`approved` on an item that is new in this turn: a new item is `proposed`",
        )
    if not unchanged:
        return STATUS_PROPOSED, (
            "`approved` on an item whose kind, summary, node, page, verdict or invocation changed: "
            "a correction is `proposed` again"
        )
    return STATUS_APPROVED, None


def bind_items(
    items: list[Item], request: Request, confirmation: Confirmation
) -> tuple[list[Item], list[str]]:
    """The returned items with their status set by code, and every reason to retry."""
    carried = {item.id: item for item in request.items}
    allowed_nodes = {node_id for node_id, _ in confirmation.listed} | {
        item.node for item in request.items if item.node
    }
    bound, problems = [], []
    for item in items:
        status, reason = _bound_status(item, carried.get(item.id))
        if reason:
            problems.append(f"{item.id}: {reason}")
        if item.node and not item.withdrawn and item.node not in allowed_nodes:
            problems.append(
                f"{item.id}: `node` {item.node!r} is not the case nor a use case listed in the brief"
            )
        bound.append(dataclasses.replace(item, status=status))
    return bound, problems


def bind_items_without_confirmation(
    items: list[Item], request: Request
) -> tuple[list[Item], list[str]]:
    """The key is off: a new `verdict` is born `approved` and a `change` is left as the model wrote
    it, but a `puntal_change` is bound as ever, because it reaches Agentos's own method and the key
    never meant to loosen that."""
    carried = {item.id: item for item in request.items}
    bound, problems = [], []
    for item in items:
        if item.kind == KIND_PUNTAL_CHANGE:
            status, reason = _bound_status(item, carried.get(item.id))
            if reason:
                problems.append(f"{item.id}: {reason}")
            item = dataclasses.replace(item, status=status)
        elif item.kind == KIND_VERDICT and not item.withdrawn:
            item = dataclasses.replace(item, status=STATUS_APPROVED)
        bound.append(item)
    return bound, problems


def proposed_after_this_turn(items: list[Item], request: Request) -> list[Item]:
    standing = {item.id: item for item in request.items}
    standing.update({item.id: item for item in items})
    return [
        item
        for item in standing.values()
        if item.kind in PROPOSABLE_KINDS and not item.withdrawn and item.status == STATUS_PROPOSED
    ]


def reply_limit(proposed_count: int) -> int:
    return MAX_REPLY_CHARS + PROPOSAL_REPLY_CHARS_PER_ITEM * proposed_count


def proposal_problems(
    proposed: list[Item], reply: str, needs_answer: bool, confirmation: Confirmation
) -> list[str]:
    """What a reply that is the proposal must hold: the question, and for every proposed change the
    case (by title or id) and the page."""
    if not proposed:
        return []
    problems = []
    if not needs_answer:
        problems.append("`needs_answer` must be true while a change is `proposed`")
    elif not any(mark in reply for mark in QUESTION_MARKS):
        problems.append("the reply must end with the question that puts the proposal to the owner")
    lowered = reply.casefold()
    for item in proposed:
        names = [name for name in (confirmation.title_of(item.node or ""), item.node) if name]
        if names and not any(name.casefold() in lowered for name in names):
            problems.append(
                f"the reply must name the case of {item.id} by its title ({names[0]!r})"
            )
        if item.page and item.page.casefold() not in lowered:
            problems.append(f"the reply must name the page of {item.id} ({item.page!r})")
    return problems
