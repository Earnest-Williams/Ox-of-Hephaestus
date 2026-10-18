# G2c — world-owned capability discovery (stage 1)

This incremental world protocol reports **only the local capabilities of the
ordinary authenticated character invoking it**. The first slice adds
`oxcapabilities <nonce>`, with a typed version 1 JSON response delivered over
Evennia OOB `ox_capabilities`.

Each response contains: protocol version, a fresh caller-supplied 128-bit
challenge (for matching only), the **server-derived actor dbref**, current ship
room identity/name, locally traversable ship exits (real Evennia exit dbrefs,
commands and adjacent destinations), and installed local fixtures with
currently eligible operation labels. No remote equipment, global topology,
private thoughts, foreign inbox, or handler-supplied role is read.

Exit discovery checks world exit traverse locks. Movement is still performed
by normal stock Evennia exit commands, never through an AI move/teleport API.
Equipment eligibility consults the authoritative fixture's role, current
condition, local presence, inspection and resource preconditions. An
advertised operation is **not a grant**: a changed world or expired
observation means the actual command/WorkReceipt can be refused again.

The default client must verify nonce and authenticated actor dbref on every
response, validate the strict versioned schema, and refresh before each
traversal. It must never infer remote physical authority from an observed
room, role, or hypothetical GOAP effect. Navigation and planning are
implemented in a following change, using locally learned edges only.

Tests cover real seven-room world topology, nonlocal fixture exclusion,
role-restricted operations, a newly applied exit lock, nonce validation,
command output and inspection-state changes. This command does not create
AI roles, grant movement permissions, or mutate world data.
