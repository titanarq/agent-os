"""The post-helpers: what an invocation records AFTER the app has its answer.

The telemetry line and the `runs.tsv` row are nothing the click waits for, so they come after the
response has been written and the caller's pipe closed (`cli.release_stdout`).
"""

from __future__ import annotations

from agent_os.product.puntal.options import Options, Request
from agent_os.product.puntal.results import InvocationResult
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.files import append_runs_row
from agent_os.product.puntal.telemetry.record import build_record
from agent_os.product.records import append_json_line


def record_invocation(
    request: Request, options: Options, clock: Clock, result: InvocationResult
) -> dict:
    """Appends the telemetry line and the `runs.tsv` row, and returns the record."""
    record = build_record(request=request, options=options, trace=result.trace, clock=clock)
    append_json_line(options.telemetry_file, record)
    append_runs_row(
        options.run_dir / "runs.tsv",
        result.log_path,
        f"{request.action} @ {request.node_id}",
        options.model,
    )
    return record
