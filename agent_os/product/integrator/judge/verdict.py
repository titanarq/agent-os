"""The model's answer against what the script allowed. The answer may confirm, split or send solo;
anything else is rejected, and a rejected answer, like no answer, sends every pull request solo."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

INDEPENDENT = "independent"
VERDICTS = (INDEPENDENT, "unsure", "coupled")
MAX_REASON_CHARS = 200
FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```\s*$", re.DOTALL)


@dataclass(frozen=True)
class JudgedGroup:
    members: tuple[int, ...]
    verdict: str
    reason: str

    @property
    def together(self) -> bool:
        """Only an independent group of two or more is proved as one."""
        return self.verdict == INDEPENDENT and len(self.members) >= 2

    def as_json(self) -> dict:
        return {
            "members": list(self.members),
            "verdict": self.verdict,
            "reason": self.reason,
            "together": self.together,
        }


def every_one_solo(members: tuple[int, ...], reason: str) -> tuple[JudgedGroup, ...]:
    return tuple(JudgedGroup((number,), "unsure", reason) for number in members)


def final_groups(proposed: tuple[JudgedGroup, ...]) -> tuple[JudgedGroup, ...]:
    """A group that is not `independent` lands as its members alone, each with the reason."""
    final: list[JudgedGroup] = []
    for group in proposed:
        if group.together or len(group.members) == 1:
            final.append(group)
        else:
            final.extend(
                JudgedGroup((number,), group.verdict, f"{group.verdict}: {group.reason}")
                for number in group.members
            )
    return tuple(final)


def _group_problems(row, allowed: set[int], seen: set[int]) -> tuple[JudgedGroup | None, list[str]]:
    if not isinstance(row, dict):
        return None, ["a group is not an object"]
    members, verdict, reason = row.get("members"), row.get("verdict"), row.get("reason")
    problems: list[str] = []
    if (
        not isinstance(members, list)
        or not members
        or not all(isinstance(n, int) and not isinstance(n, bool) for n in members)
    ):
        return None, ["`members` must be a non-empty list of numbers"]
    if verdict not in VERDICTS:
        problems.append(f"`verdict` must be one of {', '.join(VERDICTS)}")
    if not isinstance(reason, str) or not reason.strip() or "\n" in reason.strip():
        problems.append("`reason` must be one line of text")
    elif len(reason) > MAX_REASON_CHARS:
        problems.append(f"`reason` is longer than {MAX_REASON_CHARS} characters")
    if outside := sorted(set(members) - allowed):
        problems.append(f"{outside} are not in the proposed group")
    repeated = sorted((set(members) & seen) | {n for n in members if members.count(n) > 1})
    if repeated:
        problems.append(f"{repeated} appear more than once")
    if problems:
        return None, problems
    return JudgedGroup(tuple(sorted(members)), verdict, reason.strip()), []


def parse_verdict(
    text: str, expected: tuple[int, ...]
) -> tuple[tuple[JudgedGroup, ...] | None, list[str]]:
    """`(groups, [])` when the answer partitions `expected`, else `(None, why)`."""
    stripped = text.strip()
    fenced = FENCE_RE.match(stripped)
    try:
        document = json.loads(fenced.group(1) if fenced else stripped)
    except ValueError as error:
        return None, [f"not a JSON object: {error}"]
    rows = document.get("groups") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows:
        return None, ["the answer must be an object with a non-empty `groups` list"]
    allowed, seen = set(expected), set()
    groups: list[JudgedGroup] = []
    problems: list[str] = []
    for row in rows:
        group, row_problems = _group_problems(row, allowed, seen)
        problems += row_problems
        if group:
            groups.append(group)
            seen |= set(group.members)
    if missing := sorted(allowed - seen):
        problems.append(f"{missing} are in no group")
    if problems:
        return None, problems
    return tuple(sorted(groups, key=lambda group: group.members)), []
