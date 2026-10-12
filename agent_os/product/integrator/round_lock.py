"""One integration in flight per repository: a non-blocking `flock` on `.cache/integrator.lock`."""

from __future__ import annotations

import fcntl
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

LOCK_FILE_NAME = "integrator.lock"


class IntegrationInFlightError(RuntimeError):
    pass


@contextmanager
def integration_lock(cache_directory: pathlib.Path) -> Iterator[None]:
    cache_directory.mkdir(parents=True, exist_ok=True)
    with (cache_directory / LOCK_FILE_NAME).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise IntegrationInFlightError(
                f"another integration holds {cache_directory / LOCK_FILE_NAME}"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
