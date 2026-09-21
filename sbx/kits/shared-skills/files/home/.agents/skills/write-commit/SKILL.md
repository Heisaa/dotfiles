---
name: write-commit
description: Write or revise concise commit messages understandable to readers unfamiliar with the code, adding enough explanation for complex changes. Use when asked to draft or improve a commit message.
---

# Write Clear Commits

Make the change understandable at a glance to someone who has not read the code or conversation. Be much shorter than a PR description by default, but do not sacrifice clarity to meet a word limit.

## Ground the message

Inspect the diff being described and enough surrounding code to understand its purpose. Follow the user's requested scope; otherwise prefer staged changes when present. Do not silently mix staged and unrelated unstaged changes. Describe only the final changes supported by the diff, not the work history or abandoned approaches.

Writing a message does not authorize staging, committing, pushing, or publishing.

## Choose the right length

- For one straightforward change, use just a subject line.
- When the reason or effect is not obvious, add a blank line and one short paragraph explaining it.
- For a complex change, add enough context to explain the problem, the resulting behavior, and any important decision or tradeoff. Use a few short paragraphs or bullets when they are easier to scan. Avoid turning the body into a file-by-file inventory.
- Do not add a body merely to repeat the subject. Do not compress several important changes into a vague title just to stay short.

## Write plainly

Use an action-oriented subject naming the affected feature and concrete outcome, such as “Keep the space list on the current page after editing.” Aim for roughly 50–72 characters when practical; clarity takes priority over a rigid limit.

Explain user-visible behavior first. For internal changes, explain the practical effect on callers or maintainers. Avoid unexplained acronyms, internal function names as the main explanation, and vague phrases such as “improve handling” or “various fixes.”

Use the body to explain why the change matters and what now happens differently. Include implementation details only when they explain a meaningful decision or prevent misunderstanding. Omit conversational history, routine test output, Verification sections, and boilerplate.

Follow an explicitly required repository commit convention. Do not introduce Conventional Commit prefixes, issue numbers, or trailers without evidence that they are wanted or required.

## Deliver the message

Return the complete ready-to-copy commit message in one plain-text code block, without extra commentary unless requested. Use a blank line between subject and body; wrap prose around 72 characters where practical.

Unlike a PR description, do not add code links or line references by default: they clutter short messages and age poorly. If requested, provide a brief explanation with verified code references separately from the copyable message, unless the user asks to include them in the commit itself.

Before returning, check whether an unfamiliar reader can understand the purpose and effect without opening the diff, and remove any sentence that adds no useful meaning.
