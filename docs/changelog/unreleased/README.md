# Unreleased changelog notes

One file per branch, named after the branch with hyphens (`fix/dev-method` -> `fix-dev-method.md`),
holding 2-6 lines in the style of the entries of `../../CHANGELOG.md`. A note is never added to
`docs/CHANGELOG.md` directly: two parallel pull requests editing the same line there conflict every
time. When a release is published the notes are folded into the Unreleased section of `docs/CHANGELOG.md`
(newest first) and their files are deleted.
