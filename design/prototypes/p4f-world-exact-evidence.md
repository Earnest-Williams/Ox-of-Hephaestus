# P4f — authenticated exact world evidence (follow-up to PR #87)

**Status:** New standalone protocol and regression suite under review. This is
not historical retention, compacted history, or a second source of world
authority. Evennia still owns the complete immutable CrewEvent journal.

## Problem and legacy requirements

The actor-private SQLite index makes warm historical queries efficient, but
every new handler process must reconstruct all addressed history before its
normal legacy consumers can use the index. Captain tickets, deferred duties,
work receipts, hails, and investigation reports may reference arbitrarily
old original event identities. A fixed-age/window deletion is unsafe.

The first missing primitive is a direct, authenticated, **exact-event** read.
It must not produce another person's observations or mistake a missing event
for proof that a world obligation has been resolved.

## New ordinary character protocol

Request via the same authenticated/puppeted game session:

    oxevent <32-lowercase-hex-nonce> <world-event-id>

The ID accepts both legacy \`oxevt-0010\` and \`oxevt-v2-0010\` forms (at
most 64 characters). Evennia performs the indexed CrewEvent query using the
*actual command caller's dbref* in the database filter. There is no
recipient argument, admin path, or aggregate-history API.

Response: one \`ox_event_lookup\` OOB frame containing one serialized
JSON string with exactly:

- \`version\` = 1, \`nonce\` (exact requested challenge), \`actor_dbref\`
  (the authenticated caller), \`event_id\` (the exact requested ID);
- \`status\`: \`found\`, \`missing\`, or \`oversized\`;
- \`event\`: the complete original world event for \`found\`, otherwise
  \`null\`. The event includes exact \`event_id\`, \`sequence\`,
  \`recipient_dbref\`, \`sender_dbref\`, \`kind\`, \`data\`, \`text\` and
  \`game_time\`.

\`missing\` has the same wire result whether the ID was never issued or
belongs to another recipient. A foreign identifier cannot reveal its
contents. \`oversized\` is explicit; the world refuses to send a partial or
truncated proof when the **double-encoded** outbound JSON frame would
exceed the 48,000-byte safety ceiling (inside the 65,536-byte socket cap).

The handler's \`WorldEventPort\` requires authenticated puppeting and
verifies response nonce, actor, event identity, exact field set, positive
integer sequence, valid sender/recipient, bounded scalar data, finite time
and permitted status. Old or unrelated packets stay in the normal bounded
client queue. The supervisor's \`prove_world_event\` wrapper serializes
lookup with that character's inbox pagination. \`require(kind, sender)\`
does not turn a source-event observation into a new permission.

## Verified vs. remaining properties

The scoped CI includes world-side account/recipient tests and legacy import,
the new typed handler-port tests, and a **real-server two-account WebSocket**
trial. The latter verifies separate private proofs, indistinguishable
foreign/nonexistent IDs, and successful retrieval after a fresh authenticated
connection. None of these tests require hosted model calls.

- This command neither modifies equipment nor grants authority to perform,
  repeat or resolve work. Operation receipts and current-world checks remain
  separate.
- \`missing\` is not a proof of resolution, nor is \`found\` a proof of
  current validity.
- PR #87's open-obligation index is still a disposable *derived local*
  projection. A fresh supervisor continues to hydrate its entire addressed
  inbox before ordinary dispatch; no old character knowledge is silently
  discarded or withheld from Concordia.
- There is **no** history eviction, safe portable cache reuse, world
  snapshot/cursor attestation, or bounded cold-start runtime in this PR.
- A later hot/cold tier must separately account for checkpointed private
  knowledge, unresolved obligation references, legacy unknown readers and
  world journal generation/rewind. Exact lookup is a prerequisite, not
  sufficient authorization to prune local or canonical history.

## Test locations

- \`game/world/tests/test_world_event_lookup.py\`
- \`services/ai-handler/tests/test_world_event_port.py\`
- \`services/ai-handler/tests/test_paged_inbox.py\`
- \`services/ai-handler/src/ox_ai/scenarios/p4f_exact_event_lookup.py\`
- \`.github/workflows/ox-p4f-event-journal.yml\`
