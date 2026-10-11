"""What binds an item to the owner, decided by code and never by the prompt: a new item's status is
set from its origin (`proposals/origin.py`; in review mode, `sessions.confirm_before_dispatch`, it
is always `proposed`), `approved` is bound to what the owner was shown, a node must be one the
brief listed, and the reply must be the proposal. See
`docs/adr/2026-10-11-an-items-origin-sets-its-status-and-the-owner-is-asked-only-about-what-is-derived.md`
and `docs/adr/2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md`."""

from __future__ import annotations

import dataclasses
import pathlib

from agent_os.product.interpreter.constants import (
    MAX_LISTED_USE_CASES,
    MAX_REPLY_CHARS,
    PROPOSAL_REPLY_CHARS_PER_ITEM,
    QUESTION_MARKS,
    STATUS_APPROVED,
    STATUS_PROPOSED,
    InterpreterRefused,
)
from agent_os.product.interpreter.items import Item
from agent_os.product.interpreter.proposals.origin import (
    STATUS_KINDS,
    is_newly_detected,
    status_born_of,
)
from agent_os.product.interpreter.request import CaseContext, Request


@dataclasses.dataclass(frozen=True)
class Confirmation:
    """The nodes the owner may be told an item is about: the case first, then the tree's use cases
    (id, title), cut at `MAX_LISTED_USE_CASES`. `review_mode` is `sessions.confirm_before_dispatch`:
    every item is born proposed."""

    listed: tuple[tuple[str, str], ...]
    omitted: int = 0
    review_mode: bool = False

    def title_of(self, node_id: str) -> str | None:
        return dict(self.listed).get(node_id)


def confirmation_from_tree(
    case: CaseContext | None, tree_root: pathlib.Path, *, review_mode: bool = False
) -> Confirmation:
    """Fails loudly when the tree cannot be read: an item tied to a node nobody can check is what
    asking the owner exists to prevent."""
    from agent_os.product.tree.loader import TreeRootError, load_tree, require_tree_root

    try:
        tree = load_tree(require_tree_root(tree_root))
    except TreeRootError as error:
        raise InterpreterRefused(
            f"the interpreter needs the tree to list the use cases an item may be about: {error}"
        ) from error
    use_cases = sorted(
        (node.id, node.title) for node in tree.nodes.values() if node.type == "use-case"
    )
    listed = [(case.id, case.title)] if case else []
    listed += [entry for entry in use_cases if not case or entry[0] != case.id]
    return Confirmation(
        tuple(listed[:MAX_LISTED_USE_CASES]),
        max(0, len(listed) - MAX_LISTED_USE_CASES),
        review_mode,
    )


def confirmation_for(
    case: CaseContext | None, tree_root: pathlib.Path, *, review_mode: bool
) -> Confirmation | None:
    """The listing the items' nodes are checked against. Outside review mode a host with no tree
    still gets every item's status from its origin: only the node check and the listing go."""
    try:
        return confirmation_from_tree(case, tree_root, review_mode=review_mode)
    except InterpreterRefused:
        if review_mode:
            raise
        return None


def _same_proposal(item: Item, previous: Item) -> bool:
    return (item.kind, item.summary, item.node, item.page, item.verdict, item.invocations) == (
        previous.kind,
        previous.summary,
        previous.node,
        previous.page,
        previous.verdict,
        previous.invocations,
    )


def _bound_status(
    item: Item, previous: Item | None, *, review_mode: bool
) -> tuple[str | None, str | None]:
    """`(status, retry reason)` for one item the model returned. The status is the code's: the
    model may only write `approved` on an unchanged item the owner has just said yes to."""
    if item.withdrawn:
        return (previous.status if previous else None), None
    if item.kind not in STATUS_KINDS:
        reason = (
            "`approved` is only for a `change`, `decision`, `verdict` or `puntal_change` item"
            if item.status == STATUS_APPROVED
            else None
        )
        return None, reason
    unchanged = previous is not None and _same_proposal(item, previous)
    if unchanged and previous.status == STATUS_APPROVED:
        return STATUS_APPROVED, None
    born = status_born_of(item, review_mode=review_mode)
    if item.status != STATUS_APPROVED:
        return born, None
    if previous is None:
        return born, "`approved` on an item that is new in this turn: its status is set by code"
    if not unchanged:
        return born, (
            "`approved` on an item whose kind, summary, node, page, verdict or invocation changed: "
            "a correction gets the status its origin gives it"
        )
    return STATUS_APPROVED, None


def bind_items(
    items: list[Item], request: Request, confirmation: Confirmation | None
) -> tuple[list[Item], list[str]]:
    """The returned items with their status set by code, and every reason to retry. Without a
    `confirmation` (no tree was read) no node is checked and review mode is off."""
    review_mode = confirmation is not None and confirmation.review_mode
    carried = {item.id: item for item in request.items}
    allowed_nodes = {item.node for item in request.items if item.node}
    if confirmation is not None:
        allowed_nodes |= {node_id for node_id, _ in confirmation.listed}
    if request.page_node:
        allowed_nodes.add(request.page_node.id)
    bound, problems = [], []
    for item in items:
        status, reason = _bound_status(item, carried.get(item.id), review_mode=review_mode)
        if reason:
            problems.append(f"{item.id}: {reason}")
        if (
            confirmation is not None
            and item.node
            and not item.withdrawn
            and item.node not in allowed_nodes
        ):
            problems.append(
                f"{item.id}: `node` {item.node!r} is not the case nor a use case listed in the brief"
            )
        bound.append(dataclasses.replace(item, status=status))
    return bound, problems


def proposed_after_this_turn(items: list[Item], request: Request) -> list[Item]:
    standing = {item.id: item for item in request.items}
    standing.update({item.id: item for item in items})
    return [
        item
        for item in standing.values()
        if item.kind in STATUS_KINDS and not item.withdrawn and item.status == STATUS_PROPOSED
    ]


def detected_this_turn(items: list[Item], request: Request) -> list[Item]:
    carried = {item.id: item for item in request.items}
    return [item for item in items if is_newly_detected(item, carried)]


def reply_limit(announced_count: int) -> int:
    return MAX_REPLY_CHARS + PROPOSAL_REPLY_CHARS_PER_ITEM * announced_count


def proposal_problems(
    proposed: list[Item],
    detected: list[Item],
    reply: str,
    needs_answer: bool,
    confirmation: Confirmation,
) -> list[str]:
    """What a reply that puts items to the owner must hold: for a proposed item the question the
    owner answers (`needs_answer`), and for every proposed or newly detected item the case (by
    title or id) and the page, so the owner knows what is being asked or what was applied."""
    problems = []
    if proposed and not needs_answer:
        problems.append("`needs_answer` must be true while an item is `proposed`")
    elif proposed and not any(mark in reply for mark in QUESTION_MARKS):
        problems.append("the reply must end with the question that puts the proposal to the owner")
    lowered = reply.casefold()
    for item in [*proposed, *detected]:
        names = [name for name in (confirmation.title_of(item.node or ""), item.node) if name]
        if names and not any(name.casefold() in lowered for name in names):
            problems.append(
                f"the reply must name the case of {item.id} by its title ({names[0]!r})"
            )
        if item.page and item.page.casefold() not in lowered:
            problems.append(f"the reply must name the page of {item.id} ({item.page!r})")
    return problems
