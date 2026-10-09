"""The doctor's checks on references between records: the pointers a
node or a decision follows to another record, and the dependency graph between nodes.

Split from `agent_os.product.tree.checks`, which owns the checks on a node's own fields and on the
parent edge; its `CHECKS` table is the union of both tables, and `docs/AGENT_OS.md` carries every
row. A pointer at a file that failed to load is never also reported as dangling: the target has its
own defect, and one fault is one line.
"""

from __future__ import annotations

import pathlib
import subprocess

from agent_os.product.dispatch.touched_code import paths_named_in
from agent_os.product.tree.loader import Defect, Tree
from agent_os.product.tree.models import Node

DANGLING_DECISION = "dangling-decision"
SUPERSEDED_DECISION_IN_USE = "superseded-decision-in-use"
SUPERSEDED_WITHOUT_SUCCESSOR = "superseded-without-successor"
SUCCESSOR_WITHOUT_SUPERSESSION = "successor-without-supersession"
DANGLING_SUCCESSOR = "dangling-successor"
SUCCESSOR_CYCLE = "successor-cycle"
DANGLING_FRICTION_NODE = "dangling-friction-node"
DANGLING_DEPENDENCY = "dangling-dependency"
DEPENDENCY_CYCLE = "dependency-cycle"
IMPLEMENTATION_PATH_MISSING = "implementation-path-missing"
STATES_WITH_BUILT_CODE = ("implemented", "hardened")

REFERENCE_CHECKS: dict[str, str] = {
    DANGLING_DECISION: "a node's `decisions` names an id that is not a decision",
    SUPERSEDED_DECISION_IN_USE: (
        "a node's `decisions` names a superseded decision; it must name the successor"
    ),
    SUPERSEDED_WITHOUT_SUCCESSOR: "a superseded decision has no `superseded_by`",
    SUCCESSOR_WITHOUT_SUPERSESSION: "a decision that is not superseded has a `superseded_by`",
    DANGLING_SUCCESSOR: "`superseded_by` is not the id of any decision",
    SUCCESSOR_CYCLE: "the chain of `superseded_by` pointers loops back on itself",
    DANGLING_FRICTION_NODE: "a friction entry's `node` is not the id of any node",
    DANGLING_DEPENDENCY: "a node's `depends_on` names an id that is not a node",
    DEPENDENCY_CYCLE: "the `depends_on` edges loop back on themselves",
    IMPLEMENTATION_PATH_MISSING: (
        "an implemented or hardened node's `implementation` names a path written from the "
        "repository root (`web/app/x.py`, its first folder there) that does not exist: the code "
        "moved or was deleted. Checked only when the doctor is given the repository"
    ),
}


def check_references(tree: Tree) -> list[Defect]:
    return [
        *check_decision_pointers(tree),
        *check_supersession(tree),
        *check_friction_nodes(tree),
        *check_dependencies(tree),
    ]


