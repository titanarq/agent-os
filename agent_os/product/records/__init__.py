"""What every v2 log has in common: where a record is appended and which versions it carries.

The puntal's telemetry and feedback use it today; the judgments log of `docs/AGENTOS_V2_PLAN.md`
("Recording conventions") uses it next, so nothing here knows what a puntal is.

- `append_json_line` -- one JSON object on one line, appended under an exclusive lock.
- `record_versions` -- the model, the CLI version and the method version of a record.
"""

from agent_os.product.records.jsonl import append_json_line, read_json_lines
from agent_os.product.records.versions import record_versions

__all__ = ["append_json_line", "read_json_lines", "record_versions"]
