"""`bin/consolidator_task.sh <issue>`: consolidates the use case a `consolidate.<node>` job issue names.

Exit status: 0 the pull request is open, 2 not run (not a consolidation job, or a refusal to run as
configured), 3 no draft could be had or it did not validate, 4 the reviewer rejected the draft.
Stdout is the pull request's URL or the reason, one line."""

from __future__ import annotations

import argparse
import sys

from agent_os.issues import repo_name
from agent_os.lib import HOST_ROOT, load_agents_config
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.session_ingest.consolidation.job import NotAConsolidationJob, read_job
from agent_os.product.session_ingest.consolidation.options import ConsolidationRefused
from agent_os.product.session_ingest.consolidation.repository import RepositoryError
from agent_os.product.session_ingest.consolidation.run import EXIT_NOT_RUN, consolidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="consolidator_task.sh")
    parser.add_argument("issue", type=int, help="the open `consolidate.<node>` job issue")
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_agents_config()
        repo = repo_name()
        job = read_job(arguments.issue, repo, config.project.labels.consolidation)
        outcome = consolidate(
            job,
            host_root=HOST_ROOT,
            tree_root_name=config.tree.root,
            repo=repo,
            clock=Clock(None),
        )
    except (NotAConsolidationJob, ConsolidationRefused, RepositoryError) as refusal:
        print(f"consolidation not run: {refusal}", file=sys.stderr)
        return EXIT_NOT_RUN
    print(outcome.detail)
    return outcome.exit_status


if __name__ == "__main__":
    sys.exit(main())
