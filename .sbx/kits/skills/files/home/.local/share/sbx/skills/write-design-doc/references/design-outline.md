# Adaptable design outline

Inspired by Michael Lynch's [Little Moments design document](https://refactoringenglish.com/excerpts/write-an-effective-design-doc/little-moments-design-doc/). Treat its structure as a menu:

| Area | Useful contents |
| --- | --- |
| Orientation | Title, author, status, date, canonical link, purpose, motivation |
| Scope | Desired outcomes, exclusions, budget and delivery constraints |
| People and behavior | User assumptions, role-permission matrix, interface sketches, end-to-end scenarios |
| Product specifics | Feature rules, notifications, migration behavior, intentionally deferred functionality |
| Quality targets | Availability, latency under stated conditions, capacity limits |
| Architecture | Component diagram, technology and service choices, reasons and tradeoffs |
| Data and protection | Sensitive information, retention, deletion, authentication, concrete threats and mitigations |
| Delivery | Demonstrable increments, dependencies, and verification gates |
| Decisions | Unresolved questions, resolved discussions, credible alternatives and rejection reasons |
| Appendices | Required external formats and integration details |

Include only relevant areas. Use original project-specific content. The example's vendors, access policies, numbers, and personal preferences are not defaults or endorsements.

When the implementation will use capable agents, apply the effort and correctness guidance in SKILL.md. Include key invariants and acceptance evidence in the relevant sections rather than creating a separate exhaustive implementation plan.

## Turning inputs into a draft

Build a small working inventory of confirmed requirements, evidence, proposed choices, and unanswered questions. Keep that inventory internal unless it helps the user. Start from the user's stated problem; do not pick an architecture merely to fill the outline.

For each major decision, write the requirement it serves, the proposed behavior, the evidence supporting it, and any remaining uncertainty. A proposed number must remain visibly proposed until confirmed; do not quietly turn an estimate into a requirement.

Use a permission table when several roles differ. In a scenario, follow one actor from trigger to observable result and explain any consequential asynchronous or failure behavior. Use a sketch when layout affects the decision; detailed visual design is optional.

For a small change, merge the useful areas into a short proposal. For a substantial system, expand the areas with meaningful decisions and cross-reference shared rules instead of repeating them. Preserve the user's team template even when it orders these topics differently.
