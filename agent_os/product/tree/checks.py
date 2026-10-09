"""The tree doctor: every rule a tree and its ledger must satisfy, one named code each.

`check_tree` is the ONE implementation of "is this tree sound": `agent-os-tree validate` prints its
lines, `compile` refuses to render a ticket from a tree it finds anything in, and a host's own test
suite can call it to fail CI -- the way host literals fail `tests/test_no_host_literals.py`. A
rule that is only an instruction in a prompt is a rule that gets forgotten; this one is red.

`CHECKS` is the list of rules, code to one sentence. `docs/AGENT_OS.md` carries the same table and
a test keeps the two equal, so a rule cannot be added here and left undocumented.

Scope, stated because it is a choice (`docs/adr/2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`): the doctor reads ONE snapshot of
the tree. It checks that a record is well-formed and consistent with the others; it does not check
that a state TRANSITION was legal (a hardened node going back to pending), which needs two
snapshots and so a git base, and it does not run a verification command. It resolves an
implementation pointer only when it is given the repository, and only the paths written from the
repository root of a built node (`implementation_paths.py`).
"""

from __future__ import annotations

import pathlib

from agent_os.product.tree.implementation_paths import (
    IMPLEMENTATION_PATH_MISSING,
    check_implementation_paths,
)
from agent_os.product.tree.loader import (
    BAD_FRONTMATTER,
    DUPLICATE_ID,
    ORPHAN_FILE,
    SCHEMA,
    Defect,
    Tree,
)
from agent_os.product.tree.models import (
    ID_PREFIX_BY_TYPE,
    MECHANISM_PENDING,
    PARENT_TYPE_BY_TYPE,
    WORK_FIELDS,
    Decision,
    Node,
)
from agent_os.product.tree.reference_checks import (
    REFERENCE_CHECKS,
    SUCCESSOR_WITHOUT_SUPERSESSION,
    SUPERSEDED_WITHOUT_SUCCESSOR,
    check_references,
    cycle_defects,
    describe_kind,
)

ID_FILENAME_MISMATCH = "id-filename-mismatch"
ID_PREFIX_MISMATCH = "id-prefix-mismatch"
PARENT_MISSING = "parent-missing"
GOAL_HAS_PARENT = "goal-has-parent"
DANGLING_PARENT = "dangling-parent"
PARENT_TYPE_MISMATCH = "parent-type-mismatch"
PARENT_CYCLE = "parent-cycle"
GOAL_CARRIES_WORK_FIELDS = "goal-carries-work-fields"
GOAL_WITHOUT_EVALUATORS = "goal-without-evaluators"
MISSING_WORK_FIELD = "missing-work-field"
FOUNDATION_IMPROVISED = "foundation-improvised"
HARDENED_NEEDS_IMPLEMENTATION = "hardened-needs-implementation"
HARDENED_NEEDS_VERIFICATION = "hardened-needs-verification"

CHECKS: dict[str, str] = {
    ORPHAN_FILE: (
        "a file under the root that is neither a node nor a decision: not Markdown, no "
        "frontmatter, or a frontmatter `type` that is none of the record types"
    ),
    BAD_FRONTMATTER: "the frontmatter is not valid YAML, or is not a mapping of fields",
    SCHEMA: (
        "a field is missing, unknown, of the wrong type or empty (a decision's premises, "
        "rejected alternatives and review triggers are mandatory and non-empty), or the Markdown "
        "body that is the description or the statement is blank"
    ),
    DUPLICATE_ID: "two files claim the same id",
    ID_FILENAME_MISMATCH: "the `id` is not the file's name without `.md`",
    ID_PREFIX_MISMATCH: ("the `id` does not start with its type's prefix (goal-, fr-, uc-, dec-)"),
    PARENT_MISSING: "a functional requirement or a use case has no `parent`",
    GOAL_HAS_PARENT: "a goal has a `parent`; a goal is the root of the tree",
    DANGLING_PARENT: "the `parent` is not the id of any node",
    PARENT_TYPE_MISMATCH: (
        "the parent has the wrong type: a functional requirement hangs under a goal, a use case "
        "under a functional requirement"
    ),
    PARENT_CYCLE: "the chain of `parent` pointers loops back on itself",
    GOAL_CARRIES_WORK_FIELDS: (
        "a goal carries a work field (mechanism, implementation, experiments, depends_on, "
        "foundation, or a state other than pending); `verification` is not one: it is acceptance and never work"
    ),
    GOAL_WITHOUT_EVALUATORS: (
        "a goal's `verification` is empty: a goal needs at least one evaluator, a `command` or a "
        "`judge` criterion an agent judges"
    ),
    MISSING_WORK_FIELD: (
        "a functional requirement or a use case has no `mechanism` (write `pending` to defer it)"
    ),
    FOUNDATION_IMPROVISED: (
        "a foundation node is `improvised`; foundations are built as normal tickets and the shell "
        "does not go live until they are implemented and accepted (their tests come later)"
    ),
    HARDENED_NEEDS_IMPLEMENTATION: "a hardened node has no `implementation` pointer",
    HARDENED_NEEDS_VERIFICATION: (
        "a hardened node has no `verification` with a `command`: tests harden, and a judged "
        "criterion alone is acceptance, not hardening"
    ),
    IMPLEMENTATION_PATH_MISSING: (
        "an implemented or hardened node's `implementation` names a path written from the "
        "repository root (`web/app/x.py`, its first folder there) that does not exist: the code "
        "moved or was deleted. Checked only when the doctor is given the repository"
    ),
    **REFERENCE_CHECKS,
}


