"""Test selection: which tests a branch must run, from a declarative manifest and the branch's diff.

`agent-os-tests check|plan|run` (also `python -m agent_os.product.test_selection`). The design is
`docs/adr/2026-10-10-a-branch-runs-the-tests-its-manifest-maps-to-what-it-touched.md`.

- `manifest` -- the strict YAML model, one file or a folder of files.
- `checks` -- the manifest's own defects, among them a test file no group maps.
- `changed_paths` -- the paths a branch changes against the merge-base with its base.
- `manifest_changes` -- what a branch changed in the manifest itself.
- `plan` -- the pure function from those inputs to a `TestPlan`.
- `cli` -- the three commands.
"""
