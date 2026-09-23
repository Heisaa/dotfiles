---
name: write-design-doc
description: Draft, revise, or review software design documents and technical RFCs for agent-assisted implementation, with readable HTML deliverables by default. Use for proposed engineering designs, architecture proposals, or checking a design before implementation; exclude visual design briefs and ordinary code documentation.
---

# Write Design Docs

## Design principles

Apply this condensed adaptation of Michael Lynch’s [How to Write an Effective Software Design Document](https://refactoringenglish.com/excerpts/write-an-effective-design-doc/):

- Scale effort to risk, coordination needs, and project longevity. Select useful sections rather than filling every heading.
- Prioritize decisions expensive to reverse; leave easily changed details for implementation.
- Open with a plain-language purpose and enough context for an unfamiliar colleague. Express goals as outcomes; identify likely scope misunderstandings as non-goals.
- Explain the proposed system through concrete scenarios, interfaces, dependencies, and editable diagrams where helpful. Preserve diagram sources.
- State constraints and measurable service targets, with a way to observe failures.
- Address relevant threats, trust boundaries, sensitive-data handling, logging, and legal constraints.
- Choose milestones that expose useful results to stakeholders early.
- Briefly justify rejected credible alternatives.
- Record unresolved problems with options and the next action. When settled, retain the discussion alongside the decision.

## Designing for capable implementing agents

Prefer the simplest design that fully satisfies the requirements. Do not select a shortcut or weaken correctness solely because a robust implementation would traditionally require more human coding time. Do not equate complexity with correctness or assume agent implementation is free.

Evaluate implementation effort separately from verification, human review, integration, operations, maintenance, and migration costs. Account for agent execution costs and actual constraints when material; avoid unsupported speed multipliers and human developer-day estimates. Code volume alone is a poor proxy for total effort.

Make key invariants, interface contracts, failure behavior, and observable acceptance criteria explicit enough for an implementing agent to verify. Connect each major requirement to its acceptance evidence; distinguish proposed checks from checks actually run. Preserve existing system constraints and compatibility requirements.

Where a small experiment would resolve a consequential uncertainty, propose it or run it if already authorized. Bound the experiment by a question and stopping condition, and record its evidence and limitations. Writing a design does not itself authorize implementation or production changes.

Plan work as demonstrable outcomes with dependencies and verification gates. Describe interfaces between independently implementable parts when useful, but do not assume parallel work eliminates integration or human decision costs. Keep speculative features out of scope even when they are cheap to generate.

## Supporting workflow

For a substantial new design, or when asked to match the Little Moments example's depth, read [references/design-outline.md](references/design-outline.md). Adapt the outline to the project and existing template; do not reproduce the example's product or technology choices.

Before delivering a substantial draft or reviewing an existing design, read [references/completeness-checklist.md](references/completeness-checklist.md). Use it to find consequential gaps, not to require every section. A request to match the example calls for comparable specificity in relevant decisions, not comparable length.

## Output format

Default to a self-contained HTML file for completed designs and substantive review reports. Read [references/html-output.md](references/html-output.md) before producing it. Honor an explicit alternative format; answer brief questions directly. For revisions, preserve the source document and team structure, making HTML a presentation copy unless the user requests conversion or replacement.

## Execution guidance

Determine whether the user wants a draft, revision, or review. Use the supplied project notes and permitted workspace evidence. Preserve an existing team template and the requested output format.

Never invent measurements, requirements, dates, owners, approvals, or source links. Label proposed targets and assumptions explicitly. If missing information prevents a meaningful design, ask a focused question; otherwise produce the useful portion and identify what remains unknown.

For drafting, connect each major proposed decision to the evidence or requirement it addresses. Distinguish existing behavior from intended behavior. For revisions, preserve established decisions unless the user requests reconsideration or evidence reveals a conflict; explain material changes.

For reviews, lead with consequential findings, identify the affected passage, explain the likely impact, and recommend a concrete correction or question. Separate blocking uncertainty from optional editorial improvements. Do not rewrite the whole document unless requested.

Before delivery, check that the proposal actually supports its stated outcomes, internal claims agree, and unresolved assumptions are visible. Report remaining decisions without describing the design as approved or implementation-ready unless supported. Creating a document does not authorize implementing the system or contacting reviewers.
