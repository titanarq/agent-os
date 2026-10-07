"""The batch one session freezes: the open questions of `what`, the challenges, and the digest.

Everything is read from the tree and the judgments log at the moment the session opens and is then
written into the issue; the issue, not the tree, is what the owner's reply is parsed against, so a
question that changes later cannot shift the numbers under an answer already given.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_os.product.tree.loader import Tree

DIGEST_LIMIT = 20


@dataclass(frozen=True)
class SessionQuestion:
    number: int
    node_id: str
    node_title: str
    branch_id: str
    question: str
    default_answer: str
    blocks: int


@dataclass(frozen=True)
class SessionChallenge:
    node_id: str
    node_title: str
    branch_id: str
    reason: str
    explanation: str | None


@dataclass(frozen=True)
class DigestEntry:
    number: int
    judgment_id: str
    role: str
    kind: str
    node_id: str | None
    decision: str


@dataclass
class SessionBatch:
    questions: list[SessionQuestion] = field(default_factory=list)
    challenges: list[SessionChallenge] = field(default_factory=list)
    digest: list[DigestEntry] = field(default_factory=list)
    digest_omitted: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.questions or self.challenges or self.digest)


def branch_of(tree: Tree, node_id: str) -> str:
    """The goal at the root of the chain of parents; the node itself when the chain is broken."""
    seen = {node_id}
    current = node_id
    while True:
        parent = tree.nodes[current].parent
        if parent is None or parent not in tree.nodes or parent in seen:
            return current
        seen.add(parent)
        current = parent


def blocked_by(tree: Tree, node_id: str) -> int:
    """How many other nodes wait on this one: what is below it, and whatever depends on it or on
    anything below it."""
    below = {node_id}
    grew = True
    while grew:
        grew = False
        for candidate in tree.nodes.values():
            if candidate.id not in below and candidate.parent in below:
                below.add(candidate.id)
                grew = True
    waiting = set(below)
    grew = True
    while grew:
        grew = False
        for candidate in tree.nodes.values():
            if candidate.id not in waiting and waiting.intersection(candidate.depends_on):
                waiting.add(candidate.id)
                grew = True
    return len(waiting) - 1


def _ordered_open_questions(tree: Tree) -> list[SessionQuestion]:
    found = []
    for node in tree.nodes.values():
        for experiment in node.experiments:
            if experiment.is_open_what_question:
                found.append(
                    SessionQuestion(
                        number=0,
                        node_id=node.id,
                        node_title=node.title,
                        branch_id=branch_of(tree, node.id),
                        question=experiment.question,
                        default_answer=experiment.default_answer or "",
                        blocks=blocked_by(tree, node.id),
                    )
                )
    strongest_block_of_branch: dict[str, int] = {}
    for question in found:
        strongest = strongest_block_of_branch.get(question.branch_id, -1)
        strongest_block_of_branch[question.branch_id] = max(strongest, question.blocks)
    found.sort(
        key=lambda q: (
            -strongest_block_of_branch[q.branch_id],
            q.branch_id,
            -q.blocks,
            q.node_id,
            q.question,
        )
    )
    return [
        SessionQuestion(**{**question.__dict__, "number": position})
        for position, question in enumerate(found, start=1)
    ]


def build_batch(tree: Tree, judgments_since_last_session: list[dict]) -> SessionBatch:
    """A question is open when its outcome is `open` and its scope is `what`: an unanswered one of
    an earlier session is simply still open, which is how it comes back with its default."""
    challenges = [
        SessionChallenge(
            node_id=node.id,
            node_title=node.title,
            branch_id=branch_of(tree, node.id),
            reason=node.challenge.reason,
            explanation=node.challenge.explanation,
        )
        for node in sorted(tree.nodes.values(), key=lambda n: n.id)
        if node.challenge is not None
    ]
    shown = judgments_since_last_session[-DIGEST_LIMIT:]
    digest = [
        DigestEntry(
            number=position,
            judgment_id=judgment["judgment_id"],
            role=judgment["role"],
            kind=judgment["kind"],
            node_id=judgment.get("node"),
            decision=judgment["decision"],
        )
        for position, judgment in enumerate(shown, start=1)
    ]
    return SessionBatch(
        questions=_ordered_open_questions(tree),
        challenges=challenges,
        digest=digest,
        digest_omitted=len(judgments_since_last_session) - len(shown),
    )
