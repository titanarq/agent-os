"""The session issue's body, and the frozen batch hidden inside it.

The visible part is for the owner, in the order of the batch. The hidden part is one JSON comment:
the numbered questions and digest entries as they were frozen, which is what a reply is parsed
against and what `transcription` compares a pull request with.
"""

from __future__ import annotations

import json
import re

from agent_os.product.sessions.batch import SessionBatch

SESSION_MARKER = "<!-- question-session:v1 -->"
FROZEN_BLOCK = re.compile(r"<!-- question-session-batch\n(.*?)\n-->", re.DOTALL)

REPLY_INSTRUCTIONS = (
    "Answer only the ones you want, in one comment: `1: yes; 3: no, rather <your answer>`. "
    "`yes` accepts the default. Whatever you leave unanswered keeps its default and comes back "
    "in the next session. To take a decision from the digest back, write `reclaim <number>`."
)


def freeze(batch: SessionBatch) -> str:
    payload = {
        "questions": [
            {
                "number": q.number,
                "node": q.node_id,
                "question": q.question,
                "default_answer": q.default_answer,
            }
            for q in batch.questions
        ],
        "digest": [
            {
                "number": d.number,
                "judgment_id": d.judgment_id,
                "node": d.node_id,
                "decision": d.decision,
            }
            for d in batch.digest
        ],
    }
    return "<!-- question-session-batch\n" + json.dumps(payload, ensure_ascii=False) + "\n-->"


def read_frozen_batch(issue_body: str) -> dict:
    """The frozen payload of a session issue; `ValueError` when the body is not one."""
    found = FROZEN_BLOCK.search(issue_body)
    if SESSION_MARKER not in issue_body or found is None:
        raise ValueError("this issue is not a question session")
    return json.loads(found.group(1))


def session_title(date_text: str) -> str:
    return f"Question session {date_text}"


def render_session_body(batch: SessionBatch) -> str:
    lines = [SESSION_MARKER, "", REPLY_INSTRUCTIONS, ""]
    if batch.questions:
        lines.append("## Questions of what")
        current_branch = None
        for question in batch.questions:
            if question.branch_id != current_branch:
                current_branch = question.branch_id
                lines += ["", f"### Branch `{current_branch}`"]
            blocks = (
                f"blocks {question.blocks} node(s)" if question.blocks else "blocks nothing yet"
            )
            lines += [
                "",
                f"**{question.number}.** {question.question}",
                f"- node: `{question.node_id}` ({question.node_title}); {blocks}",
                f"- default, which stands until you answer: {question.default_answer}",
            ]
        lines.append("")
    if batch.challenges:
        lines += ["## Challenges (the work may not be finishable; say whether to go on)", ""]
        for challenge in batch.challenges:
            detail = f": {challenge.explanation}" if challenge.explanation else ""
            lines.append(f"- `{challenge.node_id}` -- {challenge.reason}{detail}")
        lines.append("")
    if batch.digest:
        lines += ["## Decided without you since the last session", ""]
        for entry in batch.digest:
            where = f" on `{entry.node_id}`" if entry.node_id else ""
            lines.append(
                f"- **{entry.number}.** ({entry.role}, {entry.kind}){where}: {entry.decision}"
            )
        if batch.digest_omitted:
            lines.append(f"- ... and {batch.digest_omitted} older one(s) in the judgments log.")
        lines.append("")
    if batch.is_empty:
        lines += ["Nothing is waiting for you.", ""]
    lines.append(freeze(batch))
    return "\n".join(lines) + "\n"
