- Stop-point before a test-session change is dispatched, design only (#167; branch `fix/167-confirm-before-dispatch-adr`) -- on the
  owner's word of 2026-10-10 ("un punto de parada para que yo valide si el trabajo que le vas a dar a cada worker está de acuerdo
  con mi idea"), ADR 2026-10-10 designs it: the interpreter proposes each `change` item in the chat (task, case by title, page,
  what the worker receives and what is left out) and the owner's answer, bound by code to the exact content shown, sets the item's
  `status`; `test-ingest` launches only an `approved` change and holds the raw-text fallbacks; `understood.json` gains `proposals`
  and `held`; one key, `sessions.confirm_before_dispatch`, on for now. Built by #169 (key and `status`), #170 (interpreter), #171
  (`test-ingest`); the host's part is described in the ADR. No code in this entry.
