# P3b — durable world receipts for ordinary client actions

**Status: implemented, tested and merged as
[PR #11](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/11).**
The core operation and its receipt are world-owned, not a
language-model-generated statement.
[Current implementation](../STATUS.md).

## Mechanics

`CoolingPump.durable_action` records each identified physical
`isolate`, `repair` or `commission` operation and its immutable
actor-bound receipt inside one database transaction. The
ordinary in-world `oxaction` and `oxreceipt` commands perform
the same location, engineering-role and machine-state checks as
other players' commands; they grant no special AI authority.

The client-side `DurableEvenniaPort` accepts only typed
`ox_receipt` packets. Spoken reports and room messages cannot
forge physical success. Unknown outcomes remain unknown
until the correct world request ID is reconciled. A repeated
request ID cannot become a different actor's operation.

## Executed evidence

In the [`ox-p3-durable.yml`](../../.github/workflows/ox-p3-durable.yml)
test, a real external GOAP engineer inspects P-01, plans a
physical repair, isolates the real pump, and deliberately
loses its acknowledgment. A **different handler process**
then connects to the same character, queries the world
receipt and resumes without repeating isolation. CI
independently checks persistent SQLite event history and
denies another character access to the receipt.

This is the **physical operation** recovery contract, not
a guarantee that every later radio, approval or other
social command can be resumed after any arbitrary crash.

**Later milestones:** [P3c](p3c-live-crew.md) uses this port
with three real crew, while [P4b](p4b-autonomous-watch.md)
tests two incidents and a second-watch change. The
[wire contract](../../contracts/README.md) records the
current protocol limitations.
