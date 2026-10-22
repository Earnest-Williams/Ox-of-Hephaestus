# P4k — integrated forty-character operational recovery

## State

PR #95 merged the 40-archive attestation profile. That is not a live
forty-character restart. This PR adds a focused first gate for native
Concordia checkpoint recovery with forty distinct identities, rather than
repeating the SQLite archive benchmark.

## Current architecture constraints

- `CrewAgent` already accepts arbitrary distinct identities and native
  Concordia component graphs.
- `LiveCrewBrain` restricts roles to the named `ROLES` map.
- `CrewWatchSupervisor` provisions three hard-coded authenticated accounts.
- `FiveCrewSupervisor` adds two, optionally a captain, with fixed world
  provisioning and department procedures.
- Neither supervisor currently provides a real forty-character identity roster.
  The existing supervisor must not be described as forty-character-capable.

## Acceptance ladder

1. **Native cognition:** forty independent actual `CrewAgent` graphs, private
   addressed observations, atomic persistence, fresh-process native restores,
   stable identity, no replay duplicates, rejection of foreign observations,
   and no cross-character memory mixing. Covered by
   `test_forty_native_recovery.py`; install the pinned Concordia extra.
2. **World provisioning:** provision forty distinct Evennia characters and
   accounts in a disposable instance. Require each WebSocket session to
   authenticate and puppet exactly its own DBREF. Reject duplicate bodies.
3. **Continuity:** each character verifies its retained actor-private evidence
   against a freshly authenticated nonce-bound world journal certificate
   before local historical data can be used. A stale or corrupt index must
   fail closed without preventing unrelated characters from restarting.
4. **Interrupted actions:** restart between real world execution and handler
   acknowledgement. Reconcile the existing world receipt and retained
   obligation before any retry; demonstrate no duplicate physical mutation.
5. **Fleet operations:** resume forty independent character agendas and duty
   work, with controlled recovery scheduling, no omniscient state, no unbounded
   memory replay, and recorded per-character readiness distribution.

## Required measurements

Record native restore duration separately from authenticated login,
world-continuity verification, pending-action reconciliation and operational
readiness. Do not sum independently measured stage medians as a fabricated
end-to-end fleet time. Keep long-running 40-session acceptance manual until
a measured CI budget is established.

## Run the first gate

```sh
python -m unittest discover -s services/ai-handler/tests -p 'test_forty_native_recovery.py' -v
```

**Not yet established:** authenticated forty-session recovery, native
`LiveCrewBrain` role generalisation, world-provisioning for forty bodies,
and forty-character real work continuation. These are the next implementation
steps, not achievements claimed by this PR.
