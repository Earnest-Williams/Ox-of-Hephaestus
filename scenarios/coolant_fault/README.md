# Scenario 1 — Cooperative cooling-pump fault (executable P2 mock)

**Status:** Implemented as a deterministic, zero-model, three-crew mock.
A standalone GitHub Actions trial and regression tests exercise all
equipment transitions and recipient-specific communication. This is NOT
a persistent multi-character Evennia server; live network transport is P3.

## World and authority

The mock ship has a Bridge, Connecting Passage and Engineering. Ari Sen is
the on-duty engineer in Engineering, Iona Vek is the chief engineer also
present there, and Lin Sato is the Bridge officer. The fixture world is the
only authority for time, crew locations, permissions, the cooling pump's
physical state, and communications deliveries.

The mechanical sequence matches our real Evennia P-01 proof of concept:
`normal -> low_pressure -> isolated -> repaired -> normal`. The scenario
adds one world-enforced **chief safety release** after physical repair and
before commissioning. This is a mock-only extra interlock, not yet an
Evennia pump mechanic. The character must inspect P-01 locally; an
individual's planned GOAP effects alone do not change machinery.

## Example event sequence (03:00 game time)

1. The world faults P-01. **Only Lin** receives the bridge alarm initially.
2. Lin sends a valid radio alert to the on-duty engineer Ari.
3. Ari inspects P-01 locally. His actual readout reports low pressure.
4. Ari searches the reusable symbolic GOAP domain for the minimum-cost
   physical remedy and issues **isolate** then **repair** commands.
5. Ari requests release. Only **Iona** receives that engineering request;
   she cannot approve it until she inspects the actual repaired pump.
6. Iona inspects and authorises commissioning through a separate,
   validated world action. A notification reaches Ari.
7. Ari commissions and **reinspects** P-01, verifying normal pressure.
8. Ari reports the resolved incident to Lin and Iona. Neither recipient
   is given a copy of the engineer's entire private memory.

An operator-only log exposes the actual world transitions, character
revisions and separately delivered observations. This is not an agent input.

### Failure injections and tests

- A second, *urgent* safety reading arrives **after Ari has proposed**
  isolation but before the request reaches the world. His revision changes;
  the supervisor rejects the stale proposal. A new on-site inspection is
  required even at the world permission boundary before operations resume.
- The world commits **isolation** while its acknowledgement is lost.
  The handler snapshots independent private memories and the pending
  request ID, restarts against the still-live world, queries its receipt,
  and continues. **No second isolation operation occurs.**
- Invalid remote operations, unauthorized chief releases, forged completion,
  and approvals without current first-hand inspection are all rejected.

## Run

From repository root, Python 3.12+:

```bash
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_coolant_*.py' -v
python -m ox_ai.scenarios.coolant_fault
```

Or, after this PR merges, open **Actions > Ox three-crew coolant incident >
Run workflow** on `main`. The artifact `ox-three-crew-coolant-incident`
contains a JSON transcript of independent memories, pump event history,
world events, GOAP searches, expansion counts, and model-call accounting.
No Gemini key, model download, Concordia dependency or game server is used.

## Honest limitations

All domain operators, duties and escalation requirements are authored.
There is a real state-space GOAP search for technical action selection,
plus deterministic event-specific policies for communication. This does
not establish emergent negotiation, arbitrary fault diagnosis, or three
native Concordia entities interacting. Game time is advanced directly;
a resident handler talking to real Evennia sessions has not been built.

The next integration milestone is P3: normal authenticated Evennia
character connections, per-character observations, action IDs/reconnect
reconciliation, and eventually the read-only observatory.
