# G5-a: reproducible adversarial voyage and concurrency gate

**Scope:** deliberately bounded pre-G4 reliability testing. No new crew
powers, world simulation tick rates, gameplay mechanics, or hosted models.

## Three independent evidence layers

1. **World voyage:** `world.tests.test_adversarial_voyage` creates three
   consecutive P-01/C-01/A-01 incidents from operator-authored initial conditions,
   shuffles legally independent work stages using seed `20261019`, forces
   world-refused out-of-order operations, and verifies those refusal receipts
   cannot become successes when replayed later. A real post-commit incident
   repair, world-owned watch transfer, real human hails and cross-actor
   work-receipt privacy must hold. A database rollback before commit must
   leave neither world event nor work receipt. A second deterministic seed
   `0xF731` interleaves 180 addressed event writes and injected rollbacks,
   then verifies strict private page reconstruction past 128 records.
2. **Handler crash ordering:** `test_adversarial_ledger.py` uses seeds
   `7`, `57`, and `20261019` across 24 work stages each, several crew
   identities and randomly selected pre-send/post-commit/post-ack failures.
   A recovery loads only the last saved checkpoint, reconciles original IDs
   and never duplicates world effects. Fake transport deliberately includes
   a "world committed, receipt packet lost" case and permanently refused work.
   These are pure durable-protocol checks, **not** evidence that a fake port
   enforces Evennia's real authorization.
3. **Direct world-command rollback:** `test_adversarial_transactions.py`
   forces a failure in the second addressed notice of a handover, safety
   approval and incident resolution, plus failure of the initial release
   request and direct P-01/A-01 fault alarm. Ordinary character commands
   must be transactionally safe even without the global `oxwork` wrapper.
   The world locks P-01 then the roster before reading shared mutable duty
   fields. Compartment messages announce changes only after transaction
   commit, preventing ghost evidence from rolled-back actions.
4. **Independent PostgreSQL contention:** existing guarded
   `python -m world.postgres_contention` now invokes the G5 race probe on
   the same disposable PostgreSQL database with separate DB connections.
   It races hails from different senders, duplicate requests from one
   sender, duplicated replies from a crew member, and two simultaneous
   world-clock tick executions. Expected outcomes: distinct IDs, at most
   one pending hail per sender/recipient, one actual player reply, one
   watch deadline observed by each addressed crew member. Direct hail
   mutations lock the pump's world row *before* reading/modifying Evennia
   Attributes; the duty Script similarly locks the roster row.

## Reproduction

```text
cd game
python -m world.test_runner world.tests.test_adversarial_voyage --verbosity=2

# from repository root
python -m unittest discover -s services/ai-handler/tests -p 'test_adversarial_ledger.py' -v

# isolated Postgres ONLY with the exact disposable environment of
# .github/workflows/ox-g1-postgres-contention.yml:
cd game
python -m world.postgres_contention
```

The G5 workflow runs the first two suites. The pre-existing G1 PostgreSQL
workflow remains independently responsible for the third. All tests must
complete on the same final PR SHA. A CI pass on a preceding SHA is insufficient.

## What this gate cannot claim

- Three manually seeded failures are not autonomous environmental wear,
  cargo commerce or a true multi-month continuous voyage.
- Seeded interleavings are deterministic schedules, not exhaustive
  exploration of every production thread/event ordering.
- The fake handler world validates ID durability but cannot prove hosted-model
  behavior or world permission enforcement.
- Multi-host controllers remain unfenced. Event-journal full rescans and
  unbounded historical task ledgers need future endurance/compaction work.
- Existing authenticated real-server trials remain separate and mandatory.
  Zero model calls while idle remains an invariant of the actual supervisor.
- No generalized skill-by-use, fleet economy or recruitment was introduced.

## Failure policy

Any seed/ordering that violates an invariant must fail loudly and print its
seed, stage and actor identity. Fix the world/handler contract and add a stable
regression rather than filtering the seed or silently permitting a retry
with a new work ID. Preserve immutable historical receipts and the private
character/world epistemic boundary.
