- `test-ingest` launches a change only when the owner approved it (#171; branch `fix/171-test-ingest-proposals`) -- with
  `sessions.confirm_before_dispatch` true (the default), a `change` item is opened as an issue only with `status: approved`; a
  `proposed` one or one with no status prints `proposed: ... -- waiting for the owner's word in the chat`, and the raw-text
  fallbacks (rework or change by state, general change) are held (`held: ... -- no interpreter read it`). `understood.json` blocks
  gain `proposals` and `held` (schema stays 1). With the key false nothing changes. The logic is `chat/proposals.py`. Merge after
  #170: until the interpreter writes `status`, nothing can be approved.
