# ADR 0006 - Zero-inference GOAP engineer and shared pump test

**Status:** Accepted prototype experiment (2026-10-18); GOAP repair and subsequent networked receipts verified.

> **Current implementation note:** This note records the first in-process GOAP experiment. The text describing external transport as unimplemented reflects that earlier phase; P3 and P4 have since implemented it.

## Purpose

Gemini 3.1 Flash-Lite autonomously restored P-01 in live GitHub Actions run
39088886933, requiring 10 bounded decisions. The next experiment should
demonstrate comparable *physical competence* without a model call, rather
than requiring an LLM to choose routine actions.

## Design

A reusable GOAP planner performs bounded, deterministic uniform-cost search
over STRIPS-like facts, action preconditions, add/delete effects and positive
costs. This is a genuine cost-based search, not an ordered repair script.

An independent GoapCrewAgent supplies a specific engineering domain:
known Bridge-Passage-Engineering routes, console and pump inspections, and
the causal requirements of isolate, repair, commission and verification.
This is authored equipment/procedural knowledge, NOT access to the live
world's hidden state. The controller has zero Concordia or LLM dependency.

The controller begins with an unknown pump condition. It uses its own
character-scoped room observation to plan an inspection. A telemetry
observation then supplies the actual condition. It plans a route, isolation,
repair, commissioning and verification using the same real Evennia command
dispatcher used by Gemini. The world is the only authority on action
success. After each attempted command, it reconciles its predicted effects
with actually delivered observations before proceeding.

A plan persists between actions as long as incoming observations confirm
expected effects. Conflicting evidence invalidates it and triggers a new
search. An unknown request outcome blocks retry rather than potentially
repeating a physical action. A plan's hypothetical state transition is
never itself used as proof of game-world effects.

The success condition requires both a witnessed successful repair by this
character and a final local normal-pressure reading. The existing harness
independently verifies Evennia's event journal and actor identity.

## Acceptance

- Pure Python tests for optimality, missing prerequisites, failed actions,
  finite search budget, knowledge scope, stale revision and unknown outcomes.
- Real Evennia test with the same physical pump, normal commands and
  independent outcome verifier as the Gemini test.
- Real Evennia test with a SECOND physical fault injected after commissioning
  but before final inspection; the character must notice it and replan.
- A GitHub Actions no-key manual experiment with full command transcript,
  planning search statistics and an append-only decision journal.
- Exactly zero inference requests for all GOAP tests.

## Deliberate limits

This is one engineered role on one known pump in a small mapped ship. It
does not invent new procedures, diagnose arbitrary equipment, schedule
dozens of crew, or model tools not present in the real game. The reusable
planner can select a tool-acquisition action when the domain models it,
which is tested with a synthetic action graph.

World observations are currently parsed from the trial's exact command
messages. Production requires typed, recipient-authorised observations
with provenance and freshness, not untrusted general prose. The physical
fixture and in-process local terminal are testing scaffolds; external
WorldPort transport and an asynchronous AI supervisor remain unimplemented.

The first PR does not claim GOAP outperforms Gemini. Compare actual action
counts, correctness, replanning and latency only after successful runs.


## Later results (2026-10-18)

The model-free GOAP benchmark remains a reusable deterministic control. [P3b](../prototypes/p3b-durable.md) used the same pump operations via actual authenticated Evennia WebSockets, adding durable world-owned request/receipt reconciliation. [P3c](../prototypes/p3c-live-crew.md) integrated the planner into a three-character incident. [P4a](../prototypes/p4a-live-cognition.md) and [P4b](../prototypes/p4b-autonomous-watch.md) preserved GOAP as authored equipment expertise under bounded Concordia decisions and a changed active watch. None of these milestones proves novel equipment discovery or generic planning for unmodeled machinery.
