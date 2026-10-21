# P4f follow-up — obligation-aware historical evidence selection

**Scope:** External handler-only, additive read-view refinement. No Evennia
migration, no modification of the authoritative CrewEvent journal, no loss of
historical proof, and no independent handler authorization.

## Legacy caller audit

- Captain dispatch repeatedly traversed *all* captain-addressed events to
  determine whether a ticket remained unresolved. The actor index now
  transactionally derives open/close state keyed by the world ticket ID.
  Per-ticket and per-order evidence uses the existing kind/field indexes.
- Hail dispatch previously constructed a voyage-length set of all answered
  hail IDs every wake-up, then visited all hail requests. The obligation
  state index yields only unresolved hail source events. Existing persisted
  interrupted work is separately reconciled by its exact original world
  source ID, including when an answer event has already closed the hail.
- Specialist recovery used linear event-ID scans. It now performs an exact
  indexed source lookup. Open alarms still retain their explicit disposition
  and original IDs in the private agenda.
- Investigation evidence and work receipts retain their full original event
  IDs and recipient-bound proof checks. No event has been evicted.

## Safety model

The `obligations` table is a **derived local read index**, not an Evennia
obligation ledger. It is built only from already-validated, authenticated
recipient-scoped `oxinbox` pages. Source and close transitions are committed
in the same SQLite transaction as the corresponding events. Closing an
unseen obligation does **not** fabricate an opening; repeated opening
identities are rejected. A pinned `EvidenceView` evaluates unresolved
state at its pinned upper sequence, not at the most recent archive cursor.

The world continues to own ticket status, successful work, receipts, and
physical resolution. Local absence of a new event is not proof that a world
obligation is complete. Actual operations still require independently
authenticated world acknowledgement.

## Deliberately not introduced

- **No local history eviction:** an active/closed state projection alone is
  insufficient to prove that no private character cognition, old checkpoint,
  or delayed work process needs an event.
- **No cold-start skipping:** a fresh handler continues to authenticate and
  rebuild addressed world history from cursor zero.
- **No unauthenticated exact lookup:** future world-provided exact-event
  recovery should require ordinary actor identity, a challenge-bound response,
  strict recipient filtering, and restart/rewind tests before being relied on.
- **No selective on-disk retention or world compaction:** the canonical
  journal is untouched.

## Next phase

Establish a world-owned indexed exact-event retrieval contract, prove caller
coverage and recipient isolation, then consider a bounded hot window with
separately tracked pinned references. A cutoff based only on age or event
count is forbidden while old referenced proofs remain necessary.
