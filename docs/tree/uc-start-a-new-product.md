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
implementation: 'The expert''s first run on a new product (populate the foundations and the first requirements and use cases under the owner''s goals, record the questions for the owner): prompts/expert.md, agent_task.sh expert (#118). The install step and the question session are not part of it.'
---
The owner starts a new product with Agentos: names it and writes its first goals. The clock of
a first usable product starts here, and each new product benefits from what Agentos learned
building the previous ones (goal-improves-with-every-product).
