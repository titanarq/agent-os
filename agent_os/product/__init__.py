"""The Agentos v2 subsystems: everything that works on a host's product.

The package root keeps the v1 substrate (guard, lib, issues, install, doctor...); what is new in v2
lives here, one subpackage or module per subsystem (see
`docs/adr/2026-10-07-v2-subsystems-live-under-agent-os-product.md`).

- `agent_os.product.tree` -- the product tree and decision ledger: schemas, doctor, slices, tickets.
- `agent_os.product.puntal` -- the one-shot driver that answers a live UI action: a package.
- `agent_os.product.records` -- what every v2 log shares: JSON-lines append and the versions a
  record carries.
"""
