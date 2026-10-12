"""Step 2 of the ADR: the group of one round. Greedy, oldest pull request first, one group per
round. The script alone decides what may ever be together; nothing later can add to it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_os.product.dispatch.touched_code import overlapping_paths
from agent_os.product.integrator.facts import PullRequestFacts


@dataclass(frozen=True)
class Candidate:
    facts: PullRequestFacts
    node_touches: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundGroup:
    members: tuple[int, ...]
    left_solo: dict[int, str]


def oldest_first(candidates: Sequence[Candidate]) -> list[Candidate]:
    return sorted(candidates, key=lambda row: (row.facts.created_at, row.facts.number))


def _reason_not_with(member: Candidate, other: Candidate) -> str | None:
    if member.facts.base != other.facts.base:
        return f"another base than #{member.facts.number} ({other.facts.base})"
    shared = sorted(set(member.facts.paths) & set(other.facts.paths))
    if shared:
        return f"changes {shared[0]}, as #{member.facts.number} does"
    shared_touches = overlapping_paths(member.node_touches, other.node_touches)
    if shared_touches:
        return f"touches {shared_touches[0]}, as #{member.facts.number} does by its nodes"
    return None


def choose_group(
    groupable: Sequence[Candidate], max_group_size: int, already_solo: Mapping[int, str]
) -> RoundGroup:
    """`groupable` are the candidates no rule keeps out of a group; `already_solo` carries the
    reasons of those that were kept out. A single member is not a group."""
    ordered = oldest_first(groupable)
    members: list[Candidate] = []
    left_solo = dict(already_solo)
    for candidate in ordered:
        if not members:
            members.append(candidate)
            continue
        if len(members) >= max_group_size:
            left_solo[candidate.facts.number] = f"the group is full ({max_group_size})"
            continue
        refusals = [_reason_not_with(member, candidate) for member in members]
        refusal = next((reason for reason in refusals if reason), None)
        if refusal:
            left_solo[candidate.facts.number] = refusal
        else:
            members.append(candidate)
    if len(members) < 2:
        for member in members:
            left_solo[member.facts.number] = "no other pull request can be proved with it"
        members = []
    return RoundGroup(tuple(member.facts.number for member in members), left_solo)
