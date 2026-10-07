"""The owner's reply to a session, parsed against the batch the session froze.

Grammar (`docs/adr/2026-10-07-the-reply-to-a-question-session-is-a-short-numbered-list.md`).
Items are separated by `;` or a line break and each one is either

    N: yes                      accept the default of question N
    N: no, rather <answer>      the answer is <answer>   (`no:` and `no -` work too)
    N: no                       decline the default without giving another: stays open
    N: <anything else>          that text is the answer
    reclaim M                   take digest entry M back: it becomes a question of what

A `;` inside an answer is part of it unless what follows starts a new item. Anything that is not an
item is ignored; a number the batch does not have is reported, never guessed at. When one number is
answered twice the later answer stands, across comments too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ITEM_BOUNDARY = re.compile(r"\s*(?:;|\n)\s*(?=(?:\d+\s*:|reclaim\s+\d+))", re.IGNORECASE)
QUESTION_ITEM = re.compile(r"^(\d+)\s*:\s*(.+)$", re.DOTALL)
RECLAIM_ITEM = re.compile(r"^reclaim\s+(\d+)\s*[.;]?$", re.IGNORECASE)
ACCEPT_WORDS = {"yes", "y", "ok", "accept", "accepted"}
REJECT_WITH_ANSWER = re.compile(
    r"^no\s*[,:\-]\s*(?:rather\s+|instead\s+)?(?P<answer>.+)$", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class ReplyItem:
    number: int
    kind: str  # "accept-default" | "answer" | "decline"
    text: str | None = None


@dataclass
class ParsedReply:
    answers: dict[int, ReplyItem] = field(default_factory=dict)
    reclaims: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedAnswer:
    number: int
    node_id: str
    question: str
    answer: str
    accepted_default: bool


@dataclass
class ResolvedReply:
    answers: list[ResolvedAnswer] = field(default_factory=list)
    reclaimed_digest_entries: list[dict] = field(default_factory=list)
    declined_numbers: list[int] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    return text.strip().rstrip(".").strip()


def parse_reply(comment: str, into: ParsedReply | None = None) -> ParsedReply:
    parsed = into or ParsedReply()
    for raw_item in ITEM_BOUNDARY.split(comment.strip()):
        item = raw_item.strip()
        reclaim = RECLAIM_ITEM.match(item)
        if reclaim:
            number = int(reclaim.group(1))
            if number not in parsed.reclaims:
                parsed.reclaims.append(number)
            continue
        answered = QUESTION_ITEM.match(item)
        if not answered:
            continue
        number, body = int(answered.group(1)), answered.group(2).strip()
        if _clean(body).lower() in ACCEPT_WORDS:
            parsed.answers[number] = ReplyItem(number, "accept-default")
        elif _clean(body).lower() == "no":
            parsed.answers[number] = ReplyItem(number, "decline")
        else:
            rejected = REJECT_WITH_ANSWER.match(body)
            text = _clean(rejected.group("answer") if rejected else body)
            parsed.answers[number] = ReplyItem(number, "answer", text)
    return parsed


def resolve_reply(comments: list[str], frozen_batch: dict) -> ResolvedReply:
    """The owner's comments, in the order they were written, against the frozen batch."""
    parsed = ParsedReply()
    for comment in comments:
        parse_reply(comment, parsed)
    questions = {question["number"]: question for question in frozen_batch["questions"]}
    digest = {entry["number"]: entry for entry in frozen_batch["digest"]}
    resolved = ResolvedReply()
    for number, item in sorted(parsed.answers.items()):
        question = questions.get(number)
        if question is None:
            resolved.problems.append(f"there is no question {number} in this session")
        elif item.kind == "decline":
            resolved.declined_numbers.append(number)
        else:
            accepted = item.kind == "accept-default"
            resolved.answers.append(
                ResolvedAnswer(
                    number=number,
                    node_id=question["node"],
                    question=question["question"],
                    answer=question["default_answer"] if accepted else item.text or "",
                    accepted_default=accepted,
                )
            )
    for number in parsed.reclaims:
        if number in digest:
            resolved.reclaimed_digest_entries.append(digest[number])
        else:
            resolved.problems.append(f"there is no digest entry {number} in this session")
    return resolved
