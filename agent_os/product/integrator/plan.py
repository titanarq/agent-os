"""The dry run of a round: read the pull requests, drop what is not a candidate, keep what lands
alone, group the rest. It writes nothing and calls nothing that changes GitHub."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Sequence
from dataclasses import dataclass

from agent_os.product.dispatch.touched_code import touched_paths_of
from agent_os.product.integrator.candidates import reason_not_a_candidate
from agent_os.product.integrator.facts import RunCommand, read_facts
from agent_os.product.integrator.grouping import Candidate, choose_group
from agent_os.product.integrator.solo_rules import reason_to_land_alone
from agent_os.product.shared.config import IntegratorConfig
from agent_os.product.test_selection.manifest import Manifest
from agent_os.product.test_selection.node_changes import (
    node_ids_by_changed_path,
)
from agent_os.product.test_selection.plan import TestPlan, plan_tests
from agent_os.product.tree.loader import load_tree


@dataclass(frozen=True)
class RoundPlan:
    default_branch: str
    group: tuple[int, ...]
    group_tests: int | None
    largest_member: int | None
    largest_member_tests: int | None
    not_candidates: dict[int, str]
    solo: dict[int, str]
    titles: dict[int, str]

    def as_json(self) -> dict:
        return {
            "default_branch": self.default_branch,
            "group": list(self.group),
            "union_plan_tests": self.group_tests,
            "largest_member": self.largest_member,
            "largest_member_plan_tests": self.largest_member_tests,
            "not_candidates": {str(n): reason for n, reason in self.not_candidates.items()},
            "solo": {str(n): reason for n, reason in self.solo.items()},
        }

    def summary(self) -> str:
        def line(number: int, reason: str) -> str:
            return f"  #{number} {self.titles.get(number, '')[:60]}: {reason}"

        lines = [f"default branch: {self.default_branch}"]
        if self.group:
            lines.append("group: " + " ".join(f"#{number}" for number in self.group))
            lines.append(
                f"  union plan: {self.group_tests} test path(s); largest member "
                f"#{self.largest_member}: {self.largest_member_tests} test path(s)"
            )
        else:
            lines.append("group: none (one at a time, as today)")
        lines += ["solo:", *(line(n, r) for n, r in self.solo.items())] if self.solo else []
        if self.not_candidates:
            lines += ["not candidates:", *(line(n, r) for n, r in self.not_candidates.items())]
        return "\n".join(lines)


@dataclass(frozen=True)
class TestSelectionInputs:
    manifest: Manifest | None
    manifest_path: str
    tree_root: str
    tree_ancestors: dict[str, list[str]]


def _own_plan(inputs: TestSelectionInputs, paths: Sequence[str]) -> TestPlan:
    if inputs.manifest is None:
        return TestPlan("full", "test selection is off")
    return plan_tests(
        inputs.manifest,
        paths,
        node_ids_by_changed_path(paths, inputs.tree_root),
        inputs.tree_ancestors,
    )


def _node_touches(repository: pathlib.Path, inputs: TestSelectionInputs, facts) -> tuple[str, ...]:
    """The code the nodes this pull request changes declare they touch, read from the checkout's
    tree: the data the start gate compares (`dispatch.touched_code`)."""
    node_ids = node_ids_by_changed_path(facts.paths, inputs.tree_root).values()
    if not node_ids or not (repository / inputs.tree_root).is_dir():
        return ()
    nodes = load_tree(repository / inputs.tree_root).nodes
    found = [
        path
        for node_id in node_ids
        if node_id in nodes
        for path in touched_paths_of(nodes[node_id])
    ]
    return tuple(dict.fromkeys(found))


def plan_round(
    repository: pathlib.Path,
    run: RunCommand,
    pull_requests: Sequence[int],
    default_branch: str,
    integrator: IntegratorConfig,
    inputs: TestSelectionInputs,
    repo_flags: list[str],
) -> RoundPlan:
    facts_by_number = {
        number: read_facts(repository, run, number, repo_flags)
        for number in dict.fromkeys(pull_requests)
    }
    not_candidates: dict[int, str] = {}
    solo: dict[int, str] = {}
    plans: dict[int, TestPlan] = {}
    groupable: list[Candidate] = []
    for number, facts in facts_by_number.items():
        reason = reason_not_a_candidate(facts, default_branch)
        if reason:
            not_candidates[number] = reason
            continue
        plans[number] = _own_plan(inputs, facts.paths)
        reason = reason_to_land_alone(
            facts, plans[number], integrator.solo_paths, inputs.manifest_path
        )
        if reason:
            solo[number] = reason
        else:
            groupable.append(Candidate(facts, _node_touches(repository, inputs, facts)))
    chosen = choose_group(groupable, integrator.max_group_size, solo)
    group_tests = largest = largest_tests = None
    if chosen.members:
        union_paths = sorted({p for n in chosen.members for p in facts_by_number[n].paths})
        group_tests = len(_own_plan(inputs, union_paths).tests)
        largest = max(chosen.members, key=lambda n: (len(plans[n].tests), -n))
        largest_tests = len(plans[largest].tests)
    return RoundPlan(
        default_branch,
        chosen.members,
        group_tests,
        largest,
        largest_tests,
        not_candidates,
        dict(sorted(chosen.left_solo.items())),
        {number: facts.title for number, facts in facts_by_number.items()},
    )


def render(plan: RoundPlan, output_format: str) -> str:
    return json.dumps(plan.as_json(), indent=2) if output_format == "json" else plan.summary()