def check_tree(tree: Tree, repository_root: pathlib.Path | None = None) -> list[Defect]:
    """Every defect in the tree, loader's included, in a stable order: by file, then code, then
    message. Empty means the tree is sound. The one rule that reads the repository and not the tree
    alone (`implementation-path-missing`) runs when `repository_root` is given: `compile` and `slice`
    leave it out, because a stale pointer in one node's prose must not stop every other ticket."""
    defects = [*tree.defects, *_check_node_records(tree), *_check_decision_records(tree)]
    defects += check_references(tree)
    defects += _check_parent_edges(tree)
    if repository_root is not None:
        defects += check_implementation_paths(tree, repository_root)
    return sorted(set(defects), key=lambda defect: (str(defect.path), defect.code, defect.message))


def _check_identity(tree: Tree, record: Node | Decision, defects: list[Defect]) -> None:
    path = tree.paths[record.id]
    if record.id != path.stem:
        defects.append(
            Defect(path, ID_FILENAME_MISMATCH, f"id {record.id!r} but the file is {path.name!r}")
        )
    prefix = ID_PREFIX_BY_TYPE[record.type]
    if not record.id.startswith(f"{prefix}-"):
        defects.append(
            Defect(
                path,
                ID_PREFIX_MISMATCH,
                f"id {record.id!r} should start with {prefix + '-'!r} for a {record.type}",
            )
        )


def _check_decision_records(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for decision in tree.decisions.values():
        path = tree.paths[decision.id]
        _check_identity(tree, decision, defects)
        if decision.state == "superseded" and decision.superseded_by is None:
            defects.append(
                Defect(path, SUPERSEDED_WITHOUT_SUCCESSOR, "superseded, but names no successor")
            )
        if decision.state != "superseded" and decision.superseded_by is not None:
            defects.append(
                Defect(
                    path,
                    SUCCESSOR_WITHOUT_SUPERSESSION,
                    f"superseded_by {decision.superseded_by!r} on a decision that is "
                    f"{decision.state}",
                )
            )
    return defects


def _check_node_records(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for node in tree.nodes.values():
        path = tree.paths[node.id]
        _check_identity(tree, node, defects)
        if node.type == "goal":
            if node.parent is not None:
                defects.append(Defect(path, GOAL_HAS_PARENT, f"parent {node.parent!r} on a goal"))
            carried = _work_fields_a_goal_carries(node)
            if carried:
                defects.append(
                    Defect(path, GOAL_CARRIES_WORK_FIELDS, f"a goal carries {', '.join(carried)}")
                )
            if not node.verification:
                defects.append(
                    Defect(
                        path,
                        GOAL_WITHOUT_EVALUATORS,
                        "no evaluator in `verification`: a goal needs at least one, a `command` "
                        "or a `judge` criterion an agent judges",
                    )
                )
            continue
        if node.parent is None:
            defects.append(Defect(path, PARENT_MISSING, f"a {node.type} needs a `parent`"))
        if node.mechanism is None:
            defects.append(
                Defect(
                    path,
                    MISSING_WORK_FIELD,
                    f"a {node.type} needs a `mechanism` (write `{MECHANISM_PENDING}` to defer it)",
                )
            )
        # The node's own flag, not inherited: a use case under a foundation requirement that is not
        # itself flagged may be improvised; `compile` orders it with the foundations, nothing more.
        if node.foundation and node.state == "improvised":
            defects.append(
                Defect(path, FOUNDATION_IMPROVISED, "a foundation node is built, never improvised")
            )
        if node.state == "hardened":
            if node.implementation is None:
                defects.append(
                    Defect(path, HARDENED_NEEDS_IMPLEMENTATION, "hardened, but no `implementation`")
                )
            if not node.has_executable_verification:
                defects.append(
                    Defect(
                        path,
                        HARDENED_NEEDS_VERIFICATION,
                        "hardened, but no `verification` with a `command` (tests harden; a "
                        "judged criterion alone is acceptance, not hardening)",
                    )
                )
    return defects


def _work_fields_a_goal_carries(goal: Node) -> list[str]:
    defaults = Node.model_fields
    return [
        name
        for name in WORK_FIELDS
        if getattr(goal, name) != defaults[name].get_default(call_default_factory=True)
    ]


def _check_parent_edges(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for node in tree.nodes.values():
        if node.parent is None or node.parent in tree.unusable_ids:
            continue
        path = tree.paths[node.id]
        parent = tree.nodes.get(node.parent)
        if parent is None:
            reason = (
                "it is a decision, not a node" if node.parent in tree.decisions else "no such node"
            )
            defects.append(Defect(path, DANGLING_PARENT, f"parent {node.parent!r}: {reason}"))
            continue
        expected = PARENT_TYPE_BY_TYPE.get(node.type)
        if expected is not None and parent.type != expected:
            defects.append(
                Defect(
                    path,
                    PARENT_TYPE_MISMATCH,
                    f"a {node.type} hangs under a {expected}, but parent {parent.id!r} is "
                    f"{describe_kind(tree, parent.id)}",
                )
            )
    defects += cycle_defects(
        tree,
        successor_of={node_id: node.parent for node_id, node in tree.nodes.items()},
        code=PARENT_CYCLE,
        pointer="parent",
    )
    return defects
