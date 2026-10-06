---
id: uc-start-a-new-product
type: use-case
title: Start a new product
parent: fr-a-usable-product-exists-early
sources:
- 'Owner design discussion of 2026-10-06: what the owner does with Agentos (its use cases)'
mechanism: |-
  Stage 1. agent-os-install installs Agentos in the product's repository (agent_os/ subtree,
  config/agents.yaml, the tree root); the owner writes the first goals and their evaluators; the
  expert's first questions reach the owner in a question session.
---
The owner starts a new product with Agentos: names it and writes its first goals. The clock of
a first usable product starts here, and each new product benefits from what Agentos learned
building the previous ones (goal-improves-with-every-product).
