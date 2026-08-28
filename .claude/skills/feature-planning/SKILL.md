---
name: feature-planning
description: Hierarchical top-down planning for products, features, and systems before any code is written. Use this skill whenever the user wants to plan, design, spec, or scope a new feature, product, module, refactor, or system — including phrases like "let's plan X", "help me design Y", "I want to build Z", "spec out", "break down this feature", or when they describe something they intend to build and need a structured plan first. Also use it when resuming work on an existing plan in a plans/ directory. Do NOT use for planning a single small bug fix or a task that is obviously one or two steps.
---

# Feature Planning

A workflow for turning a one-sentence idea into a layered plan, one level of detail at a time, with the user reviewing each level before you descend into the next.

## Why it works this way

Plans fail in two opposite ways: they stay so vague that the first line of code reveals a hole, or they dive into detail so early that a single wrong assumption invalidates hours of work. This skill avoids both by making detail *earned*. First the *what* is agreed (spec.md: stories, domain model, non-goals), then the *how* is elaborated one level at a time, and you only expand an item after the level above it has survived user review. When detail work reveals that a higher level — or the spec itself — was wrong, which is normal and expected, the fix flows upward before work continues downward.

Your role in this workflow is planner, not implementer. Do not write implementation code during planning. Function signatures, types, and interface sketches belong in the plan; function bodies do not.

## The levels

Levels are not content tiers — there is no rule about what *kind* of content belongs at which level. A level is simply one step more detailed than the level above it. What that detail looks like depends entirely on the size and complexity of what's being planned: a small utility might have its important function signatures right in level 1; a large system might not reach signatures until level 4. Let each expansion answer "what does this item actually consist of?" at whatever granularity is one notch finer than the parent.

Two structural rules apply uniformly:

- **At most 10 items at every level.** Level 1 has at most 10 items total, and every expanded item breaks into at most 10 sub-items. If an item needs more than 10, that's a signal it should be split into two items at its own level (or that its parent needs restructuring) — fix that first rather than overflowing.
- **The stopping rule:** stop descending into an item as soon as its important function signatures and interfaces are pinned down. That can happen at any level. Do not pad out deeper levels for symmetry. Level 4 is the normal maximum depth; go deeper only when genuinely justified (a large or intricate subsystem) and say so explicitly to the user when you propose it.

Depth is per-item, not global. A plan where item 3 goes to L4 while item 7 stops at L1 ("update the docs") is healthy, not inconsistent.

## Files

Plans live in the repo so they version with the code. One file per level:

```
plans/<feature-slug>/
├── spec.md           (what is being built)
├── level-1.md        (how, coarsest)
├── level-2.md
├── level-3.md
└── level-4.md        (only if needed)
```

Item numbering is hierarchical and stable: L1 items are `1`–`10`; item `3` expands into `3.1`, `3.2`, … in level-2.md; item `3.2` expands into `3.2.1`, … in level-3.md. Never renumber existing items when inserting — append (`3.4`) or use letter suffixes (`3.2b`) so cross-references never break.

### spec.md template

```markdown
# <Feature name> — Spec

## Pitch
<The user's original 1–3 sentence description, lightly edited for clarity.>

## Assumptions
<The assumptions settled during the opening discussion, as short bullets.>

## Stories
<At most 10 top-level entries. Job stories ("When <situation>, I want
to <motivation>, so I can <outcome>") or user stories — whichever reads
more naturally. Each may have 1–3 acceptance criteria as sub-bullets
when the success condition isn't obvious. For large scopes, top-level
entries are epics (S1–S10), each with at most 10 sub-stories
(S3.1, S3.2, ...); expand only where needed.>

## Domain model
<A Mermaid diagram (erDiagram or classDiagram) of the core entities and
their relationships, plus short notes on anything the diagram can't say:
invariants, lifecycle, ownership. Skip the diagram entirely if the
feature has fewer than ~3 entities — a sentence is enough.>

## Non-goals
<What this feature deliberately does not do. Often the most
misunderstanding-preventing section in the file.>
```

### level-1.md template

```markdown
# <Feature name> — Level 1 Plan

## Plan
1. **<Item title>** — <1–3 sentences.> `serves: S2, S5` `[expanded: L2 | not expanded]`
2. ...

## Open questions
<Anything deliberately deferred.>
```

The `serves:` tag ties each item to the stories (or epics) it exists for. It makes traceability checkable in both directions: an item with no tag is either scope creep or evidence of a missing story — say which, and fix it. A story no item serves means the plan is incomplete. Deeper-level items inherit their parent's stories and only carry their own tag when it differs.

### level-N.md template (N ≥ 2)

```markdown
# <Feature name> — Level N Plan

## 3. <Parent item title>
### 3.1 <Sub-item title> `[expanded: L3 | not expanded]`
<Detail appropriate to this level.>
### 3.2 ...

## 5. <Another parent item title>
...
```

Only parents that have actually been expanded appear in a level file. Every item at every level carries an expansion marker, so opening any file shows at a glance how far planning has progressed below it.

## The workflow

### Phase 1 — Capture the pitch

Ask for (or take from the conversation) a one-to-few-sentence description of what is being built. Resist the urge to expand it. If the user gives you three paragraphs, distill it back to a few sentences and confirm the distillation — the pitch is the anchor everything else hangs from.

### Phase 2 — Short discussion: approach and assumptions

