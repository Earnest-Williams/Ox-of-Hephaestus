# Scenario 1 — deterministic P2 coordinated coolant fault

**Status:** Implemented **mock-world** regression with three
distinct crew memories, GOAP and zero language-model calls. This
file documents the historical P2 fixture, not the live P4 runtime.
[P3c real-client test](../../design/prototypes/p3c-live-crew.md)
and [P4b two-incident runtime](../../design/prototypes/p4b-autonomous-watch.md)
are implemented separately. [Current verification](../../design/STATUS.md).

## Mock world and physical rules

The deterministic P2 mock includes Bridge, Connecting Passage,
Engineering, one cooling pump, Lin on the Bridge, Ari on
engineering watch and Iona as independent chief. The mock world
owns clock, permissions, visibility, machine state and each
delivered communication.

The pump follows `normal → low_pressure → isolated → repaired
→ normal`. In P2, we *added a mock chief-release interlock*
before commissioning. **That interlock is no longer mock-only:**
the later real Evennia implementation requires independent
world-validated inspection and release, and P4b delegates review
to Ari when Iona holds active watch. This file's scenario remains
a deterministic historical reference.

## Authored event sequence (03:00 mock game time)

1. The world faults P-01. Initially only Lin receives the
   Bridge cooling alarm.
2. Lin legitimately radios Ari on engineering watch.
3. Ari inspects locally and reads the genuine mock low-pressure
   state, not a result inferred from GOAP.
4. GOAP searches known technical operators; the mock world
   confirms **isolate** and **repair**.
5. Ari requests a separate safety release. Only Iona receives
   that request, then she independently inspects the repaired pump.
6. Iona requests authorization; only the world records it and
   delivers approval to Ari.
7. Ari commissions and directly verifies restored normal
   pressure before reporting the outcome.
8. Lin and Iona learn the verified resolution without
   receiving Ari's private observation history.

All model-free decisions are deterministic, though the GOAP
planner performs real state-space search within an authored
technical domain.

## Negative tests and resilience

- An urgent safety recheck invalidates a previously prepared
  physical action. Agent revision and the mock's preconditions
  both prohibit acting on stale evidence.
- A real mock-world isolation happens but its ACK is withheld.
  Handler snapshots preserve the unknown request, and restore
  reconciles the original receipt without a second isolation.
- Remote/unauthorized operations, self-approval, forged
  completion and approval without current first-hand inspection
  do not alter the authoritative mock pump.

## Execute the historical test

~~~sh
# Repository root; Python 3.12+
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_coolant_*.py' -v
python -m ox_ai.scenarios.coolant_fault
~~~

GitHub **Actions → Ox three-crew coolant incident → Run workflow**
runs this credential-free mock suite and retains an operator-only
diagnostic artifact. There is no hosted model or game-server
process in **this** particular test.

## Scope and later implementation

The world and escalation policies were authored for one specific
fault; there is no free-form linguistic cooperation in P2. That
limitation remains even though P4 uses separate native Concordia
entities with finite choice menus.

The subsequent real-world stages did add the originally missing
capabilities: authenticated three-character Evennia transport,
world-side receipt IDs, actual safety signoff, an Evennia-owned
watch timer, independent post-handover reviewer and two-incident
handler restart testing. This P2 mock **by itself** does not
establish any of those real-server guarantees.
