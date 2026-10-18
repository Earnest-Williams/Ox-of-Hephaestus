# ADR 0007 — Event-driven three-crew P2 watch supervision

**Status:** Prototype experiment, 2026-10-18.

## Decision

Before introducing autonomous duties inside live Evennia, implement a
separate stdlib-only deterministic mock world for the three-crew
watch-handover acceptance scenario.

The **world** owns the mock game clock, station locations, duty roster,
authorised observations, communications, and duty-acceptance effects.
The **handler** owns one isolated event memory and policy per character,
an event-triggered supervisor, duty queue, and pending request identities.

Policies never inspect the world audit log or another agent's memory.
A world observation has a recipient and source event ID. Optional typed
`kind` and `data` fields have been appended to WorldObservation, preserving
backward compatibility with existing Concordia/Evennia prototype callers.

The supervisor drains recipient-scoped observations and issues one duty
wake at 07:55. There is no per-agent polling, model call, or narrating
Game Master. Policies propose a report or acknowledgement; the mock
world alone validates and commits each effect.

World requests are idempotent by request ID. On dropped acknowledgments,
the handler stores an **unknown** outcome and reconciles via the world's
recorded receipt. It does not replay actions after restart. A JSON
checkpoint preserves handler-owned memories, seen events, outstanding
requests, agenda and wake counters. The world remains live in this test;
durable world restart is future work.

## Scope

This implements the **watch-handover portion of P2**, not the entire P2
coolant incident and emergent-cooperation gate. The crew do not yet travel
using Evennia sessions, run automatically in a persistent external daemon,
or coordinate a full pump repair. Known duties produce narrow deterministic
social actions; this is not a general conversational agent.

The previous in-process Evennia GOAP/Gemini repair experiments remain valid.
P3 introduces the ordinary-client connection that will let the supervisor
dispatch such work to the actual persistent ship without consulting its
database or taking authority over mechanical outcomes.

Do not equate a passing deterministic mock with a persistent autonomous
spaceship or general multi-agent intelligence.
