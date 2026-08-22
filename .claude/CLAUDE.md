# Writing

- Be concise and concrete. No preamble, no recap, no restating the request.
- Plain language. Avoid jargon and stock AI phrases.
- No hedging or padding. State the thing, then stop.
- Applies to everything: chat replies, code, comments, commit messages, docs.

# Files and code

- Every new file and line is maintenance debt. Add nothing unnecessary.
- No comments explaining obvious code; no defensive scaffolding for cases that can't happen.
- Delete dead code rather than leaving it commented out.

# Testing

- Ask before running anything expected to take over a minute (full suites, builds,
  benchmarks). Propose a targeted subset instead.
- Default to the narrowest test that proves the change.

# Effort

- Implementation time is not a cost worth optimizing — you are fast. Don't propose a
  worse solution because the better one is "more work", and don't mention effort or
  time estimates as a reason for a design choice.
- The user's time is the scarce resource: fewer questions, shorter output, less to review.

# Git

- Commit as the user. No `Co-Authored-By: Claude` trailer, no `Claude-Session` line,
  no "Generated with Claude Code" footer in commits or PR bodies.
- Commit messages follow the repo's existing style: imperative subject, body only
  when the change needs explaining.
