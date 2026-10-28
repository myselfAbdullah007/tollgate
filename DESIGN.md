# Experience and interface design

## Navigation

A persistent sidebar names the user's tasks: Overview, Customers, Request logs, Plans & budgets, Model routing, API keys, Providers. Playground is separated under Build & test. Setup and documentation sit beside workspace settings. Workspace selection is always visible.

The overview answers four questions first: how much did we spend, how much traffic is passing, which customers are active, and how much sensitive input was protected? The chart and protection summary provide context. Customer budgets are sorted by highest utilization so the next action is visible.

## Interaction rules

- Keep the primary action next to its page title. Customer edit is in the row; details are linked from the customer name. Budget notifications link directly to the customer.
- Show used amount, limit, percentage bar, and tier together. Colors supplement text; tier labels and percentages remain explicit.
- Search supports customer names and external IDs. `/` focuses search. Request filters and pagination stay together. CSV export explicitly exports the current page.
- Keys are generated once and copied in a dedicated confirmation view. Revocation has an explanatory confirmation. Errors stay inside the form; successful saves refresh persisted data and show a dismissible status.
- Plans use plain fields and percentage thresholds. Routing uses a visible vertical ladder and left-to-right fallbacks, editable with model selectors.
- Playground shows input and output side by side, redaction preview below the input, and actual model/tier/cache response metadata beside the answer. Streaming can be stopped.
- Shared sessions are deployment-wide administrator identities. Workspace navigation does not claim to be per-tenant identity authorization.

## Visual system

Light neutral canvas, white bordered panels, restrained violet actions, green protection indicators, amber budget thresholds, muted red exhaustion/errors. DM Sans and Manrope are bundled locally. Charts use a violet area fill with labeled axes. Tables scroll within panels on narrow displays. Mobile uses an off-canvas sidebar; the document itself must not overflow horizontally.

## Accessibility and feedback

Visible focus states, labeled inputs, real buttons/links, focus-contained dialogs with Escape, status/error semantics, skip-to-content, minimum readable operational text, reduced-motion support. Table actions have descriptive accessible names. Automated functional checks do not substitute for an independent accessibility audit; WCAG certification is not claimed.
