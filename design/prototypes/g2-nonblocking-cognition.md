# G2b — nonblocking individual cognition and single-host supervisor lease

**Implementation target:** [PR #33](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/33). This is handler-only scheduling, with actual world receipts and rules unchanged.

## Ownership and safety

* Evennia still owns each world event, character identity, actual location, equipment precondition, duty roster and immutable consequential action receipt. The external handler never reads or writes the Evennia DB.
* The handler's event-loop-owned native Concordia mind remains mutable only on that loop. At a decision point, `CrewAgent.fork_for_inference()` constructs a **detached deep snapshot** of one character's native components and context; synchronous model inference runs only against that fork in a worker thread.
* A finished candidate is adopted by the live agent only when the expected observation revision and person/character binding still match. A newly received observation makes the proposal stale. Rejected, late, invalid or timed-out work never enters the live pending-request ledger or touches the world.
* Global inference semaphore caps parallel model requests (default 2), while an actor may have only one live or quarantined model request. Worker waiting, provider latency and decisions have a bounded wait (default 25 seconds). Provider errors are redacted. No model calls occur during idle time. Explicit configurable actor and global quotas refresh each 3600 wall seconds.
* A timed-out synchronous worker **cannot forcibly be killed** in Python. Its detached state is discarded, and the role remains quarantined until the worker exits. Provider transport timeouts are also required; this mechanism is fail-closed, not preemptive worker termination.

## Independent dispatch

The ordinary three- and five-person supervisors now call `await self.choose(role,...)` rather than blocking on native Concordia `act()` inside the event loop. Existing priority order for coolant/scrubber/cargo and actual physical work is deliberately unchanged. Multiple addressed hails are processed as independent role-scoped coroutines over distinct authenticated character sockets; one slow model cannot prevent another role's hail decision from progressing. Each hail still uses a world-owned receipt and crash-reconciled work ID. We do **not** concurrently mutate one actor's physical equipment or allow two consumers of the same socket.

## Supervisor process lease

`supervisor_lease.py` uses a single stable `.ox-state/supervisor.lock` POSIX advisory flock for **both** legacy and five-crew handlers. It is acquired before socket opening and released after closure, including exceptions. The lock inode is never unlinked; a crashed process releases its kernel lock. The file stores a diagnostic monotonic epoch and PID, but these are **not an Evennia-enforced distributed fencing token**. This is a single-host deployment guarantee only; cluster/multi-host operation is forbidden until the game authority verifies an epoch or equivalent fencing lease for each request.

## Environment configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OX_MAX_PARALLEL_COGNITION` | `2` | Concurrent model calls across the ship |
| `OX_COGNITION_TIMEOUT_SECONDS` | `25` | Maximum wait for a proposed decision |
| `OX_COGNITION_ACTOR_BUDGET` | `500` | Per-character starts per 3600 wall seconds |
| `OX_COGNITION_TOTAL_BUDGET` | `2500` | Shipwide starts per 3600 wall seconds |

These are inference admission controls and cannot override the world's role, permission or equipment safety checks.

## Evidence and limitations

The new [G2b CI](../../.github/workflows/ox-g2-nonblocking-cognition.yml) tests separate native Concordia minds, one deliberately blocked model vs a responsive second agent, receiving an observation while inference is in flight, stale rejection before adoption, same-actor exclusion, timeout quarantine, safe provider failure, quota reset, cross-character adoption refusal, and POSIX child-process lock contention/crash recovery. Existing live-world scenario workflows remain mandatory and test the changed handler paths.

This does not implement asynchronous world-action execution in parallel, world-enforced distributed fencing, arbitrary unsolicited event processing during every in-progress world procedure, or a continuously running inference process. Those are later capabilities and must not be claimed from this slice.