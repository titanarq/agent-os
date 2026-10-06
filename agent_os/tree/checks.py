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
snapshots and so a git base, and it does not run a verification command or check that an
implementation pointer resolves.
"""

from __future__ import annotations

from agent_os.tree.loader import (
    BAD_FRONTMATTER,
    DUPLICATE_ID,
    ORPHAN_FILE,
    SCHEMA,
    Defect,
    Tree,
)
from agent_os.tree.models import (
    ID_PREFIX_BY_TYPE,
    MECHANISM_PENDING,
    PARENT_TYPE_BY_TYPE,
    WORK_FIELDS,
    Decision,
    Node,
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
DANGLING_DECISION = "dangling-decision"
SUPERSEDED_DECISION_IN_USE = "superseded-decision-in-use"
SUPERSEDED_WITHOUT_SUCCESSOR = "superseded-without-successor"
SUCCESSOR_WITHOUT_SUPERSESSION = "successor-without-supersession"
DANGLING_SUCCESSOR = "dangling-successor"
SUCCESSOR_CYCLE = "successor-cycle"
DANGLING_FRICTION_NODE = "dangling-friction-node"

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
        "a goal carries a work field (mechanism, implementation, spikes, foundation, or a state "
        "other than pending); `verification` is not one: it is acceptance and never work"
    ),
    GOAL_WITHOUT_EVALUATORS: (
        "a goal's `verification` is empty: a goal needs at least one evaluator, a `command` or a "
        "`judge` criterion an agent judges"
    ),
    MISSING_WORK_FIELD: (
        "a functional requirement or a use case has no `mechanism` (write `pending` to defer it)"
    ),
    FOUNDATION_IMPROVISED: (
        "a foundation node is `improvised`; foundations are built as normal issues and the shell "
        "does not go live until they are hardened"
    ),
    HARDENED_NEEDS_IMPLEMENTATION: "a hardened node has no `implementation` pointer",
    HARDENED_NEEDS_VERIFICATION: (
        "a hardened node has no `verification` with a `command`: tests harden, and a judged "
        "criterion alone is acceptance, not hardening"
    ),
    DANGLING_DECISION: "a node's `decisions` names an id that is not a decision",
    SUPERSEDED_DECISION_IN_USE: (
        "a node's `decisions` names a superseded decision; it must name the successor"
    ),
    SUPERSEDED_WITHOUT_SUCCESSOR: "a superseded decision has no `superseded_by`",
    SUCCESSOR_WITHOUT_SUPERSESSION: "a decision that is not superseded has a `superseded_by`",
    DANGLING_SUCCESSOR: "`superseded_by` is not the id of any decision",
    SUCCESSOR_CYCLE: "the chain of `superseded_by` pointers loops back on itself",
    DANGLING_FRICTION_NODE: "a friction entry's `node` is not the id of any node",
}


def check_tree(tree: Tree) -> list[Defect]:
    """Every defect in the tree, loader's included, in a stable order: by file, then code, then
    message. Empty means the tree is sound."""
    defects = [*tree.defects, *_check_node_records(tree), *_check_decision_records(tree)]
    defects += _check_parent_edges(tree) + _check_decision_pointers(tree)
    defects += _check_supersession(tree) + _check_friction_nodes(tree)
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


def _describe_kind(tree: Tree, record_id: str) -> str:
    if record_id in tree.decisions:
        return "a decision"
    node = tree.nodes.get(record_id)
    return f"a {node.type}" if node else "unknown"


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
                    f"{_describe_kind(tree, parent.id)}",
                )
            )
    defects += _cycle_defects(
        tree,
        successor_of={node_id: node.parent for node_id, node in tree.nodes.items()},
        code=PARENT_CYCLE,
        pointer="parent",
    )
    return defects


def _cycle_defects(
    tree: Tree, *, successor_of: dict[str, str | None], code: str, pointer: str
) -> list[Defect]:
    """One defect per member of every cycle in a graph where each id points at one other id. The
    walk follows the pointer from each id until it leaves the graph or revisits an id of its own
    path; an id already known to lead somewhere harmless is not walked again."""
    defects: list[Defect] = []
    settled: set[str] = set()
    for start in sorted(successor_of):
        path_so_far: list[str] = []
        current: str | None = start
        while current is not None and current in successor_of and current not in settled:
            if current in path_so_far:
                loop = path_so_far[path_so_far.index(current) :]
                rendered = " -> ".join([*loop, current])
                defects += [
                    Defect(tree.paths[member], code, f"`{pointer}` loops: {rendered}")
                    for member in loop
                ]
                break
            path_so_far.append(current)
            current = successor_of[current]
        settled.update(path_so_far)
    return defects


def _current_decision(tree: Tree, decision_id: str) -> str | None:
    """The live end of a chain of supersessions, or None when the chain loops or dangles."""
    seen: set[str] = set()
    current = decision_id
    while current in tree.decisions and tree.decisions[current].state == "superseded":
        if current in seen:
            return None
        seen.add(current)
        successor = tree.decisions[current].superseded_by
        if successor is None:
            return None
        current = successor
    return current if current in tree.decisions else None


def _check_decision_pointers(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for node in tree.nodes.values():
        path = tree.paths[node.id]
        for decision_id in node.decisions:
            if decision_id in tree.unusable_ids:
                continue
            decision = tree.decisions.get(decision_id)
            if decision is None:
                reason = (
                    f"it is {_describe_kind(tree, decision_id)}, not a decision"
                    if decision_id in tree.nodes
                    else "no such decision"
                )
                defects.append(
                    Defect(path, DANGLING_DECISION, f"decisions: {decision_id!r}: {reason}")
                )
            elif decision.state == "superseded":
                current = _current_decision(tree, decision_id)
                repoint = f"; point at {current!r} instead" if current else ""
                defects.append(
                    Defect(
                        path,
                        SUPERSEDED_DECISION_IN_USE,
                        f"decisions: {decision_id!r} is superseded{repoint}",
                    )
                )
    return defects


def _check_supersession(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for decision in tree.decisions.values():
        successor = decision.superseded_by
        if successor is None or successor in tree.unusable_ids:
            continue
        if successor not in tree.decisions:
            reason = (
                f"it is {_describe_kind(tree, successor)}, not a decision"
                if successor in tree.nodes
                else "no such decision"
            )
            defects.append(
                Defect(
                    tree.paths[decision.id],
                    DANGLING_SUCCESSOR,
                    f"superseded_by {successor!r}: {reason}",
                )
            )
    defects += _cycle_defects(
        tree,
        successor_of={
            decision_id: decision.superseded_by for decision_id, decision in tree.decisions.items()
        },
        code=SUCCESSOR_CYCLE,
        pointer="superseded_by",
    )
    return defects


def _check_friction_nodes(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for decision in tree.decisions.values():
        for entry in decision.friction:
            if entry.node is None or entry.node in tree.nodes or entry.node in tree.unusable_ids:
                continue
            defects.append(
                Defect(
                    tree.paths[decision.id],
                    DANGLING_FRICTION_NODE,
                    f"friction of {entry.date}: node {entry.node!r} does not exist",
                )
            )
    return defects
