"""The drafter's and the reviewer's answers, validated before anything is written or opened."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml

from agent_os.product.tree.loader import split_frontmatter

DEFINITION_MARKER = "=== DEFINITION ==="
TESTS_MARKER = "=== OBSOLETE TESTS ==="
END_MARKER = "=== END ==="
DISCARDED_HEADING = "## Probado y descartado"
NO_TESTS = "none"
TEST_ACTIONS = ("delete", "adjust")
OBSOLETE_TEST_RE = re.compile(r'^- `([^`]+)` `([^`]+)` \| (\w+) \| "(.+)" \| (.+)$')
APPROVE = "approve"
REJECT = "reject"
MAX_REASON_CHARS = 300
MAX_REASONS = 5
FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```\s*$", re.DOTALL)


@dataclass(frozen=True)
class ObsoleteTest:
    """A test the new definition makes obsolete, with the line of the old definition that justified it."""

    path: str
    test_name: str
    action: str
    old_line: str
    why: str

    def as_markdown(self) -> str:
        return (
            f'- `{self.path}` `{self.test_name}` | {self.action} | "{self.old_line}" | {self.why}'
        )


@dataclass(frozen=True)
class Draft:
    definition: str
    obsolete_tests: tuple[ObsoleteTest, ...]


@dataclass(frozen=True)
class Review:
    approved: bool
    reasons: tuple[str, ...]


def parse_draft(text: str, original_definition: str) -> tuple[Draft | None, list[str]]:
    """`(draft, [])`, or `(None, why)`. The frontmatter must be the original's, and the body must
    close with the `Probado y descartado` section."""
    positions = [text.find(marker) for marker in (DEFINITION_MARKER, TESTS_MARKER, END_MARKER)]
    if -1 in positions or positions != sorted(positions):
        return None, [
            f"the answer lacks {DEFINITION_MARKER}, {TESTS_MARKER}, {END_MARKER} in order"
        ]
    definition = text[positions[0] + len(DEFINITION_MARKER) : positions[1]].strip("\n") + "\n"
    tests_block = text[positions[1] + len(TESTS_MARKER) : positions[2]].strip()
    problems = definition_problems(definition, original_definition)
    if problems:
        return None, problems
    lines = tuple(line.strip() for line in tests_block.splitlines() if line.strip())
    if lines == (NO_TESTS,):
        lines = ()
    obsolete_tests, problems = parse_obsolete_tests(lines, original_definition)
    if problems:
        return None, problems
    return Draft(definition, obsolete_tests), []


def _squeezed(text: str) -> str:
    return " ".join(text.split())


def parse_obsolete_tests(
    lines: tuple[str, ...], original_definition: str
) -> tuple[tuple[ObsoleteTest, ...], list[str]]:
    """No test is proposed without the line of the OLD definition that justified it: the quote must
    be in the original file, word for word (whitespace aside)."""
    original = _squeezed(original_definition)
    proposals: list[ObsoleteTest] = []
    problems: list[str] = []
    for line in lines:
        matched = OBSOLETE_TEST_RE.match(line)
        if not matched:
            problems.append(
                f'an obsolete test line is not `- `path` `test` | action | "quote" | why`: {line!r}'
            )
            continue
        proposal = ObsoleteTest(*matched.groups())
        if proposal.action not in TEST_ACTIONS:
            problems.append(f"the action of {proposal.test_name!r} must be one of {TEST_ACTIONS}")
        elif _squeezed(proposal.old_line) not in original:
            problems.append(
                f"the quote justifying {proposal.test_name!r} is not a line of the old definition: "
                f"{proposal.old_line!r}"
            )
        else:
            proposals.append(proposal)
    return tuple(proposals), problems


def definition_problems(definition: str, original_definition: str) -> list[str]:
    drafted, original = split_frontmatter(definition), split_frontmatter(original_definition)
    if drafted is None:
        return ["the definition does not open with a closed `---` frontmatter block"]
    if original is None:
        return ["the use case on disk has no frontmatter to compare with"]
    try:
        if yaml.safe_load(drafted[0]) != yaml.safe_load(original[0]):
            return ["the frontmatter is not the original's"]
    except yaml.YAMLError as error:
        return [f"the frontmatter does not parse: {error}"]
    headings = [line.strip() for line in drafted[1].splitlines() if line.startswith("## ")]
    if headings.count(DISCARDED_HEADING) != 1 or headings[-1] != DISCARDED_HEADING:
        return [f"`{DISCARDED_HEADING}` must appear once, as the last `##` section"]
    return []


def parse_review(text: str) -> tuple[Review | None, list[str]]:
    stripped = text.strip()
    fenced = FENCE_RE.match(stripped)
    try:
        document = json.loads(fenced.group(1) if fenced else stripped)
    except ValueError as error:
        return None, [f"not a JSON object: {error}"]
    if not isinstance(document, dict) or document.get("verdict") not in (APPROVE, REJECT):
        return None, [f"`verdict` must be `{APPROVE}` or `{REJECT}`"]
    reasons = document.get("reasons")
    if (
        not isinstance(reasons, list)
        or not 1 <= len(reasons) <= MAX_REASONS
        or not all(isinstance(r, str) and r.strip() and len(r) <= MAX_REASON_CHARS for r in reasons)
    ):
        return None, [
            f"`reasons` must hold 1 to {MAX_REASONS} lines of at most {MAX_REASON_CHARS} characters"
        ]
    return Review(document["verdict"] == APPROVE, tuple(r.strip() for r in reasons)), []
