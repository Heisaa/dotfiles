# Completeness and consistency check

Apply this operational checklist to the actual proposal. Absence of a heading alone is not a finding. Identify a relevant decision or contradiction before requesting more detail.

- Can a reader trace each major outcome to proposed behavior and a way to assess success?
- Do scenarios, permission tables, interface contracts, and architecture agree about who can do what?
- Do components and data flows in diagrams match the prose, including any bypass paths around the application?
- Do proposed targets name the workload and measurement conditions? Are feasibility claims supported, or clearly awaiting validation?
- Are third-party capabilities and price assumptions verified when they materially determine the design?
- Where asynchronous work matters, does the design address retries, duplicate effects, partial completion, and user-visible status at an appropriate depth?
- Where migration matters, are mappings, validation, and recovery from interruption sufficiently clear to evaluate the approach?
- Do privacy promises agree with actual access routes, exports, logs, backups, and deletion behavior?
- Does each material risk have a mitigation, explicit acceptance, or unresolved decision? Avoid treating an unverified claim as a guarantee.
- Can proposed milestones be demonstrated, and do their dependencies and verification gates make sense?
- Are shortcuts justified by actual constraints rather than assumed human coding time? Does added complexity have a requirement-based purpose?
- Are critical invariants and acceptance criteria explicit enough for an implementing agent to verify? Are proposed tests distinguished from results?
- Are effort claims grounded, separating implementation from review, integration, and long-term costs?
- Are unresolved assumptions distinguishable from settled requirements and decisions?

Fix supported inconsistencies directly when drafting. When evidence is missing, preserve the uncertainty and identify the next useful action. In review mode, present findings ordered by impact with the affected passage and recommended correction; do not dump this checklist as generic feedback.

Stop once material gaps are corrected or explicitly surfaced. Never claim production readiness solely because the checklist was applied.
