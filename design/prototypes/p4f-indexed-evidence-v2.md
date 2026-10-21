# P4f follow-up — bounded-memory, indexed actor evidence (PR #86)

**Status:** Implemented on PR #86 with focused SQLite/transport tests and
scoped ready-for-review world/handler acceptance. This is an external-handler
optimization. It introduces **no** Evennia migration, new command, new
physical authority, model decision or hidden-fact channel.

## Why PR #85 was insufficient

PR #85 removed repeated world pagination during ordinary processing, but
each supervisor still retained every addressed event as a Python dictionary.
Pump safety, hails, captain tickets and investigations use historical
receipt identities, so deleting old events by age or retaining only N recent
messages would break source verification and restarted work.

## Accepted ownership and storage

1. **Evennia** owns the canonical PostgreSQL CrewEvent journal, event IDs,
   commit-ordered sequences, recipient authentication and operation receipts.
2. **The handler** creates one new SQLite file per actor per *process* in a
   private temporary directory. Rows are inserted only from that actor's
   addressed, version-2 oxinbox pages after validation.
3. **The SQLite index is a disposable read cache, never autonomous evidence.**
   A new process does not trust a previous process's local copy. It rereads
   world history from cursor zero before using old proof; subsequent reads
   continue at the indexed high-water mark.
4. **Legacy evidence** is exposed as a read-only, stable-sequence EvidenceView.
   Iteration is lazy and ordered, while get(event_id), latest(kind), and
   select(kind, data) use SQLite indexes instead of materializing a voyage.
   Identity is actor-scoped even when two characters saw related ship events.
5. **Private cognition** still owns beliefs, interpretations and memory
   revisions. The index is neither a native Concordia memory nor a
   substitute for a brain or its checkpoint.

## Transaction and crash invariants

- A single actor's read is serialized on its authenticated socket.
- Each world page has <=128 addressed events; received count, sequence
  ordering, version-2 continuation and cursor progress are checked *before*
  insertion. All pages of **one read** commit or roll back as a batch.
- Before the supervisor cursor may advance, the newly indexed records
  are observed by that actor's private brain and its checkpoint is saved.
  A brain/ledger checkpoint failure restores the prior in-memory cursor;
  the indexed rows remain replayable in that process and world rows remain
  replayable on a fresh process.
- Independent private agenda and epistemic cursors can lag the parent.
  Their indexed delta begins at the minimum private cursor; each consumer
  only admits events beyond its own stored last sequence. Historical
  checkpoint upgrades still examine older addressed source events.
- Exact receipt IDs, sender IDs, event kinds and case/ticket data must
  still agree with the calling workflow. Merely finding an event in a
  local index is never authorization for an unreceipted world effect.
- The separate asynchronous wake-up frame staging deque has 256 entries,
  with durable event truth still read through oxinbox.

## Lookup map

| Consumer | Historical evidence needed | Indexed access |
| --- | --- | --- |
| Pump/radio and reviewer | Original alarm, request/approval, resolution source event | Exact event_id; alarm_id + kind |
| Watch handover | Due posting, offer and confirmed transition | Latest kind; exact work source |
| Player hail | Delivered hail and acknowledged answer | kind + hail_id/mode |
| Supply | Original personal order/delivery event | kind + order_id |
| Captain | Open ticket, current order, review/response and evidence | kind + ticket_id/order_id; no foreign private facts |
| Investigations and rounds | Notice, case testimony, first-person sample/report | kind + case_id or exact event_id |
| Agenda/epistemics | Only unseen addressed events, including restart backfill | seq > independently checkpointed cursor |

## Verified scope and limits

Focused tests cover 8,001 interleaved input records with 6,001 genuinely
addressed events streamed in <=128-item pages without returning a full
Python list; 12,800 indexed records with typed and exact lookup; foreign
recipient refusal; an interrupted multi-page batch; immutable views; and
private consumer checkpoint backfill. Applicable CI integration gates
exercise the real authenticated Evennia transport and restart protocol.

This bounds **per-process Python historical event retention and per-actor
SQLite page cache** (configured at 512 KiB); it does **not** bound on-disk
index size, startup world-pagination cost, Python objects temporarily held
by an unrelated caller that explicitly requests a list, Concordia-private
memories, or JSON checkpoint size. The world's canonical journal continues
to grow. Signed world generations / safe across-restart index reuse and
selective checkpoint persistence are distinct future projects.
