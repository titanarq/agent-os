"""What the judge reads about each pull request of the group, and the first message built from it."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

MAX_HUNK_HEADER_LINES = 40


class GroupIndexError(ValueError):
    """A request that is not an index."""


@dataclass(frozen=True)
class MemberIndex:
    number: int
    title: str
    issue_title: str
    files: tuple[str, ...]
    test_groups: tuple[str, ...]
    hunk_headers: tuple[str, ...] = ()
    hunk_headers_left_out: int = 0


@dataclass(frozen=True)
class GroupIndex:
    members: tuple[MemberIndex, ...]
    union_tests: int | None
    largest_member: int | None
    largest_member_tests: int | None
    extras: dict = field(default_factory=dict)

    @property
    def numbers(self) -> tuple[int, ...]:
        return tuple(member.number for member in self.members)


def _member_section(member: MemberIndex) -> str:
    left_out = (
        f"\n  ({member.hunk_headers_left_out} more hunk header(s) left out)"
        if member.hunk_headers_left_out
        else ""
    )
    return (
        f"## #{member.number}: {member.title}\n"
        f"closes: {member.issue_title or '(no issue)'}\n"
        f"files ({len(member.files)}): {', '.join(member.files) or '-'}\n"
        f"test groups its plan selects: {', '.join(member.test_groups) or '-'}\n"
        "changed symbols:\n  "
        + ("\n  ".join(member.hunk_headers) if member.hunk_headers else "(none read)")
        + left_out
    )


def build_brief(index: GroupIndex) -> str:
    numbers = " ".join(f"#{number}" for number in index.numbers)
    numbers_line = (
        f"tests of the union: {index.union_tests}; tests of the largest member "
        f"(#{index.largest_member}): {index.largest_member_tests}"
    )
    return (
        f"# Proposed group: {numbers}\n{numbers_line}\n\n"
        + "\n\n".join(_member_section(member) for member in index.members)
        + "\n\nAnswer with the JSON object only."
    )


def _text_list(row: dict, key: str) -> tuple[str, ...]:
    value = row.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GroupIndexError(f"{key!r} must be a list of strings")
    return tuple(value)


def _optional_count(document: dict, key: str) -> int | None:
    value = document.get(key)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise GroupIndexError(f"{key!r} must be a number")
    return value


def parse_index(text: str) -> GroupIndex:
    try:
        document = json.loads(text)
        rows = document["members"]
        if not isinstance(rows, list) or len(rows) < 2:
            raise GroupIndexError("`members` must list at least two pull requests")
        members = tuple(
            MemberIndex(
                number=row["number"],
                title=str(row.get("title") or ""),
                issue_title=str(row.get("issue_title") or ""),
                files=_text_list(row, "files"),
                test_groups=_text_list(row, "test_groups"),
                hunk_headers=_text_list(row, "hunk_headers")[:MAX_HUNK_HEADER_LINES],
                hunk_headers_left_out=int(row.get("hunk_headers_left_out") or 0),
            )
            for row in rows
        )
        index = GroupIndex(
            members,
            _optional_count(document, "union_tests"),
            _optional_count(document, "largest_member"),
            _optional_count(document, "largest_member_tests"),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise GroupIndexError(f"the request is not a group index: {error}") from error
    if len(set(index.numbers)) != len(index.numbers) or not all(
        isinstance(number, int) for number in index.numbers
    ):
        raise GroupIndexError("`members` must name distinct pull request numbers")
    return index
