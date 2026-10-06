---
id: dec-a-component-has-a-core-and-extensions
type: decision
title: A component has a core and extensions, and is tested once
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal D (Agentos improves with every product)
- Owner design discussion of 2026-10-06, point 8 (representation invention)
premises:
- Requiring every piece to keep the whole verification rejects edge cases an extension could handle
- A reused block tested in every place that uses it costs the same test many times
- A repository of tested components pays off in the medium term if it is built well from the start
rejected_alternatives:
- option: A component covers every case of every use, its verification intact
  reason: 'The owner, more lax: a core verified within its scope, extended where it is integrated'
  basis: stated
- option: A shared components repository from day one
  reason: 'The owner: it starts inside the vector'
  basis: stated
review_triggers:
- Extensions grow until they hide what the core does
- A change to a core breaks an extension its tests did not cover
---
A component (a `component` record in the tree) has a core whose verification is scoped to it; the
cases outside the core are covered by extending it where it is integrated (`extends:`), and the
extension brings its own tests. Nodes declare the components they `use:`; a component is tested
once, and a change to its core runs the core's tests and those of everything that extends or uses
it. What must never break is the products' top-down acceptance. Components live in the product's
own package first and are promoted to a shared repository when another product reuses them. The
expert looks for what is already solved before designing (copy by analogy), and explores wide and
thin when there is no direct solution; compression -- context per slice, new code per node, reuse
-- measures the trend, and schemas are mined from the documents puntales improvise.
