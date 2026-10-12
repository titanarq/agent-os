"""The integration head's checks, read through the existing one-line `bin/dev/wait_checks.sh`."""

from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass

WAIT_CHECKS_SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "bin" / "dev" / "wait_checks.sh"
ALL_SUCCESS, ANY_OTHER, TIMED_OUT = 0, 1, 2
TEST_FAILURE = "FAILURE"


@dataclass(frozen=True)
class ChecksReading:
    outcome: int
    line: str

    @property
    def conclusions(self) -> list[str]:
        """The conclusion of each check of a `<pr> head=<sha7> name=CONCLUSION,...` line."""
        if "head=" not in self.line:
            return []
        checks = self.line.split(" ", 2)[-1]
        return [check.rsplit("=", 1)[-1] for check in checks.split(",") if "=" in check]

    @property
    def is_a_test_failure(self) -> bool:
        """Red because a check FAILED; CANCELLED, TIMED_OUT and the like are the infrastructure."""
        conclusions = [conclusion for conclusion in self.conclusions if conclusion != "SUCCESS"]
        return (
            self.outcome == ANY_OTHER and bool(conclusions) and set(conclusions) == {TEST_FAILURE}
        )


def wait_for_checks(repository: pathlib.Path, pull_request: int, max_minutes: int) -> ChecksReading:
    if not WAIT_CHECKS_SCRIPT.is_file():
        raise FileNotFoundError(f"{WAIT_CHECKS_SCRIPT} is missing")
    finished = subprocess.run(
        ["bash", str(WAIT_CHECKS_SCRIPT), str(repository), str(pull_request), str(max_minutes)],
        capture_output=True,
        text=True,
        check=False,
    )
    return ChecksReading(finished.returncode, finished.stdout.strip())
