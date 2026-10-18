# P3b — Durable external GOAP

Evennia now owns an immutable, actor-bound receipt for every identified
physical command. The ordinary in-world oxaction and oxreceipt commands
use the same engineering permissions, location checks, and machine state
transitions as player commands. A durable action and its receipt are written
in one database transaction. The AI handler accepts only typed ox_receipt
OOB frames; spoken claims or plain room text cannot fake success.

A live, external, zero-inference GOAP engineer inspects the real pump,
computes a three-operation repair plan and isolates P-01. Its receipt is
deliberately discarded and its pending request checkpointed. A separate
handler process logs in as the same character, reconciles its receipt,
observes the actual machine state, replans and finishes the repair. CI
independently verifies an exact one-time physical isolation in persisted
SQLite and denies foreign receipt access. This is not yet multi-agent P3c.
