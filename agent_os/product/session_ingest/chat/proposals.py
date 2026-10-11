"""The stop-point between what the interpreter read and what is launched
(`docs/adr/2026-10-10-a-test-session-change-is-proposed-to-the-owner-before-it-is-dispatched.md`).

With `sessions.confirm_before_dispatch` true, `test-ingest` opens the issue of a `change` item only
when the interpreter marked it `approved`, which it does only after the owner said yes in the chat:

- `approved` is launched; `proposed`, or no status at all (a file from before), waits and is listed
  for the owner in `understood.json` under `proposals`;
- text no item covers (the raw-text fallbacks) is **held**, never launched: the interpreter did not
  read it, so there is nothing to put in front of the owner. It is listed under `held`;
- with the key false the status is ignored and every change not withdrawn is launched.

`understood.json` lists `proposals` (`{id, status, summary, node, page, from_messages}`: each change
proposed, or approved and not launched because it has a problem) and `held` (`{summary, node}`).
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_os.product.session_ingest.chat.model import Item

APPROVED = "approved"


@dataclass(frozen=True)
class HeldText:
    """Owner text that no item covers, kept out of the backlog while the guard is on."""

    summary: str
    node: str | None


def is_awaiting_approval(item: Item, *, confirm_before_dispatch: bool) -> bool:
    """A status-less item counts as proposed: when in doubt, nothing is launched."""
    return confirm_before_dispatch and item.status != APPROVED


def proposal_entry(item: Item) -> dict:
    return {
        "id": item.id,
        "status": item.status or "proposed",
        "summary": item.summary,
        "node": item.node,
        "page": item.page,
        "from_messages": list(item.from_messages),
    }


def held_entry(held: HeldText) -> dict:
    return {"summary": held.summary, "node": held.node}