def check_dependencies(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for node in tree.nodes.values():
        for dependency_id in node.depends_on:
            if dependency_id in tree.nodes or dependency_id in tree.unusable_ids:
                continue
            reason = (
                f"it is {describe_kind(tree, dependency_id)}, not a node"
                if dependency_id in tree.decisions
                else "no such node"
            )
            defects.append(
                Defect(
                    tree.paths[node.id],
                    DANGLING_DEPENDENCY,
                    f"depends_on: {dependency_id!r}: {reason}",
                )
            )
    return defects + dependency_cycle_defects(tree)


def dependency_cycle_defects(tree: Tree) -> list[Defect]:
    """One defect per node that is on a cycle of `depends_on`: a node is on one exactly when it can
    reach itself, so every member of a cycle is named and a node that merely depends on a cycle is
    not."""
    defects: list[Defect] = []
    for node in tree.nodes.values():
        if node.id in nodes_reachable_through_dependencies(tree, node.id):
            defects.append(
                Defect(
                    tree.paths[node.id],
                    DEPENDENCY_CYCLE,
                    f"`depends_on` leads back to {node.id!r}",
                )
            )
    return defects


def nodes_reachable_through_dependencies(tree: Tree, start_id: str) -> set[str]:
    """Every node id that `start_id` depends on, directly or not; `start_id` itself only when it
    sits on a cycle. Terminates on any graph."""
    reached: set[str] = set()
    pending = [start_id]
    while pending:
        node = tree.nodes.get(pending.pop())
        if node is None:
            continue
        for dependency_id in node.depends_on:
            if dependency_id not in reached:
                reached.add(dependency_id)
                pending.append(dependency_id)
    return reached


def describe_kind(tree: Tree, record_id: str) -> str:
    if record_id in tree.decisions:
        return "a decision"
    node = tree.nodes.get(record_id)
    return f"a {node.type}" if node else "unknown"


def cycle_defects(
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


def current_decision(tree: Tree, decision_id: str) -> str | None:
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


def check_decision_pointers(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for node in tree.nodes.values():
        path = tree.paths[node.id]
        for decision_id in node.decisions:
            if decision_id in tree.unusable_ids:
                continue
            decision = tree.decisions.get(decision_id)
            if decision is None:
                reason = (
                    f"it is {describe_kind(tree, decision_id)}, not a decision"
                    if decision_id in tree.nodes
                    else "no such decision"
                )
                defects.append(
                    Defect(path, DANGLING_DECISION, f"decisions: {decision_id!r}: {reason}")
                )
            elif decision.state == "superseded":
                current = current_decision(tree, decision_id)
                repoint = f"; point at {current!r} instead" if current else ""
                defects.append(
                    Defect(
                        path,
                        SUPERSEDED_DECISION_IN_USE,
                        f"decisions: {decision_id!r} is superseded{repoint}",
                    )
                )
    return defects


def check_supersession(tree: Tree) -> list[Defect]:
    defects: list[Defect] = []
    for decision in tree.decisions.values():
        successor = decision.superseded_by
        if successor is None or successor in tree.unusable_ids:
            continue
        if successor not in tree.decisions:
            reason = (
                f"it is {describe_kind(tree, successor)}, not a decision"
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
    defects += cycle_defects(
        tree,
        successor_of={
            decision_id: decision.superseded_by for decision_id, decision in tree.decisions.items()
        },
        code=SUCCESSOR_CYCLE,
        pointer="superseded_by",
    )
    return defects


def check_friction_nodes(tree: Tree) -> list[Defect]:
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


# THE PATHS A BUILT NODE NAMES STILL EXIST (docs/adr/2026-10-09-the-doctor-resolves-the-root-relative-
# paths-of-a-built-node.md). `implementation` is prose, so this is built for precision and not for
# recall: a false positive turns a sound tree red, a false negative only leaves today's blindness.
# Only nodes that are `implemented` or `hardened` (before that the code may not exist yet); only
# words with a `/`, never a bare `entry.html` (possibly relative to a folder named earlier) or a
# dotted word like `http.client`; and only those whose first folder the repository root holds
# (`answers/puntal_client.py` after `web/app/shell/` is relative, and nothing here can resolve it).
# What survives is a root-relative path whose first folder is real and whose rest is not.


def repository_root_of(directory: pathlib.Path) -> pathlib.Path | None:
    """The git checkout `directory` belongs to, or None when it belongs to none -- a tree under a
    temporary directory, which has no repository to hold its paths against."""
    completed = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return pathlib.Path(completed.stdout.strip()).resolve()


def _missing_paths_of(node: Node, repository_root: pathlib.Path) -> list[str]:
    missing = []
    for path in paths_named_in(node.implementation or ""):
        first_folder, separator, _rest = path.partition("/")
        if not separator or not (repository_root / first_folder).exists():
            continue
        if not (repository_root / path).exists():
            missing.append(path)
    return missing


def check_implementation_paths(tree: Tree, repository_root: pathlib.Path) -> list[Defect]:
    defects = []
    for node in tree.nodes.values():
        if node.state not in STATES_WITH_BUILT_CODE:
            continue
        for path in _missing_paths_of(node, repository_root):
            defects.append(
                Defect(
                    tree.paths[node.id],
                    IMPLEMENTATION_PATH_MISSING,
                    f"`implementation` names {path}, which does not exist in the repository",
                )
            )
    return defects
