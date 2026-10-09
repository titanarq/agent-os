"""`headroom`: read the open issues once, split them by state, and print the answer."""

from __future__ import annotations

from agent_os import issues, lib
from agent_os.lib import label_names
from agent_os.product.dispatch.headroom.assessment import assess_ready_tickets
from agent_os.product.dispatch.headroom.report import render_json, render_text
from agent_os.product.dispatch.headroom.slot_ledger import SlotLedger
from agent_os.product.dispatch.rules import is_v2_host

OPEN_ISSUES_LIMIT = "500"
NOT_A_V2_HOST = (
    "headroom: not a v2 host (`tree.dispatch_by_node` is not true): the tree rules are not in force "
    "here, so there is nothing to assess; compare the dispatchable issues with "
    "planner.max_parallel_issues by hand"
)


def headroom(*, as_json: bool) -> int:
    config = lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG)
    if not is_v2_host(config):
        print(NOT_A_V2_HOST)
        return 0
    open_rows = issues.gh_json(
        "issue",
        "list",
        "--state",
        "open",
        "--json",
        "number,body,labels",
        "--limit",
        OPEN_ISSUES_LIMIT,
    )
    labels = config.project.labels
    ready_rows = [row for row in open_rows if labels.ready in label_names(row)]
    running_rows = [row for row in open_rows if labels.doing in label_names(row)]
    ledger = SlotLedger.of_host(config, running_rows)
    assessments = assess_ready_tickets(ready_rows, open_rows, running_rows, ledger)
    print((render_json if as_json else render_text)(assessments, ledger))
    return 0