Ask **at most 5 questions**, then stop. The budget is deliberate: it forces you to spend questions on things that change the shape of the spec and plan (target users, build-vs-integrate, hard constraints, what's explicitly out of scope, the riskiest unknown) rather than details that belong deep in the levels. Before asking anything, check the conversation and the repo — questions whose answers are already visible waste the budget. Fewer than 5 is fine; one sharp question beats five generic ones.

State your remaining assumptions explicitly as a short list and get a nod before writing the spec — the pitch and the settled assumptions become the opening sections of spec.md. An assumption the user corrects now is worth ten corrected at level 3.

### Phase 3 — Spec: what is being built

Before planning *how*, write down *what*. This is where misunderstandings die cheaply: a wrong entity relationship caught in spec.md costs one diagram edit; caught at level 3 it costs a replan of every level above it.

Write spec.md with:

- **Stories** — at most 10 top-level entries, covering who needs what and why. Prefer job stories ("When ..., I want to ..., so I can ...") for technical and B2B features where the triggering situation matters more than a persona; classic user stories are fine when actors are the natural frame. Add acceptance criteria only where success isn't obvious from the story itself. When the scope is bigger than ten stories can honestly cover — a product, a large subsystem — the same 10-per-parent rule applies as everywhere else: top-level entries become epics (numbered `S1`–`S10`), each expandable into at most 10 stories (`S3.1`, `S3.2`, ...). Expand only the epics that need it; a flat list of ten stories remains the normal case for a feature.
- **Domain model** — the core entities and their relationships as a Mermaid `erDiagram` or `classDiagram`. Mermaid because it lives in the markdown, diffs in git, and renders on GitHub and in editors. Note invariants and lifecycle rules the diagram can't express as bullets beneath it.
- **Non-goals** — explicit exclusions. Most planning misunderstandings are someone assuming a thing is in scope that never was.

Scale to the feature: a small utility might have three stories and no diagram; a new subsystem deserves the full treatment. When the feature touches existing code, derive the domain model from the real types in the repo, extended with the new entities — don't invent a parallel vocabulary.

Review-gate the spec exactly like the plans: present it, take edits, and don't write level-1.md until the user agrees it describes the right thing. Level 1 then answers "how do we build *this*?" — its items should be traceable back to the stories they serve, and if an L1 item serves no story, either a story is missing or the item is scope creep.

### Phase 4 — Level 1 plan

Write level-1.md: **at most 10 items**. If the feature honestly needs more than 10, that is a sign the pitch covers two features — say so and suggest splitting rather than cramming.

Order items by dependency where a natural order exists. Keep each item at whatever altitude fits the project — for a small feature, concrete technical detail in L1 is fine; for a large one, stay at milestones and components.

### Phase 5 — Review loop

Present the plan and ask for reactions. Apply the user's edits — reorder, merge, split, reword, add, remove — and re-present until they're satisfied. Don't defend the plan; it's theirs. Do push back once, briefly, if an edit hides a real risk, then defer.

Do not descend to level 2 until the user says the L1 plan is done. This gate exists because every hour of L2+ work built on a wrong L1 item is wasted.

### Phase 6 — Descend, item by item

Ask which item to expand first (or propose the riskiest/most load-bearing one). Expand it one level at a time into the appropriate level file, then give the user a chance to react before expanding further — the review loop from Phase 5 applies at every level, just lighter-weight.

At each expansion, actively look at the code the plan touches. Grep for the real module names, read the real types. A plan that invents function names for modules that already exist is worse than no plan.

Apply the stopping rule per item. When proposing to go past level 4, justify it in one sentence and let the user decide.

### Phase 7 — Upward propagation

When work at level N reveals that something at level N−1 (or higher) is wrong or incomplete — a discovery in the code, a changed decision, a merged or split item — **stop descending and fix upward first**:

1. Edit the higher-level file to reflect the new understanding.
2. Check whether the change ripples further up; repeat until a level is unaffected. **spec.md is the top of the chain**: if the discovery changes what is being built — an entity, a relationship, a story, a non-goal — the spec gets edited too, and a spec change warrants an explicit heads-up to the user, since it means the earlier shared understanding was wrong.
3. Skim sibling items at the corrected level for contamination by the old assumption.
4. Tell the user what changed and why in one or two sentences.
5. Resume descending.

Never leave levels contradicting each other "to clean up later" — the whole value of the plan tree is that any level can be trusted as an accurate summary of the level below.

### Compressing the workflow for small features

The gates are sacred; the ceremony is not. For a small, well-understood feature it is legitimate — and better — to compress: present a mini-spec (a few stories, non-goals, maybe no diagram) and the L1 plan together in one message, take one round of review, and start descending. What may never be skipped: the user approves the *what* before you elaborate the *how*, and approves each level before you build on it. If mid-compression the feature turns out bigger than it looked, fall back to the full phase sequence and say so.

## Resuming an existing plan

When asked to continue planning (or when you find a `plans/<slug>/` directory relevant to the task), read spec.md and level-1.md first, then only the level files for the items being worked on. Confirm with the user where they left off before expanding anything.

## Tone throughout

Keep planning conversation terse. Plans are for scanning: short items, concrete nouns, and real file and function names as soon as the plan starts touching real code. If the user starts asking you to implement mid-planning, note which plan item the code belongs to, and if implementation reveals plan errors, Phase 7 applies.
