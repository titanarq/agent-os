"""Who acts: the one thing the app's own code needs to know about a click that the plan cannot say.

The pre-helper's reads, the executor and the slow path's `./state` tool are the app's commands, run
by the driver on behalf of one person's click. The contract between the driver and those commands is
one environment variable, `PUNTAL_ACTOR` (`docs/AGENT_OS.md` §4.7), so that a command in any language
reads it without a change to the operations' shape or to the command line the host configured:

- the JSON request's `actor`, when it names one, sets it;
- otherwise whatever the caller exported as `PUNTAL_ACTOR` is passed on, unchanged;
- otherwise it is not set. The driver never invents an actor.
"""

from __future__ import annotations

import os

from agent_os.product.puntal.constants import ACTOR_VARIABLE


def actor_of(requested_actor: str) -> str:
    """The request's actor, else the one the caller exported, else nobody (the empty string)."""
    return requested_actor or os.environ.get(ACTOR_VARIABLE, "")


def command_environment(actor: str) -> dict[str, str] | None:
    """The environment for a command run on behalf of `actor`, or None to leave it as it is."""
    return {**os.environ, ACTOR_VARIABLE: actor} if actor else None
