"""The schemas of the product tree and of the decision ledger.

These models say what SHAPE a record has: which fields exist, which are required, what type each
is, and that an unknown field is an error (`Strict`, the same closed-partition discipline
`config/agents.yaml` has). The RULES a record or a whole tree must also satisfy -- an id that
matches its filename, a parent of the right type, a hardened node that carries an implementation
pointer -- are not here but in `agent_os.tree.checks`, one named code each, so every red check a
host can see has a name to grep for and a row in `docs/AGENT_OS.md`.

A record is one Markdown file. Its YAML frontmatter holds every field below except the one that is
prose by nature: a node's `description` and a decision's `statement` are the Markdown body, so a
file reads as a document and a diff of it reads as one.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from agent_os.lib import Strict

NODE_TYPES = ("goal", "functional-requirement", "use-case")
DECISION_TYPE = "decision"
RECORD_TYPES = (*NODE_TYPES, DECISION_TYPE)

# The id of a record starts with a prefix that says what it is, so a directory listing, a grep and
# a ticket's address marker all read at a glance, and a record whose type was edited without its
# id is a red check (`id-prefix-mismatch`). The rest of the id is a slug chosen once and never
# changed: an id is an address other files point at, so it encodes no position in the tree --
# re-parenting a node edits one `parent:` line and breaks no pointer.
ID_PREFIX_BY_TYPE = {
    "goal": "goal",
    "functional-requirement": "fr",
    "use-case": "uc",
    DECISION_TYPE: "dec",
}

# What a node's parent must be: the hierarchy is goal -> functional requirement -> use case, and a
# goal is the root.
PARENT_TYPE_BY_TYPE = {"functional-requirement": "goal", "use-case": "functional-requirement"}

# A node's solution mechanism is either text or this literal: the lazy-materialization discipline
# of the plan (the first agent that needs it resolves it and writes it back into the node).
MECHANISM_PENDING = "pending"

# The fields that make a node a work item. A goal is a lighthouse, not something to build, and
# carries none of them (`goal-carries-work-fields`). `verification` is deliberately not among them:
# tests run top-down from the goals, so a goal's verification is the acceptance that keeps the work
# under it from drifting, never work to dispatch -- and it is the one field a goal MUST carry
# (`goal-without-evaluators`).
WORK_FIELDS = ("mechanism", "implementation", "spikes", "foundation", "state")

# The two fields that are the Markdown body rather than frontmatter, by record type.
BODY_FIELD_BY_TYPE = {**dict.fromkeys(NODE_TYPES, "description"), DECISION_TYPE: "statement"}

IDENTIFIER_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
Identifier = Annotated[str, StringConstraints(pattern=IDENTIFIER_PATTERN)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OneLine = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\r\n]+$")
]


class Verification(Strict):
    """One evaluator of a node, and exactly one of two kinds: a `command` that exits 0 when the node
    holds, or a `judge` -- a criterion in plain language that an agent judges (pass or fail, with
    reasons) against what was built. The top-down acceptance is essential from the first build and
    cannot always be checked deterministically
    (`docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`).

    A command is what the dispatch ticket's acceptance criteria are made of and what hardens a node
    (`hardened-needs-verification`); a judged criterion is acceptance, never hardening
    (`docs/tree/dec-tests-harden-they-do-not-build.md`)."""

    command: NonBlank | None = None
    # What a pass of the command proves, in one sentence. Optional: the command alone is a
    # criterion, this makes it a readable one. It belongs to a command and to nothing else.
    expects: NonBlank | None = None
    # One paragraph that says what must be true of what was built for the node to be met.
    judge: NonBlank | None = None

    @model_validator(mode="after")
    def _is_a_command_or_a_judged_criterion(self) -> Verification:
        if self.command is not None and self.judge is not None:
            raise ValueError("an entry is a `command` or a `judge`, not both")
        if self.command is None and self.judge is None:
            raise ValueError("an entry needs a `command` or a `judge`")
        if self.judge is not None and self.expects is not None:
            raise ValueError(
                "`expects` says what a `command` proves; a `judge` is a criterion by itself"
            )
        return self

    @property
    def is_judged(self) -> bool:
        return self.judge is not None


class SpikeResult(Strict):
    """What a timeboxed spike found. Difficulty is measured by spikes, never by an agent's own
    estimate, so the outcome is a closed vocabulary a tool can act on: an `infeasible` spike on a
    node whose mechanism is still pending makes it undispatchable (`mechanism-unresolvable`)."""

    question: NonBlank
    outcome: Literal["feasible", "infeasible", "inconclusive"]
    finding: NonBlank
    date: datetime.date


class Node(Strict):
    """One goal, functional requirement or use case. The `description` is the Markdown body."""

    id: Identifier
    type: Literal["goal", "functional-requirement", "use-case"]
    title: OneLine
    description: NonBlank
    # The tree edge. A goal has none; a functional requirement's is a goal; a use case's is a
    # functional requirement (`parent-missing`, `goal-has-parent`, `parent-type-mismatch`).
    parent: Identifier | None = None
    # Where the node's content comes from -- who asked for it, which document, which spike. Free
    # text, at least one: a node nobody can trace back to anything is an unfounded claim.
    sources: list[NonBlank] = Field(min_length=1)
    # The decisions in force on this node, by id. They bind its whole subtree as well: a decision
    # on a requirement binds its use cases, so a slice collects them along the chain of ancestors.
    decisions: list[Identifier] = Field(default_factory=list)
    # Text, or `pending`. Required on a functional requirement and a use case (`missing-work-field`),
    # so that deferring it is a visible choice and not an omission.
    mechanism: NonBlank | None = None
    # Where the built thing lives (a path, a symbol, a pull request). Free text; required once the
    # node is hardened (`hardened-needs-implementation`).
    implementation: NonBlank | None = None
    # Commands and criteria an agent judges. An executable one (a `command`) is mandatory for
    # dispatch: a leaf node without any escalates instead of becoming a ticket
    # (`agent_os.tree.compile`), and a hardened node needs one (`hardened-needs-verification`). On a
    # goal, or on any node with children, it is the acceptance of the subtree -- an evaluator the
    # work below must not break, never work itself -- and a goal must have at least one
    # (`goal-without-evaluators`).
    verification: list[Verification] = Field(default_factory=list)
    state: Literal["pending", "improvised", "hardened"] = "pending"
    # A foundation node (persistence, identity, UI skeleton) must be hardened before the shell goes
    # live and is built as a normal issue, never improvised.
    foundation: bool = False
    spikes: list[SpikeResult] = Field(default_factory=list)

    @property
    def has_executable_verification(self) -> bool:
        """A `command` among the verification entries: what a judged criterion alone is not."""
        return any(check.command is not None for check in self.verification)


class RejectedAlternative(Strict):
    """An option the decision turned down, and why. The record exists so that a worker tempted to
    relitigate the decision finds the answer already written."""

    option: NonBlank
    reason: NonBlank
    # Whether the source of the decision ARGUES against this option (`stated`) or the ledger entry
    # only infers it from the premises or the review triggers (`implied`). An implied alternative
    # is honest bookkeeping, not an invention passed off as history: whoever fills the ledger --
    # an LLM included -- must say which of the two it is writing.
    basis: Literal["stated", "implied"]


class FrictionEntry(Strict):
    """One time a decision made a solution worse. Accumulated against the decision's own id; enough
    of them is what puts a decision under review."""

    date: datetime.date
    summary: NonBlank
    # The node whose solution the constraint made worse, when there is one.
    node: Identifier | None = None
    # A pointer to the evidence (a pull request, a validator review, a run log).
    evidence: NonBlank | None = None


class Decision(Strict):
    """One entry of the ledger. The `statement` -- what was decided and what it binds -- is the
    Markdown body; `title` is the same thing in one line."""

    id: Identifier
    type: Literal["decision"]
    title: OneLine
    statement: NonBlank
    # in-force -> under-review -> superseded. An `under-review` decision is still obeyed
    # ("obey while challenging"): the state says it is being challenged, not that it lapsed.
    state: Literal["in-force", "under-review", "superseded"]
    # The successor's id. Required exactly when the state is `superseded`, and it must exist
    # (`superseded-without-successor`, `successor-without-supersession`, `dangling-successor`).
    superseded_by: Identifier | None = None
    # Needed because a review trigger can be measured in time ("unused after two months").
    decided: datetime.date
    sources: list[NonBlank] = Field(min_length=1)
    # What the decision stands on. When one of them stops being true the decision is due for review.
    premises: list[NonBlank] = Field(min_length=1)
    rejected_alternatives: list[RejectedAlternative] = Field(min_length=1)
    # Any ONE of these firing puts the decision under review, so each is its own entry: a trigger
    # written as "A, or B" is two triggers a consolidator can check separately.
    review_triggers: list[NonBlank] = Field(min_length=1)
    friction: list[FrictionEntry] = Field(default_factory=list)
