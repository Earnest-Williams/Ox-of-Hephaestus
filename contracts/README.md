# Cross-system contracts: implemented transport and future APIs

**Status (21 October 2026, through G12 and PRs #82–83):** Ox uses an
**ordinary authenticated Evennia WebSocket + game-command/OOB protocol**.
G7b adds persistent typed social agreements, G10b adds authenticated clock
reads, and the PostgreSQL journal now serializes sequence assignment
through commit. The Python `WorldPort` remains an internal prototype
interface, **not** a public multi-character service or browser/handler API.
See [implementation status](../design/STATUS.md).

## Ownership rules

| Information | Sole authority | Handler/view behavior |
| --- | --- | --- |
| Character identity, location, roles, watch, physical machinery | Evennia | Observe or propose via character-authorized game actions |
| Real game time and scheduled due events | Evennia | Verify `oxclock` nonce/actor before mapping game seconds to private memory ticks |
| World physical operation receipts | Evennia | Reconcile unknown by request ID; never infer success from text |
| Stable person IDs, formative aptitudes, professional skills, theoretical mastery, procedure familiarity and awarded learning | Evennia | Read only authorized observations; no agent self-awarded capability or credit |
| Private observations legitimately delivered to a character | Evennia | Feed only that character's Concordia memory |
| Beliefs, private reinterpretations, cognition clocks, plans and unresolved actions | AI handler | Owner-specific records, independent cognition revision and private checkpoints; never world authority |
| Joined dashboards and charts | Future interface | Derived and permissioned; never world authority |

## Implemented ordinary-client wire path (P3/P4)

- Each AI character has its own ordinary Evennia account/session and an
  account-bound puppet permission. The first handshake is `connect`,
  `ic <character-dbref>` and a nonce-backed `oxidentity` proof.
  Bot passwords are not stored in Ox source code.
- The wire uses Evennia's existing `v1.evennia.com` JSON framing.
  Character speech/text cannot stand in for a world receipt.
- A private `ox_event` is an **addressed** game-produced OOB message:
  `event_id`, `recipient_dbref`, `sender_dbref`, `kind`,
  `game_time`, `text` and flat `datum_*` scalar fields for details.
  Nested object dictionaries are **not** valid Evennia OOB payloads.
- `oxinbox <after-sequence>` returns only the authenticated character's
  own persisted events, followed by `ox_inbox_done`. The handler
  verifies recipient, stable ID and framing before placing an event
  in that character's memory.
- `oxaction <32-lowercase-hex-request-id> <isolate|repair|commission>`
  applies normal Evennia role, locality and pump-state checks, writing
  an actor-bound record in the world. The reply is typed `ox_receipt`,
  not arbitrary narrative. `oxreceipt <request-id>` queries it later.
- `DurableEvenniaPort` accepts `succeeded`, `failed` or `unknown`.
  On unknown, the handler must reconcile the **same ID** rather than
  replay the command. An action proposal and a world-issued result are
  different records.
- Supported radio, handover, captain, education and G7b bilateral social
  operations use typed actor-bound world receipts. Free-text speech does not
  form a persistent agreement or prove a motive; arbitrary mid-scene
  activities are not all recoverable.

This is **Ox's current convention on top of ordinary game commands**,
not a stable publicly versioned network schema. See
[`game/commands/ship.py`](../game/commands/ship.py),
[`game/commands/crew.py`](../game/commands/crew.py),
[`world.live_crew`](../game/world/live_crew.py), and the
[external port](../services/ai-handler/src/ox_ai/ports/evennia/durable.py).

## Extended world-owned work and learning (G3–G4)

In addition to the early `oxaction` form above, the game now exposes
`oxwork <request-id> <operation> <subject> ...` and
`oxworkreceipt <request-id>` for typed, globally actor-bound transactions.
The world validates role, locality, current observation and operation-specific
preconditions; receipts and effects are committed together. This common
namespace covers supported physical work, captain handoffs, investigative
reports and the G4g/G4h learning stages. A successful submission receipt
**does not imply a passing assessment**: the actor's addressed assessment
event supplies that result. Replaying the same ID cannot repeat a physical
effect or educational credit, and an unrelated character cannot query it.

G4f practice credits only selected **successful, actual** P-01/C-01/A-01
work receipts. G4g credits one supervised controlled-comparison curriculum
after a world-graded transfer assessment. G4h credits bounded
`investigation.methods` study after a real local question, saved pre-test
forecast, receipted probe and delayed evidence-limits/source-independence
assessment. Hidden causes, bridge hypotheses and unearned role claims cannot
be grading inputs. World capability records remain distinct from an AI's
private belief or self-description. See [G4f](../design/prototypes/g4f-world-receipt-learning.md),
[G4g](../design/prototypes/g4g-verified-conceptual-learning.md) and
[G4h](../design/prototypes/g4h-investigative-learning.md).

## Current G6–G12 additions and transport safety

- G6/G6b terminal actions and mortality remain opt-in game-authoritative
  fixtures. A service receipt proves an equipment operation, **not**
  restoration of an unrelated atmospheric breach.
- G7b `oxwork <request-id> social_<operation> social <encoded-arguments>`
  is a typed participant-specific transaction; `oxsocialstatus` is
  restricted to the parties. Agreed terms do not prove desire; work
  consideration requires verified, unused world-receipt evidence.
- G8–G9 private memories and interpretations belong to the handler.
  `cognition_revision` protects against stale detached inference and
  `OxMemoryContext` exposes only fallible, owner-relevant read-only
  history to native Concordia prompts.
- G10b `oxclock <32-lowercase-hex-nonce>` returns actor-bound `ox_clock`.
  `WorldClockPort` verifies actor, nonce and finite game seconds before
  advancing private time. G8's virtual GOAP decision clock is distinct.
- PostgreSQL journal allocation is **commit-ordered** under a single
  transaction-held lock. `oxinbox` cursors are recipient-scoped and
  replayable; work receipts use events causally emitted by the operation.
  A-01 alarms and captain reminders follow P-01 → ticket → journal locks.
- PR #85's handler processes one full addressed inbox hydration **per
  process** for legacy historical evidence, then requests events strictly
  after its durable character cursor; the five-crew private consumer
  cursors advance independently. Incomplete page counts, inconsistent
  sequence boundaries, malformed continuations or cross-recipient data
  never authorize advancing that cursor. A restart may rehydrate full
  context, and in-process retention is not yet bounded or compacted.
- `receive_matching()` preserves unrelated WebSocket frames in order
  under a 512-packet bound. On saturation it raises **before** reading
  another wire frame. Malformed unattributable `ox_receipt` frames remain
  unmatched and never count as the desired result. The requested ID,
  actor and status remain subject to fail-closed validation.

G11 is a small manual matched-evidence hosted-model A/B harness. G12's
6/20/40 local native-brain profile is **not** 20/40 live crew sessions
or hosted inference latency. Neither changes the world/handler boundary.

## Python-only contract

`services/ai-handler/src/ox_ai/ports/base.py` defines `WorldObservation`,
`ActionRequest`, `ActionOutcome` and the `WorldPort` async protocol.
It is an **internal prototype abstraction**, not a claim that all
implementations already satisfy a formal versioned remote schema.

An observation is delivered to exactly one character with provenance.
A request carries a stable ID, intended character/operation and agent
revision. A missing/ambiguous receipt stays unknown. An agent's
recorded narrative or belief is not an alternative source of physical
truth. On restart the game may continue to progress even while the
handler has missed private events, which must be replayed **only when
legitimately addressed to that character**.

## Planned API boundary (P5 postponed)

Future human inspection requires **two separately authenticated APIs**:
an Evennia-facing world read model and a handler-owned cognitive read
model, joined in the interface with provenance and access control.
Before making those public, design schema versions, pagination/cursors,
stable agent-to-character IDs, access roles, operator-only endpoints and
private-event retention. There is no live API server or published
OpenAPI/JSON wire schema today.

See the [architecture](../ARCHITECTURE.md) and
[deferred interface](../services/interface/README.md).
