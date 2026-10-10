"""The names, kinds and exit statuses the feedback interpreter shares."""

from __future__ import annotations

from agent_os.product.puntal.constants import (
    EXIT_ANSWERED,
    EXIT_BACKEND_FAILED,
    EXIT_CEILING_CUT,
    EXIT_CONTRACT_VIOLATION,
    EXIT_INVALID_PLAN,
    EXIT_NOT_RUN,
    EXIT_TIMEOUT,
)

INTERPRETER_ROLE = "interpreter"
# Bumped on any incompatible change of the request, the envelope or an item.
CONTRACT_SCHEMA = 1

ROLE_OWNER = "owner"
ROLE_AGENT = "agent"
THREAD_ROLES = (ROLE_OWNER, ROLE_AGENT)

KIND_CHANGE = "change"
KIND_DECISION = "decision"
KIND_QUESTION_OF_WHAT = "question_of_what"
ITEM_KINDS = (KIND_CHANGE, KIND_DECISION, KIND_QUESTION_OF_WHAT)

MAX_REPLY_CHARS = 1200
ITEM_ID_PREFIX = "item-"
# The model gets one more turn after an output the validator rejected, and no more.
MAX_RETRIES = 1

# The same statuses as the puntal's, so a host that already maps them needs nothing new.
OUTCOME_INVALID_OUTPUT = "invalid_output"
OUTCOME_EXIT_STATUS = {
    "ok": EXIT_ANSWERED,
    "error": EXIT_BACKEND_FAILED,
    "not_run": EXIT_NOT_RUN,
    "contract_violation": EXIT_CONTRACT_VIOLATION,
    "ceiling_cut": EXIT_CEILING_CUT,
    OUTCOME_INVALID_OUTPUT: EXIT_INVALID_PLAN,
    "timeout": EXIT_TIMEOUT,
}


class InterpreterRefused(Exception):
    """An interpretation that cannot be run as asked: the request or the config is wrong. Raised
    before anything is spent."""
