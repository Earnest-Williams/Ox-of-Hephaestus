# P4k — integrated forty-character restart acceptance

**Verified:** 22 October 2026, [live GitHub Actions run 39700450262](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39700450262).
The test successfully booted the real Evennia world twice and ran two
independent handler processes; this is not another synthetic SQLite-only test.

## What passed

- Provisioned **40 separate ordinary account credentials and persistent
  Evennia crew bodies**. Each WebSocket independently authenticated and
  proved it was puppeting its intended DBREF with the existing identity nonce.
- Created 40 independent native Concordia `CrewAgent` graphs, each with
  separately checkpointed private state and distinct identity. Restoration
  rejected mismatched identities and private observations.
- Reused the actual `CrewWatchSupervisor.read_inbox` path: 40 persistent
  actor-scoped SQLite histories, full local prefix rehash, actor- and
  nonce-bound world `oxjournal` certificates, authenticated streaming inbox
  pagination, and immutable older event references.
- Restarted **both** the external handler and Evennia itself. Every actor
  accepted a second newly addressed duty observation after world restart,
  while keeping its original native memory and refusing replay duplicates.
- Committed one real `round_report` via an authenticated cargo character,
  after a local inspection and world-qualified duty window. The handler
  persisted its request ID **before** issuing `oxwork`, then simulated
  dropping the world-success acknowledgement.
- After restart, reconciled the unchanged request ID via
  `oxworkreceipt`, verified the original `round_recorded` source through
  the same authenticated character's `oxevent`, and never resubmitted work.
  A post-stop database check found **one and only one** successful
  `WorkReceipt` and matching world event.
- Used the same single-host supervisor lease as the three/five-crew paths
  to prohibit parallel local controllers over the same ship.

## Implemented paths

- `game/world/transport_probe.py`: disposable fleet identity/account
  provisioning and operator-only two-phase world fixture.
- `services/ai-handler/src/ox_ai/runtime/fleet_recovery.py`: strict
  forty-slot roster validation, private native brains and shared attested
  evidence recovery path.
- `services/ai-handler/src/ox_ai/scenarios/p4k_fleet_recovery.py`:
  two-process, two-world-boot authenticated acceptance.
- `services/ai-handler/tests/test_forty_native_recovery.py` and
  `test_p4k_fleet_recovery.py`: model-backed native-state and pure
  identity-guard regression coverage.
- `.github/workflows/ox-p4k-fleet-recovery.yml`: path-scoped dedicated
  integration CI, not part of unrelated PR gates.

## Explicit limitations

This establishes **40-character authenticated cognitive/evidence restart**,
not 40 autonomous agents working simultaneously. The production
`CrewWatchSupervisor` remains specialized for three people and
`FiveCrewSupervisor` for five/six. P4k has a separate forty-body acceptance
controller that reuses the existing authoritative evidence path, but does
not invoke the specialized legacy GOAP duty policy.

The current P4k world-work recovery covers **one** real cargo report to
establish receipt correctness across process boundaries. It does not yet
exercise forty separate pending requests, independent task agendas,
forty simultaneous model decisions, or long-run autonomous duty dispatch.
The synthetic 1.6-million-event P4f benchmark and P4k live test are
different measurements: P4k does **not** preload those enormous archives,
so its startup timing must not be interpreted as a 1.6M-event live boot.

## Next acceptance priority

Extend the 40-session test to **forty distinct model-selected world-duty
requests**, each first grounded in genuine local inspection and permitted by
the world, with a persisted request ID. Drop or interrupt selected
acknowledgements, restart the handler, reconcile every pending receipt and
prove there were no duplicate world effects. Retain independently dated
and interpreted private memories through longer interrupted duty sequences,
then load-test real concurrent active cognition, yielding and dispatch.

Do not broaden Evennia ownership or relax world permission checking.
