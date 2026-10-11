"""The stop-point between what the interpreter read and what is launched
(`docs/adr/2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md`).

The interpreter sets an item's `status` from its `origin` (`docs/adr/2026-10-11-an-items-origin-sets-its-status-and-the-owner-is-asked-only-about-what-is-derived.md`):
a stated or detected item is `approved`, a derived one `proposed` until the owner says yes in the
chat. `test-ingest` launches what is not waiting:

- `approved` is launched; `proposed` waits and is listed for the owner in `understood.json` under
  `proposals`; an item with no status (a file from before) is launched;
- with `sessions.confirm_before_dispatch` true (review mode) only `approved` is launched: no status
  at all waits too, and text no item covers (the raw-text fallbacks) is **held**, never launched: the
  interpreter did not read it, so there is nothing to put in front of the owner. It is listed under
  `held`.

`understood.json` lists `proposals` (`{id, status, origin, summary, node, page, from_messages}`: each
item proposed, or approved and not launched because it has a problem) and `held` (`{summary, node}`).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_os.product.session_ingest.chat.model import Item

APPROVED = "approved"
PROPOSED = "proposed"


@dataclass(frozen=True)
class HeldText:
    """Owner text that no item covers, kept out of the backlog while the guard is on."""

    summary: str
    node: str | None


def is_awaiting_approval(item: Item, *, confirm_before_dispatch: bool) -> bool:
    """In review mode a status-less item counts as proposed: when in doubt, nothing is launched.
    Outside it only an item the interpreter marked `proposed` waits."""
    if confirm_before_dispatch:
        return item.status != APPROVED
    return item.status == PROPOSED


def proposal_entry(item: Item) -> dict:
    return {
        "id": item.id,
        "status": item.status or PROPOSED,
        "origin": item.origin,
        "summary": item.summary,
        "node": item.node,
        "page": item.page,
        "from_messages": list(item.from_messages),
    }


def held_entry(held: HeldText) -> dict:
    return {"summary": held.summary, "node": held.node}
