---
name: write-pr
description: Write or revise PR titles and descriptions that are brief, understandable to readers unfamiliar with the code, and linked to the most important code changes. Use when drafting or improving a pull request message.
---

# Write Clear PRs

Help a reviewer understand the problem, the resulting behavior, and where to look without needing the conversation or detailed knowledge of the code. Keep the message inviting to read: enough context to understand the change, little enough to scan quickly.

## Ground the message

Inspect the actual diff and enough surrounding code to explain it accurately. Use the requested comparison or PR base; distinguish the full PR diff from uncommitted work. Describe the final change, not the work chronology or abandoned approaches. Do not invent causes, outcomes, line numbers, or checks.

Drafting a message does not authorize publishing it, opening a PR, committing, or pushing.

## Write for an unfamiliar reader

- Give the title a concrete action and affected feature or behavior. Prefer “Keep the space list on the current page after editing” over “Improve admin UX” or an internal function name.
- Start the body with one or two sentences explaining the problem and the result. Use a short before/after example when it makes the change easier to understand.
- Explain observable behavior before implementation. For internal changes, explain the practical effect on callers or maintainers.
- Use plain language. Avoid unexplained acronyms, internal identifiers, marketing language, and claims such as “more robust” without a concrete meaning.
- Group related changes by their purpose, not by filename. Omit incidental cleanup and details already obvious in the diff.
- Aim for roughly 100–200 words for an ordinary PR, less for a small change. This is a guide, not a quota; add detail only when needed to understand a meaningful tradeoff or limitation.
- Do not include a Verification section, testing checklist, or manual-check instructions unless explicitly requested. Still disclose a known material limitation briefly when omitting it would mislead the reviewer.

## Point to the important code

Include references to the most important changes, usually two to four for a typical PR and fewer for a small one. Choose locations that explain the behavior or a decision a reviewer should inspect, rather than listing every changed file.

- Place each link beside the explanation it supports. Use a compact “Key code” list only when inline links would clutter the prose; do not duplicate the explanation.
- Verify each path and line against the code being described.
- For a published PR, use repository links pinned to the relevant commit with line anchors. Never put local absolute filesystem links in a PR body.
- For a local draft whose changes are not yet available in a remote commit, use accurate repository-relative `path:line` references. In chat, clickable local file links may be supplied separately. Do not fabricate remote links or push solely to obtain them.

## Preferred shape

A concrete title, a short problem/result paragraph, and a few bullets for distinct behavior changes with their key code references. A small PR may need only the title and a paragraph with a link. Avoid empty headings, nested lists, and repeating the same facts in multiple sections.

Before returning the message, check: Can someone unfamiliar with the code explain what changes for them, understand why, and find the key implementation without reading a long description?
