"""What a CI run hands to the workflow: `mode=` as a step output and the plan as a job summary."""

from __future__ import annotations

import os
from collections.abc import Mapping

from agent_os.product.test_selection.plan import TestPlan


def publish_plan_to_github(plan: TestPlan, environment: Mapping[str, str] = os.environ) -> None:
    output_path = environment.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"mode={plan.mode}\n")
    summary_path = environment.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(f"```\n{plan.summary()}\n```\n")
