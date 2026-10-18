# P4b — event-driven watch service and two real cooling incidents

**Status: implemented, tested and merged as
[PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14).**
Nine focused workflows passed on the final PR commit and on
the merge into `main`. [Implementation matrix](../STATUS.md).

## Runtime now in the repository

The external handler's normal entry point is:

~~~sh
# From the repository root after installing dependencies and
# provisioning nonprivileged accounts in a LOCAL development world:
python -m ox_ai.runtime.watch_service serve
~~~

`ox_ai.runtime.watch_service.CrewWatchSupervisor` maintains three
independent character sessions, per-entity Concordia snapshots
and a durable handler phase record under `.ox-state/`.
When idle, it suspends on authenticated character events
rather than polling models on game ticks.

The world-owned `world.live_clock.ShipDutyClock` is an Evennia
**persistent Script**; it fires due-watch observations at an
armed game timestamp. It never invokes Concordia or claims
a social outcome. This supplants the original P3
“incident ended, therefore it is 07:55” shortcut for
the new P4b integration scenario.

## First watch, second watch

- The first P-01 fault arrives on the Bridge, is relayed
  to Ari on engineering watch, and is repaired after Iona's
  independent safety inspection.
- The real duty Script enables a game-validated watch
  handover to Iona.
- A second P-01 fault is injected in the same world.
  Iona, not Ari, is the authorized repairer. **Ari**
  is now the separately assigned safety reviewer.
  Iona cannot approve her own commissioning.
- After a physical isolation has been committed, the test
  deliberately loses its ACK and stops the **external
  handler**. A new process reconnects as Iona, queries
  the existing receipt ID and finishes safely.
- An independent database verdict confirms both full pump
  event sequences, Iona's actor identity for second-watch
  operations, appropriate review and **no duplicate isolation**.

The executable evidence is
[`ox-p4b-autonomy.yml`](../../.github/workflows/ox-p4b-autonomy.yml).
`begin`/`resume` are dedicated two-process failure-injection
modes; normal ongoing operation uses `serve` and retains
successful action acknowledgments.

## What this does not establish

- `serve` is implemented and can remain connected, but
  no managed deployment, long-duration soak test or
  production uptime guarantee has been delivered.
- CI uses native Concordia with a deterministic
  `MockModel`. It does not demonstrate arbitrary
  hosted-model three-party negotiation or diagnosis.
- Isolate/repair/commission have world-side durable
  receipts. Generic crash-safe continuation of **every**
  later non-idempotent social command remains future
  work. A handler must fail closed rather than blindly
  replaying an unconfirmed action.
- The ship still has only three compartments, three crew
  and one modelled piece of repairable machinery.
  Cargo/propulsion, skills-by-use and the browser
  observatory remain unimplemented. P5 was deliberately
  postponed.

See [getting started](../../INSTALL.md),
[handler operations](../../services/ai-handler/README.md)
and [world authority](../../ARCHITECTURE.md). The former
P2/P3 scenario documents are useful historical regression
cases, not alternative descriptions of the current runtime.
