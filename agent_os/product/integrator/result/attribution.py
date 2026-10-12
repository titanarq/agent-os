"""Which member a failing test belongs to: the member whose own test plan selects it. Pure, so a
recorded suite summary index is enough to try it."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Mapping

from agent_os.product.test_selection.plan import TestPlan

PYTHON_SUFFIX = ".py"


class SummaryIndexError(ValueError):
    pass


def read_failing_test_ids(summary_index_path: pathlib.Path) -> tuple[str, ...]:
    """The ids of `suite.summary.json` (written by `bin/dev/run_suite.sh`): never the raw log."""
    try:
        index = json.loads(summary_index_path.read_text())
        return tuple(failure["id"] for failure in index["failures"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SummaryIndexError(f"{summary_index_path} is not a suite summary index: {error}")


def _module_path_of(test_id: str) -> str:
    """`tests.product.test_x.TestCase::test_name` as `tests/product/test_x.TestCase`."""
    return test_id.split("::", 1)[0].replace(".", "/")


def plan_selects_test(plan: TestPlan, test_id: str) -> bool:
    if plan.mode == "full":
        return True
    module_path = _module_path_of(test_id)
    for entry in plan.tests:
        entry_without_suffix = entry.removeprefix("./").rstrip("/").removesuffix(PYTHON_SUFFIX)
        if module_path == entry_without_suffix or module_path.startswith(
            entry_without_suffix + "/"
        ):
            return True
    return False


def member_to_evict(
    failing_test_ids: tuple[str, ...], plans_by_member: Mapping[int, TestPlan]
) -> tuple[int | None, str]:
    """`(member, "")` when the failures implicate exactly one member, else `(None, why solo)`."""
    if not failing_test_ids:
        return None, "the check is red but the summary index lists no failing test"
    implicated: set[int] = set()
    for test_id in failing_test_ids:
        selecting = {
            number for number, plan in plans_by_member.items() if plan_selects_test(plan, test_id)
        }
        if not selecting:
            return None, f"no member's plan selects the failing test {test_id}"
        implicated |= selecting
    if len(implicated) == 1:
        return next(iter(implicated)), ""
    names = " ".join(f"#{number}" for number in sorted(implicated))
    return None, f"the failures implicate several members: {names}"
