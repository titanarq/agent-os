"""Rework after a review that asked for changes: the stage the issue's plan was missing.

A worker whose every stage is committed has nothing left to launch, so `worker_task.sh resume`
refused a run whose pull request the validator had sent back with CHANGES_REQUESTED -- and the fix
was done by hand: a new stage appended to the issue's `## Stages` checklist, carrying the review's
fixes, and a relaunch with the review as context. This module is that hand work as a first-class
step (`worker_task.sh <backend> resume --issue <N> --rework`, bin/worker/worker_rework.sh): it reads the
pull request's newest verdict, appends the stage the branch's own commits will then count, and
writes the review down as the context the relaunched run is handed.

Pure functions plus one CLI, `python -m agent_os.product.tracker.rework prepare`; the driver does every `gh` call.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from agent_os.lib import parse_stages

CHANGES_REQUESTED = "CHANGES_REQUESTED"
# The states that settle a pull request's standing, newest wins. A plain comment or a pending
# review says nothing about whether changes are still owed.
SETTLING_REVIEW_STATES = (CHANGES_REQUESTED, "APPROVED", "DISMISSED")

STAGES_HEADING = "## Stages"
_REWORK_TITLE_PREFIX = "Address the changes requested on PR #"


class ReworkRefused(Exception):
    """The run has nothing to rework, said in the words the driver prints."""


def newest_review_requesting_changes(pull_requests: list[dict], branch: str) -> tuple[int, dict]:
    """The `(pull request number, review)` of the newest settling review when it asks for changes.
    Refuses when the branch has no open pull request, no settling review, or when the newest one is
    an approval or a dismissal: those leave nothing owed."""
    if not pull_requests:
        raise ReworkRefused(f"no open pull request has {branch} as its head branch")
    verdicts = []
    for pull_request in pull_requests:
        settling = [
            review
            for review in pull_request.get("reviews") or []
            if review.get("state") in SETTLING_REVIEW_STATES
        ]
        if settling:
            verdicts.append((int(pull_request["number"]), settling[-1]))
    if not verdicts:
        raise ReworkRefused(f"no review on the pull request of {branch} has settled it yet")
    for number, review in verdicts:
        if review["state"] == CHANGES_REQUESTED:
            return number, review
    number, review = verdicts[0]
    raise ReworkRefused(
        f"the newest review of PR #{number} is {review['state']}, not {CHANGES_REQUESTED}"
        " -- no changes are owed"
    )


def rework_stage_title(pull_request: int, existing_titles: list[str]) -> str:
    """The title a rework stage's commit subject must carry. The round number only appears from the
    second round on, so two reworks of one pull request never share a title."""
    prefix = f"{_REWORK_TITLE_PREFIX}{pull_request}"
    earlier_rounds = sum(1 for title in existing_titles if title.startswith(prefix))
    return prefix if earlier_rounds == 0 else f"{prefix} (round {earlier_rounds + 1})"


def with_stage_appended(body: str, title: str) -> str:
    """`body` with `- [ ] <title>` after the last checklist line of its `## Stages` section."""
    lines = body.splitlines()
    heading = next(i for i, line in enumerate(lines) if line.strip() == STAGES_HEADING)
    section_end = next(
        (i for i in range(heading + 1, len(lines)) if lines[i].strip().startswith("##")),
        len(lines),
    )
    last_stage = max(
        i for i in range(heading + 1, section_end) if re.match(r"^\s*-\s*\[[ xX]\]", lines[i])
    )
    lines.insert(last_stage + 1, f"- [ ] {title}")
    return "\n".join(lines) + ("\n" if body.endswith("\n") else "")


def rework_instruction(pull_request: int, review: dict) -> str:
    """What the relaunched run is handed alongside the brief: the review, verbatim."""
    text = (review.get("body") or "").strip()
    if not text:
        text = (
            "(the review has no summary text: its findings are inline comments -- read them with "
            f"`gh pr view {pull_request} --comments`)"
        )
    return (
        f"The pull request #{pull_request} of this branch was sent back with this review:\n\n{text}"
    )


def prepare(
    pull_requests: list[dict], body: str, *, branch: str, stages_done: int, stages_total: int
) -> tuple[str | None, str, str]:
    """`(new issue body or None, the stage the run launches, the context it is handed)`.

    The body is None when a stage is still pending: an earlier `--rework` already appended the
    rework stage and the run was cut before committing it, so the stage to launch exists and a second
    one would only duplicate it."""
    number, review = newest_review_requesting_changes(pull_requests, branch)
    if stages_total == 0:
        raise ReworkRefused("the issue declares no `## Stages` to extend")
    context = rework_instruction(number, review)
    if stages_done < stages_total:
        return None, parse_stages(body)[stages_done], context
    title = rework_stage_title(number, parse_stages(body))
    return with_stage_appended(body, title), title, context


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m agent_os.product.tracker.rework")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--pull-requests", required=True, help="`gh pr list --json` file")
    prepare_parser.add_argument("--issue-body", required=True)
    prepare_parser.add_argument("--branch", required=True)
    prepare_parser.add_argument("--stages-done", type=int, required=True)
    prepare_parser.add_argument("--stages-total", type=int, required=True)
    prepare_parser.add_argument("--body-out", required=True, help="written empty when unchanged")
    prepare_parser.add_argument("--context-out", required=True)
    args = parser.parse_args()
    try:
        new_body, stage, context = prepare(
            json.loads(pathlib.Path(args.pull_requests).read_text() or "[]"),
            pathlib.Path(args.issue_body).read_text(),
            branch=args.branch,
            stages_done=args.stages_done,
            stages_total=args.stages_total,
        )
    except ReworkRefused as refusal:
        # On stdout, where every other refusal of the driver says why.
        print(f"rework refused: {refusal}")
        sys.exit(1)
    pathlib.Path(args.body_out).write_text(new_body or "")
    pathlib.Path(args.context_out).write_text(context)
    print(f"rework stage: {stage}" + ("" if new_body else " (already planned)"))


if __name__ == "__main__":
    main()
