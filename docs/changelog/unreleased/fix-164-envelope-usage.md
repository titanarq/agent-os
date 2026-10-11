- The feedback interpreter's envelope carries `usage` and `latency_s` (#164; branch `fix/164-envelope-usage`) -- a host
  writes its own `interpret_feedback` line in the puntal telemetry file and could only fill `cost_usd` and the duration it measured: `tokens` stayed
  `null` because the envelope on stdout had no tokens, although the interpreter's own record (`<cache>/interpreter/telemetry.jsonl`)
  always did. The envelope now has `usage` (same shape as that record's) and `latency_s.total`; both `null` on `not_run`. Additive: `schema` stays 1.
  Documented in `docs/FEEDBACK_INTERPRETER.md`.
