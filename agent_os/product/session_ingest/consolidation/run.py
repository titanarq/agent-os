"""One consolidation: Sonnet drafts, Opus reviews, and only an approved draft becomes a pull request.

A draft that does not validate or that the reviewer rejects is never opened: the job issue gets one
comment with the reasons and stays open for the next run. There is no retry inside a run (a second
draft would be paid for blind to what was wrong), and no look-back at earlier runs."""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.session_ingest.consolidation import repository
from agent_os.product.session_ingest.consolidation.answer import (
    parse_draft,
    parse_review,
)
from agent_os.product.session_ingest.consolidation.brief import drafter_brief, reviewer_brief
from agent_os.product.session_ingest.consolidation.job import ConsolidationJob
from agent_os.product.session_ingest.consolidation.options import (
    DRAFTER_ROLE,
    REVIEWER_ROLE,
    resolve_options,
)
from agent_os.product.session_ingest.consolidation.turn import answer_one_turn
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.loader import load_tree

EXIT_OPENED = 0
EXIT_NOT_RUN = 2
EXIT_DRAFT_REFUSED = 3
EXIT_DRAFT_REJECTED = 4
TRAILER = "Node-Change: rework"


@dataclass(frozen=True)
class Outcome:
    exit_status: int
    detail: str


def _branch_for(job: ConsolidationJob) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", job.node_id.lower()).strip("-")[:60]
    return f"consolidate/{job.number}-{slug}"


def _defects(worktree: pathlib.Path, tree_root: pathlib.Path) -> set[tuple[str, str, str]]:
    return {
        (str(d.path.relative_to(worktree)), d.code, d.message)
        for d in check_tree(load_tree(tree_root), worktree)
    }


def _refused(job: ConsolidationJob, repo: str, cwd: pathlib.Path, why: str, status: int) -> Outcome:
    repository.comment_on_issue(
        repo,
        job.number,
        f"The consolidation of `{job.node_id}` was not opened as a pull request:\n\n{why}\n\n"
        "The issue stays open; the next run drafts again.",
        cwd,
    )
    return Outcome(status, why)


def consolidate(
    job: ConsolidationJob, *, host_root: pathlib.Path, tree_root_name: str, repo: str, clock: Clock
) -> Outcome:
    drafter = resolve_options(DRAFTER_ROLE, host_root=host_root)
    reviewer = resolve_options(REVIEWER_ROLE, host_root=host_root)
    branch = _branch_for(job)
    with repository.worktree_on_default_branch(host_root, branch) as worktree:
        tree_root = worktree / tree_root_name
        tree = load_tree(tree_root)
        if job.node_id not in tree.nodes:
            return Outcome(
                EXIT_NOT_RUN, f"`{job.node_id}` is not a node of the tree on the default branch"
            )
        node_path = tree.paths[job.node_id]
        before = node_path.read_text()
        defects_before = _defects(worktree, tree_root)

        draft_answer = answer_one_turn(
            role=DRAFTER_ROLE,
            subject=job.node_id,
            options=drafter,
            clock=clock,
            brief=drafter_brief(
                node_id=job.node_id,
                job_body=job.body,
                definition=before,
                mentions=repository.lines_naming(worktree, job.node_id, tree_root_name),
            ),
        )
        if draft_answer.failure:
            return Outcome(EXIT_DRAFT_REFUSED, draft_answer.failure)
        draft, problems = parse_draft(draft_answer.text, before)
        if draft is None:
            return _refused(
                job,
                repo,
                worktree,
                "The draft did not validate: " + "; ".join(problems),
                EXIT_DRAFT_REFUSED,
            )
        unfound = [
            test
            for test in draft.obsolete_tests
            if not (worktree / test.path).is_file()
            or test.test_name not in (worktree / test.path).read_text()
        ]
        if unfound:
            return _refused(
                job,
                repo,
                worktree,
                "The draft proposes tests that are not in the repository: "
                + "; ".join(f"`{test.path}` `{test.test_name}`" for test in unfound),
                EXIT_DRAFT_REFUSED,
            )
        node_path.write_text(draft.definition)
        new_defects = _defects(worktree, tree_root) - defects_before
        if new_defects:
            node_path.write_text(before)
            listed = "; ".join(f"{code}: {message}" for _, code, message in sorted(new_defects))
            return _refused(
                job,
                repo,
                worktree,
                f"The draft breaks the tree doctor: {listed}",
                EXIT_DRAFT_REFUSED,
            )

        review_answer = answer_one_turn(
            role=REVIEWER_ROLE,
            subject=job.node_id,
            options=reviewer,
            clock=clock,
            brief=reviewer_brief(
                node_id=job.node_id, job_body=job.body, before=before, draft=draft
            ),
        )
        if review_answer.failure:
            return Outcome(EXIT_DRAFT_REFUSED, review_answer.failure)
        review, problems = parse_review(review_answer.text)
        if review is None:
            return _refused(
                job,
                repo,
                worktree,
                "The review did not validate: " + "; ".join(problems),
                EXIT_DRAFT_REFUSED,
            )
        reasons = "\n".join(f"- {reason}" for reason in review.reasons)
        if not review.approved:
            return _refused(
                job,
                repo,
                worktree,
                f"The reviewer ({reviewer.model}) rejected the draft:\n\n{reasons}",
                EXIT_DRAFT_REJECTED,
            )

        node_file = node_path.relative_to(worktree)
        title = f"docs(tree): consolidate {job.node_id} into one definition (#{job.number})"
        repository.commit_and_push(worktree, node_file, branch, f"{title}\n\n{TRAILER}\n")
        tests = "\n".join(test.as_markdown() for test in draft.obsolete_tests) or "none"
        body = (
            f"Closes #{job.number}\n\n"
            f"`{node_file}` consolidated into one definition, with `Probado y descartado` pruned. "
            f"Drafted by `{drafter.model}`, reviewed by `{reviewer.model}`, who approved:\n\n{reasons}\n\n"
            "Tests the new definition makes obsolete, each with the line of the old definition that "
            "justified it. They are proposals for the code-quality review of this pull request; "
            f"none was changed here:\n\n{tests}\n"
        )
        url = repository.open_pull_request(worktree, repo, branch, title, body)
        repository.comment_on_issue(repo, job.number, f"Consolidation opened: {url}", worktree)
        return Outcome(EXIT_OPENED, url)
