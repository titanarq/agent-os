- Interpreter reads the puntal's recent answers (#180, branch `fix/180-interpreter-invocations`): the brief lists the request's
  `invocations`; the prompt teaches `verdict`, a correction of the case (`change`/`decision`) and `puntal_change` with the target
  proposed and confirmed in the dialog; code refuses an item that names an invocation the request did not carry, treats `verdict` and
  `puntal_change` as proposals bound to what the owner was shown, and never lets a `puntal_change` be born `approved`, whatever
  `sessions.confirm_before_dispatch` says. The item kinds, verdicts and statuses are defined once (`interpreter/constants.py`).
