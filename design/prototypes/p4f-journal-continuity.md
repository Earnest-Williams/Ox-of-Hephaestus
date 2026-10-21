# Actor-private journal generation and historical prefix attestation

This protocol establishes a verifiable **continuity boundary** between
Evennia's growing authoritative event journal and a handler-owned archive.
It is not a history retention cutoff, world permission system, or an
alternative Concordia memory authority.

## Representation and storage

World migration `0014_journal_continuity` adds a nullable, 64-hex
`chain_hash` to each immutable world `CrewEvent`, and a singleton
`JournalEpoch` containing a 32-hex generation ID. Migration seals the
existing events in world sequence order, without dropping or renumbering
records. That is a **one-time O(history) migration cost**.

For one recipient, the genesis digest is SHA-256 of
`ox-journal-v1:<generation>:<actor-dbref>`. Each subsequent digest is
SHA-256 of the 32 raw bytes of its predecessor plus the UTF-8 canonical
JSON serialization of the **complete** addressed world event, using
sorted keys and no spaces. No other recipient's events enter that chain.

All ordinary `emit` writers already share the PostgreSQL transaction-held
journal advisory lock. Each insertion now attaches its recipient digest in
the **same transaction** as its event ID, content, and notification. An
unsealed predecessor is an error. The one-time legacy importer reseals
its imported history, preserving the original legacy IDs. The explicitly
destructive operator-only test fixture rotates the generation.

The chain is integrity/continuity evidence for world-authored history;
it is not a digital signature protecting against a hostile operator who
can directly rewrite the authoritative database and all its hashes.

## Ordinary authenticated character protocol

`oxjournal <32-lowercase-hex-nonce> <recipient-event-sequence-or-0>`

The request is interpreted **only for the puppeted character**. No
recipient argument or operator-wide history is accepted. One
`ox_journal_proof` OOB packet returns JSON fields:

- `version=1`, `nonce`, `actor_dbref`, `generation`;
- `requested_cursor`, `prefix_digest` (64 lowercase hex, or null);
- `head_cursor` and `head_digest`, for the most recent event addressed
  to this recipient (or cursor 0 and the genesis digest).

A requested nonzero cursor must exactly match an event addressed to the
caller. A foreign-recipient cursor and a nonexistent one have the same
null prefix; no source event details are disclosed. Cursor 0 always
attests the genesis. Reads take the same journal transaction lock as
writers to report a consistent generation/head/prefix snapshot.

The independent typed `WorldJournalPort` requires an authenticated
Evennia client, challenges with a new nonce, preserves unrelated packets,
and verifies exact actor, cursor, version, generation, digest shapes and
head consistency. A fresh certificate for a saved `generation, cursor,
digest` can distinguish an unchanged actor-specific prefix from a
world reset, rewind or historical divergence.

**Negative/nonmatching evidence is not proof that any shipboard work
has been completed.** An old event's authenticity also does not
authorise its operation to run again.

## Scope deliberately postponed

This PR does not use old local SQLite files on startup. Their persisted
complete contents and native private memory/checkpoint revisions must be
verified **together** before a fresh handler can safely skip world inbox
rehydration. A one-event head digest by itself does not prove the bytes
in a local archive. A subsequent change should compare an archive's
complete computed local prefix against the world certificate, and reject
an incompatible world generation or a checkpoint ahead of world history.

Total world journal storage intentionally remains proportional to
historical activity. Long-term engineering goals are efficient local
reuse, indexed cold retrieval and storage/compression management—not
arbitrary forgetting of maintenance or character history.

## Acceptance

- `game/world/tests/test_journal_continuity.py` tests generation
  rotation, legacy resealing, rollback and interleaved private prefixes.
- `services/ai-handler/tests/test_world_journal_port.py` tests malformed,
  foreign, stale and mismatched certificates, and preserved OOB packets.
- Real two-account `p4f_exact_event_lookup` verifies actor boundaries
  and unchanged old prefixes across authenticated reconnection.
