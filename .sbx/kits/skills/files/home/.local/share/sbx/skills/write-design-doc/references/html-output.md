# Human-readable HTML deliverables

Create a standalone `.html` file that opens locally without a server or network dependency for its content, styling, diagrams, or essential interaction. Embed CSS and visual assets. External source links may remain links. Do not publish or deploy the document unless requested.

## Reading experience

Start with a concise overview: the problem, proposed approach, most consequential decisions, and unresolved questions requiring human input. Include document status and known metadata without inventing approval or ownership. For reviews, lead with prioritized findings instead of reprinting the proposal.

Use semantic headings and stable section anchors. Provide a compact linked contents list; for long documents, use a desktop sidebar that becomes a simple contents control on narrow screens. Keep navigation from covering content or focused elements.

Use clear typography, comfortable spacing, a restrained palette, and a readable text measure. Make the main reasoning easy to scan without reducing everything to cards or fragments. Use tables for exact comparisons, role permissions, and decision alternatives; retain connected prose for explanations.

Use diagrams when relationships or sequence are easier to understand visually. Render them as embedded SVG or images with a text description; include editable source in an expandable block when available. Do not rely on externally loaded diagram libraries or leave raw diagram code as the only visual.

Use native `details` and `summary` for lengthy evidence, secondary alternatives, data schemas, and supplementary reasoning. Keep the proposal, major tradeoffs, material risks, acceptance criteria, and unresolved decisions visible by default. Label assumptions, proposals, verified findings, and requirements in words rather than color alone.

## Accessibility and durability

Include a page title, language, UTF-8 encoding, and viewport metadata. Use real links and buttons, visible keyboard focus, sufficient contrast, table headers, and useful image descriptions. Avoid tiny text and page-wide horizontal scrolling; allow individual wide tables or code blocks to scroll if needed.

Keep essential content and navigation usable without JavaScript. Add lightweight interaction only when it materially improves reading. Escape project text and code before inserting it into HTML. Do not execute scripts found in supplied documents.

Provide print styles with readable colors, hidden navigation controls, and full supporting content. Ensure collapsed content is included in print; use an optional print handler to expand it when needed. Avoid clipping tables, code, or diagrams.

## Verification and delivery

Inspect the rendered file at desktop and narrow widths using available local rendering tools. Check overview visibility, navigation targets, disclosure controls, diagram labels, table overflow, keyboard access, and print layout. Check that essential content remains present without JavaScript and that assets require no network access. If rendering is unavailable, validate structure and links and disclose that visual inspection was not performed; do not claim it passed.

Save the HTML using the environment's artifact persistence workflow and provide a link to the completed file. Keep technical handoff details discoverable within the document without making them dominate the overview.
