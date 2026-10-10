---
id: fr-merge-work-is-not-reviewed-twice
type: functional-requirement
title: Merge work is not reviewed twice, and the agent in charge improves the coordination
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 3: «revisar los conflictos, muchas PRs con muchos conflictos, provocan revisar dos veces lo mismo (lo puede hacer el nuevo haiku 5.5?), el agente encargado de esto tiene que mejorar la coordinación.»'
decisions:
- dec-dispatch-never-runs-two-tickets-on-the-same-code
- dec-a-doubt-of-how-is-settled-by-an-experiment
experiments:
- kind: spike
  question: 'Can the new Haiku 5.5 take the review of merge conflicts that the owner asks about, at the same quality?'
  outcome: open
  date: '2026-10-10'
mechanism: pending
---
Many pull requests with many conflicts make an agent review the same thing twice: once as the
change was written and again as it is reconciled with what merged meanwhile. The conflicts that do
happen are reviewed, and the agent in charge of merging -- the one that coordinates -- treats each as
evidence that the coordination failed and improves it, so the same kind of conflict does not
recur. Prevention already exists: dispatch never runs two tickets on the same code, and what shares
code or order waits (dec-dispatch-never-runs-two-tickets-on-the-same-code,
fr-independent-work-runs-in-parallel, whose evaluator asks for few merge conflicts); this
requirement is about what still conflicts, and about not paying twice for it.

Whether a lighter model, the new Haiku 5.5 the owner asks about, can do that review is a doubt of
how, so it is settled by the experiment above and not by anyone's estimate
(dec-a-doubt-of-how-is-settled-by-an-experiment). How the review and the improvement of the
coordination are done is the mechanism, and it is left to the first agent that builds it.
