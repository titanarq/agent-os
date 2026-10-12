"""`agent-os-integrate plan --judge`: the index of the round's group, one judgment, the final groups.

A group is only kept when the judge says `independent`. No group to judge, `judge: false` (a host's
explicit choice: the rules alone decide), an unreadable fact the index needs, or a judgment that
could not be had are told apart in `source`."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from agent_os.lib import HOST_ROOT
from agent_os.product.integrator.facts import RunCommand
from agent_os.product.integrator.judge.evidence import closed_issue_title, hunk_headers
from agent_os.product.integrator.judge.index import GroupIndex, MemberIndex
from agent_os.product.integrator.judge.options import JudgeRefused, resolve_options
from agent_os.product.integrator.judge.run import Judgment, judge_group, not_judged
from agent_os.product.integrator.judge.verdict import JudgedGroup
from agent_os.product.integrator.plan import RoundPlan
from agent_os.product.puntal.stream.launch import Clock

SOURCE_MECHANICAL = "mechanical rules alone (judge: false)"
SOURCE_MODEL = "judge"


@dataclass(frozen=True)
class JudgedRound:
    groups: tuple[JudgedGroup, ...]
    source: str
    detail: str = ""
    model: str = ""

    def as_json(self) -> dict:
        return {
            "source": self.source,
            "detail": self.detail,
            "model": self.model,
            "groups": [group.as_json() for group in self.groups],
        }

    def summary(self) -> str:
        lines = [f"judged by: {self.source}{' (' + self.model + ')' if self.model else ''}"]
        if self.detail:
            lines.append(f"  could not be judged: {self.detail}")
        for group in self.groups:
            members = " ".join(f"#{number}" for number in group.members)
            kind = "together" if group.together else "alone"
            lines.append(f"  {kind}: {members} -- {group.verdict}: {group.reason}")
        return "\n".join(lines)


def build_index(
    repository: pathlib.Path, run: RunCommand, plan: RoundPlan, repo_flags: list[str]
) -> GroupIndex:
    members = []
    for number in plan.group:
        summary = plan.members[number]
        headers, left_out = hunk_headers(
            repository, run, f"origin/{plan.default_branch}", summary.head_sha
        )
        members.append(
            MemberIndex(
                number=number,
                title=plan.titles.get(number, ""),
                issue_title=closed_issue_title(run, number, repo_flags),
                files=summary.files,
                test_groups=summary.test_groups,
                hunk_headers=headers,
                hunk_headers_left_out=left_out,
            )
        )
    return GroupIndex(
        tuple(members), plan.group_tests, plan.largest_member, plan.largest_member_tests
    )


def judge_round(
    repository: pathlib.Path,
    run: RunCommand,
    plan: RoundPlan,
    repo_flags: list[str],
    *,
    judge_enabled: bool,
) -> JudgedRound:
    if not plan.group:
        return JudgedRound((), "no group to judge")
    if not judge_enabled:
        reason = "the rules allowed it; judge is off"
        return JudgedRound((JudgedGroup(plan.group, "independent", reason),), SOURCE_MECHANICAL)
    index = build_index(repository, run, plan, repo_flags)
    try:
        options = resolve_options(host_root=HOST_ROOT)
        judgment: Judgment = judge_group(index, options, Clock(None))
    except JudgeRefused as refusal:
        judgment = not_judged(index, "not_run", str(refusal))
    return JudgedRound(
        judgment.groups,
        SOURCE_MODEL,
        judgment.detail,
        judgment.model,
    )
