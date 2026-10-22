# P4l — forty independent model-selected duty obligations through restart

**Scope:** Extend P4k's successful forty-character authenticated, native
Concordia and attested-journal restart to **forty world-authorised work
requests**, one from each distinct crew body.

## Procedure

1. Start an ordinary Evennia server after operator-only provisioning of forty
   distinct accounts, world bodies and individual duty posts. Each has one of
   four ordinary station roles and is physically placed at its own instrument.
   Start a genuine world-owned round window.
2. Open **forty ordinary authenticated WebSocket sessions** in a separate
   handler process and attest every actor's private world journal.
3. Each of forty native Concordia entities receives only their own addressed
   duty notice. The actor sends an ordinary local `inspect` command and
   observes its genuine station readout in private cognition.
4. Offer each entity **two options**: the typed `round_report` and a safe
   deferral. The configured mock model deterministically chooses the actual
   world-duty request. A `CrewAgent` creates its own durable `ActionRequest`,
   preserving the agent's independent pending-intent state.
5. Atomically persist the forty native Concordia checkpoints and the handler
   roster/work ledger **before any** report is submitted. Submit the forty
   typed intents through `DurableEvenniaPort.submit_work`. Validate world
   receipts, but deliberately **do not** record their acknowledgement in the
   durable private intent state.
6. Stop the handler and Evennia. An operator-only fixture checks all forty
   world receipts exist, appends one new private duty update per body and
   restarts Evennia. Start a wholly new handler process.
7. For all forty characters, reauthenticate, independently recompute/attest
   complete original recipient-private prefixes, replay only the delta,
   rehydrate native pending requests and invoke `reconcile_work` using the
   **unchanged IDs**. Never resend the original operations.
8. Verify each returned source `round_recorded` through the same character's
   authenticated `oxevent`, record the verified outcome in its own native
   agent, and persist that agent before advancing the corresponding durable
   handler work status. Check independent resumption remains retry-safe.
9. Stop the game and inspect the authoritative database: exactly forty
   successful distinct `WorkReceipt` rows, each paired with its own
   `round_recorded` addressed world event, plus forty opening and forty
   resumed duty observations. Record per-character readiness and phase times.

## Boundaries

The four station postings are a controlled, disposable acceptance scenario,
not claims that forty people are interchangeable engineers or that every
real voyage will assign every crew member exactly one round. The model selects
an attempt; only Evennia can permit and receipt it. No arbitrary evidence,
equipment state, duty cycle or physical operation is supplied by the AI
handler.

This is a **forty-decision, forty-durable-world-work recovery test**, not yet a
500-turn autonomous voyage, psychological continuity assessment or exhaustive
cross-department GOAP exercise. Production supervisors' existing three/five
person policies remain unchanged. This P4l increment also does not preload
the million-record P4f archive fixture; large-history end-to-end startup
should be measured separately after the integration path is settled.

The test is supplied in `.github/workflows/ox-p4k-fleet-recovery.yml`,
path-scoped and opt-in by workflow dispatch for subsequent runs.
