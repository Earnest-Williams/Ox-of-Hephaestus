# P4a — three native Concordia actors in real Evennia

**Status: implemented, tested and merged as
[PR #13](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/13).**
[Current feature matrix](../STATUS.md).

P3c proved a real networked three-crew cooling incident with
authored deterministic role policies. P4a built **three
independently instantiated native Concordia entities** whose
observations, memory, revisions, journal and checkpoints are
owned by their respective identities (Lin, Ari, Iona).

Each character receives only world-delivered private
`ox_event` packets and readouts genuinely returned to its
ordinary Evennia connection. Concordia selects among a
**finite set of offered actions**, including deferral;
unoffered or malformed decisions cannot become world
commands. Routine equipment work still uses deterministic
GOAP; physical success still requires world-owned receipts.
A delayed private event may legitimately have an earlier
game timestamp and is not rejected solely for arriving late.

## What the CI demonstrates

The real-server [`ox-p4a-concordia-crew.yml`](../../.github/workflows/ox-p4a-concordia-crew.yml)
runs three real clients and three native Concordia entities.
It demonstrates character-private memory, model invocation at
decision points, validated proposals, local inspection,
P-01 isolation/repair, independent release approval,
commissioning, closure and watch handover.

**Crucial test boundary:** CI uses Concordia's deterministic
`MockModel`, which selects expected offered options. This
establishes correct integration, **not** unscripted creative
cooperation or three actual Gemini reasoning processes.
An optional hosted-model trial requires
`OX_COGNITION_PROVIDER=gemini` and a privately supplied
`GEMINI_API_KEY`; refusals and timeouts fail closed.
A prior live Gemini success was for the bounded
*single-engineer* harness.

Actions without a suitable actor-visible acknowledgment
remain unknown, not successfully completed merely because
another character was seen acting. The model must never
see a second character's private journal.

**Next work is already implemented:** [P4b](p4b-autonomous-watch.md)
adds a world-owned duty Script, a repeat incident under a
different active engineer, an event-driven independent
runtime and verified isolation reconciliation across
handler processes. P5's browser observatory remains deferred.
