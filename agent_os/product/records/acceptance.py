"""The owner's acceptance of a node, as the node itself records it.

Written by `agent-os-sessions test-ingest` when a closed test session accepted a case of the node,
and read by the hardening order: what the owner accepted, and how often, says what to consolidate
first (`docs/tree/dec-use-orders-hardening-and-the-owner-order-wins.md`). The trailer of the commit
that writes it is `Node-Change: usage`, never `owner`: an agent transcribes the owner's verdict, it
does not give one.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import StringConstraints

from agent_os.lib import Strict


class Acceptance(Strict):
    """One test session in which the owner accepted this node's case."""

    # The id of the session file the app wrote (`ts-<date>-<time>-<hex>`), so the verdict can be
    # traced to the session, and a second ingestion of that session recognises its own entry.
    session: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    # The day the session was closed.
    date: datetime.date
