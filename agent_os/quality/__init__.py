"""The code-quality ratchet (`docs/tree/fr-consolidated-code-is-clear-and-organized-in-depth.md`).

- `agent_os.quality.config` -- the `quality:` section of a host's config.
- `agent_os.quality.ratchet` -- the pure rules: two snapshots in, violations out.
- `agent_os.quality.git_snapshots` -- reads a snapshot from git.
- `agent_os.quality.cli` -- `agent-os-quality --base REF`, what CI calls.
"""
