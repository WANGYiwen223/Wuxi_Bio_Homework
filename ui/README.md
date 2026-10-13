# Demo UI

Employee chat, explicit permission and fix feedback, and a separate reviewer
approval/handoff view. Backend sessions establish identities and roles.

`app.js` polls case activity during a running turn, updates step status and sources,
and exposes metadata in a collapsed developer inspector. Assistant citations link
to numbered source cards; internal record IDs appear only in diagnostics/reviewer
details. The page uses text nodes for untrusted output. See
`docs/INTERACTION_DESIGN.md` for the interaction contract and known limits.
