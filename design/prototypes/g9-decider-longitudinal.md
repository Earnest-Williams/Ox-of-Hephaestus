# G9: Real longitudinal Decider personality in a six-crew Evennia voyage

**Scope:** Opt-in follow-through on the personality-weighted GOAP/Decider
integration merged in PR #100. The established G8 500-turn symbolic baseline
remains the default, unchanged. This experiment uses the already selected
**Decider 4B Q4_K_M** as the *only* model; there is no further model comparison.

## Why this experiment

The previous 48-decision authored dilemma assay showed reproducible
character-sensitive decisions. It could not establish whether such tendencies
survive actual changing world experience. G9 therefore reuses G8's
independently authenticated six-client Evennia experiment in which witnessed
conversations, private claims, social agreements and minor maintenance incidents
accumulate over sequential turns.

Every character starts with G8's fallible private relationship history and a
distinct fixed 12-dimensional CrewBlueprint. Subsequent actor knowledge is
admitted through already-verified room-local utterance deliveries and
world-backed social/work receipts. A character never reads another actor's
private memories. The game remains sole authority for physical state and
work receipts, while model proposals have no world-command capability.

On every seventh eligible social turn, the existing CharacterRouteController
freezes a personality-weighted GOAP/Decider route in the actor's durable
checkpoint *before* model inference. GOAP retains its cost-based social planner.
The alternative is a seven-choice Decider option-logit decision over currently
applicable, existing GOAP social operators. No unbounded language-generation
or arbitrary world command is accepted. A selected action is translated through
the same original G8 **say** path, with authenticated counterpart delivery and
per-listener witnessed memory admission. Social agreements still require exact
world receipts. Neither choices nor actual outcomes are scripted to produce a
particular relationship.

## Acceptance trial

A separate PR-gated
`.github/workflows/ox-g9-live-personality.yml` runs **205 actual six-client
turns** on disposable Evennia, with deliberate subprocess/staged resumes at
turns 34 and 137. A trusted operator injects one cargo fault and one atmosphere
fault only with the server stopped. Cargo and scrubber owners follow their
existing fully world-verified multi-stage procedures. The CI workflow uses
the existing pinned Decider GGUF and publisher tokenizer (CPU only, no hosted
API), tests the event/memory contracts, then archives a report and six
separate private brain snapshots.

`scenarios/g8_soap_opera/g9_evaluate.py` independently checks:
- all 205 unique turns were observed, not simply planned;
- correct real world fault operation sequences and source-event receipts;
- at least eight actor-bound route boundaries with actual model consultations;
- each consulted memory context refers only to earlier speech that the specific
  agent's authenticated client actually received;
- each selected social intent corresponds to a witnessed world conversation;
- independently restored cognition belongs to the same actor/profile and
  contains chronologically growing witnessed episodes; and
- the actual cargo/scrubber state is verified after stopping the game.

The route audit contains actor, turn, choice, baseline plan, world-observed
context reference IDs, consultation probability, and execution correspondence.
It does not export hidden prompts or invent Decider explanations.

**Limits:** This is a staged, bounded 205-turn behavioural experiment, not the
production supervisor, a statistical psychological evaluation, or an entire
500-turn Decider voyage. Some world-verified spoken lines use the G8 harness's
authenticated receipt-of-text check and **synthetic source keys**; those are
not misrepresented as server-signed world event IDs. True work receipts do
carry server-issued IDs. Re-entering after a checkpoint taken mid-conversation
fails closed pending explicit reconciliation: it will not replay possibly
already witnessed dialogue. The experiment's isolated dialogue proposals
are not production-safe durable physical work steps.

The result should be read for longitudinal actor differences, choice drift,
unexpected deviations, stable procedural work, actual remembered interactions,
and any order or prompt sensitivity. Do not assume success in advance, and do
not select only the traces that confirm an intended personality.
